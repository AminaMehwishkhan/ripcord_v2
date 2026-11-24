"""
assemblyai_service.py

Thin, correct wrapper around AssemblyAI's real-time Streaming WebSocket API
(v3). Verified against the live AssemblyAI docs on 2026-09-19:

    Endpoint:  wss://streaming.assemblyai.com/v3/ws
    Auth:      Authorization header with a raw API key (server-side), or a
               short-lived token from GET https://streaming.assemblyai.com/v3/token
               (required for browser clients, since browsers can't set
               WebSocket headers). Ripcord's browser never talks to
               AssemblyAI directly — it streams mic audio to *our* backend,
               which holds the permanent API key and proxies to AssemblyAI.
               So we always use the Authorization header here, server-side.

Message types this module understands (server -> client):
    Begin, SpeechStarted, Turn, Heartbeat, Termination, SpeakerRevision
Message types this module can send (client -> server):
    binary audio chunks, UpdateConfiguration, ForceEndpoint, Terminate, KeepAlive

We only use what Ripcord needs: Turn (for transcript + word confidence) and
Begin/Termination (for session lifecycle). Do not add speaker diarization,
PII redaction, or LLM Gateway wiring here — out of scope for the MVP and
not needed for order-ID verification.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional
from urllib.parse import urlencode

import httpx
import websockets
from websockets.client import WebSocketClientProtocol

from .config import settings

logger = logging.getLogger("ripcord.assemblyai")

AUDIO_CHUNK_MIN_MS = 50
AUDIO_CHUNK_MAX_MS = 1000


class AssemblyAIError(Exception):
    pass


@dataclass
class StreamingConfig:
    sample_rate: int = 16000
    encoding: str = "pcm_s16le"
    speech_model: str = field(default_factory=lambda: settings.assemblyai_speech_model)
    # Boost recognition of the vocabulary our one workflow actually needs.
    # See https://www.assemblyai.com/docs/streaming/keyterms-prompting
    keyterms_prompt: tuple[str, ...] = (
        "order number", "order ID", "booking reference", "confirmation code",
    )
    format_turns: bool = False

    def as_query(self) -> dict[str, str]:
        q = {
            "sample_rate": str(self.sample_rate),
            "encoding": self.encoding,
            "speech_model": self.speech_model,
            "format_turns": "true" if self.format_turns else "false",
        }
        return q


async def generate_temporary_token(expires_in_seconds: int = 60) -> str:
    """
    Generate a short-lived streaming token via GET /v3/token. Ripcord's
    backend doesn't need this for its own connection (it can use the
    Authorization header directly), but it's exposed for completeness /
    in case a future client wants to stream straight from the browser.
    """
    if not settings.has_assemblyai_key:
        raise AssemblyAIError("ASSEMBLYAI_API_KEY is not configured.")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            settings.assemblyai_token_url,
            headers={"Authorization": settings.assemblyai_api_key},
            params={"expires_in_seconds": expires_in_seconds},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["token"]


class AssemblyAIStreamingSession:
    """
    Async context manager around one AssemblyAI v3 streaming WebSocket
    connection. Usage:

        async with AssemblyAIStreamingSession() as session:
            await session.send_audio(chunk)
            async for message in session.messages():
                ...
    """

    def __init__(self, config: Optional[StreamingConfig] = None):
        if not settings.has_assemblyai_key:
            raise AssemblyAIError(
                "ASSEMBLYAI_API_KEY is not configured. Set MOCK_MODE=true to "
                "run without it, or add the key to your .env file."
            )
        self.config = config or StreamingConfig()
        self._ws: Optional[WebSocketClientProtocol] = None

    async def __aenter__(self) -> "AssemblyAIStreamingSession":
        query = self.config.as_query()
        url = f"{settings.assemblyai_streaming_ws_url}?{urlencode(query)}"
        try:
            self._ws = await websockets.connect(
                url,
                extra_headers={"Authorization": settings.assemblyai_api_key},
                ping_interval=15,
                ping_timeout=20,
                max_size=None,
            )
        except Exception as exc:  # noqa: BLE001 — surface as a typed error
            raise AssemblyAIError(f"Failed to connect to AssemblyAI streaming: {exc}") from exc

        # First message must be a "Begin" session confirmation.
        raw = await self._ws.recv()
        begin = json.loads(raw)
        if begin.get("type") != "Begin":
            raise AssemblyAIError(f"Unexpected first message from AssemblyAI: {begin}")
        logger.info("AssemblyAI session started: %s", begin.get("id"))
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "Terminate"}))
            except Exception:  # noqa: BLE001
                pass
            await self._ws.close()

    async def send_audio(self, chunk: bytes) -> None:
        """Send a raw PCM16 chunk (50ms-1000ms of audio, per AssemblyAI docs)."""
        if self._ws is None:
            raise AssemblyAIError("Session not connected.")
        await self._ws.send(chunk)

    async def update_agent_context(self, agent_reply_text: str) -> None:
        """Feed the agent's last spoken reply back in as context (helps
        accuracy on short/ambiguous replies like a bare confirmation)."""
        if self._ws is None:
            return
        await self._ws.send(json.dumps({
            "type": "UpdateConfiguration",
            "agent_context": agent_reply_text[:1750],
        }))

    async def force_endpoint(self) -> None:
        if self._ws is not None:
            await self._ws.send(json.dumps({"type": "ForceEndpoint"}))

    async def messages(self) -> AsyncIterator[dict]:
        if self._ws is None:
            raise AssemblyAIError("Session not connected.")
        async for raw in self._ws:
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Non-JSON message from AssemblyAI, ignoring: %r", raw[:200])
