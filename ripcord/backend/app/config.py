"""
Ripcord backend configuration.

Loads settings from environment variables (and a local .env file for
development). Nothing here should ever hard-code a secret.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str) -> Optional[float]:
    val = os.getenv(name)
    if val is None or not val.strip():
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _list_env(name: str, default: list[str]) -> list[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    assemblyai_api_key: str = field(default_factory=lambda: os.getenv("ASSEMBLYAI_API_KEY", ""))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_key: str = field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))

    # MOCK_MODE defaults to true so the project runs out of the box without
    # any credentials. The hackathon demo must be run with MOCK_MODE=false.
    mock_mode: bool = field(default_factory=lambda: _bool_env("MOCK_MODE", True))

    cors_origins: list[str] = field(
        default_factory=lambda: _list_env(
            "CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"]
        )
    )

    # Streaming (real-time) speech model. See:
    # https://www.assemblyai.com/docs/streaming/select-the-speech-model
    # Valid values as of this build: universal-3-5-pro, universal-streaming-english,
    # universal-streaming-multilingual. We default to the English streaming model
    # since it exposes end_of_turn_confidence_threshold tuning and is the
    # cheapest/fastest option for the single-language MVP demo.
    assemblyai_speech_model: str = field(
        default_factory=lambda: os.getenv("ASSEMBLYAI_SPEECH_MODEL", "universal-streaming-english")
    )

    assemblyai_streaming_ws_url: str = "wss://streaming.assemblyai.com/v3/ws"
    assemblyai_token_url: str = "https://streaming.assemblyai.com/v3/token"

    # Optional manual override of the clarify threshold (a probability, 0-1).
    # Leave unset to use the operating point stored with the trained model
    # (backend/app/risk_model.json), which is chosen on validation data.
    risk_clarify_threshold_override: Optional[float] = field(
        default_factory=lambda: _float_env("RISK_CLARIFY_THRESHOLD")
    )

    @property
    def has_assemblyai_key(self) -> bool:
        return bool(self.assemblyai_api_key)


settings = Settings()
