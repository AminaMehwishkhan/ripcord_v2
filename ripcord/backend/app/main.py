"""
main.py — Ripcord backend entrypoint.

REST:
    GET  /api/health        liveness check, mock/real mode, trained-model info
    GET  /api/scenarios     demo scenarios: recorded real-ASR ones + scripted ones
    GET  /api/benchmark     held-out benchmark results (benchmark/results/)
    GET  /api/evaluation    re-run the 10 scripted scenarios through the pipeline
    POST /api/assess        score any transcript + word confidences (playground)
    GET  /api/sessions      recent past sessions (local JSONL log)

WebSocket:
    /ws/session              one Ripcord session. See README "WebSocket
                             protocol" for the full message reference.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, Field

from .assemblyai_service import AssemblyAIError, AssemblyAIStreamingSession
from .benchmark import RESULTS_PATH
from .clarification_engine import build_clarification
from .config import settings
from .entity_detector import detect_critical_entity
from .evaluation import run_evaluation
from .event_log import list_recent_sessions, record_session
from .mock_service import get_scenario, load_scenarios, reply_turn, stream_scenario
from .models import Word
from .risk_engine import RiskContext, assess_risk
from .risk_model import load_model
from .session import SessionOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ripcord.main")

app = FastAPI(title="Ripcord", description="Real-Time Self-Repair for Voice Agents")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_AAI_RECONNECT_ATTEMPTS = 4
AAI_RECONNECT_BASE_DELAY_S = 1.5


@app.get("/api/health")
def health():
    model = load_model()
    return {
        "status": "ok",
        "mock_mode": settings.mock_mode,
        "assemblyai_key_configured": settings.has_assemblyai_key,
        "risk_engine": "learned-v2" if model else "rules-v1",
        "clarify_threshold": settings.risk_clarify_threshold_override
        if settings.risk_clarify_threshold_override is not None else (model.threshold if model else 0.35),
        "model_meta": model.meta if model else None,
    }


@app.get("/api/scenarios")
def scenarios():
    out = []
    for s in load_scenarios():
        out.append({
            "id": s["id"], "title": s["title"], "spoken": s["spoken"], "source": s.get("source", "scripted"),
            "condition": s.get("condition"), "has_replies": bool(s.get("replies")),
            "truth": (s.get("expect") or {}).get("final_value"), "category": s.get("category"),
        })
    return out


@app.get("/api/benchmark")
def benchmark():
    if not RESULTS_PATH.exists():
        raise HTTPException(404, "No benchmark results yet — run benchmark/evaluate.py")
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


@app.get("/api/evaluation")
def evaluation():
    return run_evaluation()


@app.get("/api/sessions")
def sessions():
    return list_recent_sessions()


class AssessWord(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)


class AssessRequest(BaseModel):
    transcript: str = ""
    words: list[AssessWord] = Field(default_factory=list)


@app.post("/api/assess")
def assess(req: AssessRequest):
    """Score any transcript + per-word confidences — powers the dashboard playground."""
    words = [Word(text=w.text, confidence=w.confidence) for w in req.words]
    entity = detect_critical_entity(req.transcript, words)
    if entity is None:
        return {"entity": None, "risk": None, "question": None}
    risk = assess_risk(entity, RiskContext())
    question = build_clarification(entity, risk) if risk.should_clarify else None
    return {"entity": json.loads(entity.model_dump_json()), "risk": json.loads(risk.model_dump_json()),
            "question": json.loads(question.model_dump_json()) if question else None}


@app.websocket("/ws/session")
async def session_ws(ws: WebSocket):
    await ws.accept()
    orch: Optional[SessionOrchestrator] = None
    aai_session: Optional[AssemblyAIStreamingSession] = None
    aai_reader_task: Optional[asyncio.Task] = None
    real_stream_requested = False  # tracks intent, so a dropped connection knows to reconnect
    active_scenario: Optional[dict] = None  # last scenario replayed in this connection

    async def send_state():
        await ws.send_json({"type": "state", "state": json.loads(orch.state.model_dump_json())})

    async def send_error(message: str):
        await ws.send_json({"type": "error", "message": message})

    async def run_mock_scenario(scenario_id: int):
        nonlocal orch, active_scenario
        scenario = get_scenario(scenario_id)
        active_scenario = scenario
        async for turn in stream_scenario(scenario):
            orch.process_turn(turn)
            await send_state()

    async def run_compare(scenario_id: int, auto_reply: bool = True):
        """Run one scenario through Mode A and Mode B side by side."""
        scenario = get_scenario(scenario_id)
        truth = (scenario.get("expect") or {}).get("final_value")
        a = SessionOrchestrator(ripcord_enabled=False, mock_mode=True)
        b = SessionOrchestrator(ripcord_enabled=True, mock_mode=True)

        async def push():
            await ws.send_json({
                "type": "compare", "truth": truth, "scenario_id": scenario_id,
                "a": json.loads(a.state.model_dump_json()), "b": json.loads(b.state.model_dump_json()),
            })

        await push()
        async for turn in stream_scenario(scenario):
            a.process_turn(turn)
            b.process_turn(turn)
            await push()
        if auto_reply and b.state.clarification is not None:
            await asyncio.sleep(1.4)
            kind = "yes" if b.state.clarification.candidate_value == truth else "no"
            rt = reply_turn(scenario, kind)
            if rt is None:  # scripted scenarios have no recording: synthesise the reply text
                names = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
                         "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}
                text = "Yes, that's right." if kind == "yes" else "No, it's " + " ".join(names[d] for d in (truth or ""))
                rt = {"transcript": text, "end_of_turn": True,
                      "words": [{"text": w, "confidence": 0.95} for w in text.split()]}
            b.process_turn(rt)
            await push()

    async def connect_real_stream(ripcord_enabled: bool) -> bool:
        """Open (or re-open) the AssemblyAI session. Returns True on success."""
        nonlocal aai_session, orch
        if orch is None:
            orch = SessionOrchestrator(ripcord_enabled=ripcord_enabled, mock_mode=False)
        orch.state.connection_status = "connecting"
        await send_state()
        try:
            aai_session = AssemblyAIStreamingSession()
            await aai_session.__aenter__()
        except AssemblyAIError as exc:
            orch.state.connection_status = "disconnected"
            await send_state()
            await send_error(str(exc))
            return False
        orch.state.connection_status = "live"
        await send_state()
        return True

    async def read_real_transcripts():
        """
        Background task: pump AssemblyAI Turn messages into the orchestrator.
        If the stream drops unexpectedly (network blip, idle timeout) while
        the user still wants a real session, retry with backoff instead of
        just dying — a dropped mic connection mid-call is exactly the kind
        of thing a "reliability layer" product shouldn't itself be fragile
        about.
        """
        nonlocal aai_session, orch
        attempt = 0
        while real_stream_requested:
            try:
                async for message in aai_session.messages():
                    attempt = 0  # reset backoff after any successful message
                    mtype = message.get("type")
                    if mtype == "Turn":
                        orch.process_turn(message)
                        await send_state()
                    elif mtype == "Termination":
                        await ws.send_json({"type": "system", "message": "AssemblyAI session ended."})
                return  # clean end, not an error — don't reconnect
            except Exception as exc:  # noqa: BLE001
                if not real_stream_requested:
                    return
                attempt += 1
                logger.warning("AssemblyAI stream dropped (attempt %d): %s", attempt, exc)
                if attempt > MAX_AAI_RECONNECT_ATTEMPTS:
                    orch.state.connection_status = "disconnected"
                    await send_state()
                    await send_error(
                        f"Lost connection to AssemblyAI after {MAX_AAI_RECONNECT_ATTEMPTS} retries: {exc}"
                    )
                    return
                orch.state.connection_status = "reconnecting"
                await send_state()
                await asyncio.sleep(AAI_RECONNECT_BASE_DELAY_S * (2 ** (attempt - 1)))
                if not real_stream_requested:
                    return
                ok = await connect_real_stream(orch.state.ripcord_enabled)
                if not ok:
                    return

    try:
        while True:
            try:
                message = await ws.receive()
            except RuntimeError:
                # Starlette raises RuntimeError (rather than WebSocketDisconnect)
                # if receive() is called again after a disconnect has already
                # been observed. Treat it the same as a clean disconnect.
                break

            if "bytes" in message and message["bytes"] is not None:
                if aai_session is not None:
                    try:
                        await aai_session.send_audio(message["bytes"])
                    except Exception:  # noqa: BLE001
                        pass  # the reader task's reconnect loop will handle it
                continue

            if "text" not in message or message["text"] is None:
                continue

            try:
                payload = json.loads(message["text"])
            except json.JSONDecodeError:
                await send_error("Malformed JSON control message.")
                continue

            action = payload.get("action")

            if action == "start_session":
                ripcord_enabled = bool(payload.get("ripcord_enabled", True))
                mock = bool(payload.get("mock_mode", settings.mock_mode))
                orch = SessionOrchestrator(ripcord_enabled=ripcord_enabled, mock_mode=mock)
                await send_state()

            elif action == "toggle_ripcord":
                if orch is None:
                    await send_error("Start a session first.")
                    continue
                orch.set_ripcord_enabled(bool(payload.get("enabled", True)))
                await send_state()

            elif action == "run_mock_scenario":
                if orch is None:
                    orch = SessionOrchestrator(
                        ripcord_enabled=bool(payload.get("ripcord_enabled", True)), mock_mode=True
                    )
                scenario_id = int(payload.get("scenario_id", 1))
                try:
                    await run_mock_scenario(scenario_id)
                except KeyError:
                    await send_error(f"Unknown scenario_id {scenario_id}")

            elif action == "run_compare":
                try:
                    await run_compare(int(payload.get("scenario_id", 1)), bool(payload.get("auto_reply", True)))
                except KeyError:
                    await send_error(f"Unknown scenario_id {payload.get('scenario_id')}")

            elif action == "recorded_reply":
                if orch is None or active_scenario is None:
                    await send_error("Run a scenario first.")
                    continue
                rt = reply_turn(active_scenario, str(payload.get("kind", "yes")))
                if rt is None:
                    await send_error("This scenario has no recorded reply of that kind — type one instead.")
                    continue
                orch.process_turn(rt)
                await send_state()

            elif action == "reset":
                orch = SessionOrchestrator(
                    ripcord_enabled=orch.state.ripcord_enabled if orch else True, mock_mode=True
                )
                active_scenario = None
                await send_state()

            elif action == "start_real_stream":
                if settings.mock_mode or not settings.has_assemblyai_key:
                    await send_error(
                        "Real streaming isn't available: MOCK_MODE is on or "
                        "ASSEMBLYAI_API_KEY is missing."
                    )
                    continue
                real_stream_requested = True
                ripcord_enabled = bool(payload.get("ripcord_enabled", True))
                ok = await connect_real_stream(ripcord_enabled)
                if ok:
                    aai_reader_task = asyncio.create_task(read_real_transcripts())
                    await ws.send_json({"type": "system", "message": "Real AssemblyAI stream connected."})

            elif action == "user_response":
                # Text fallback for the clarification reply (used in mock mode,
                # or as a typed backup if mic input isn't available).
                if orch is None:
                    await send_error("Start a session first.")
                    continue
                text = str(payload.get("text", ""))
                orch.process_turn({
                    "transcript": text,
                    "end_of_turn": True,
                    "words": [{"text": w, "confidence": 0.95} for w in text.split()],
                })
                await send_state()

            elif action == "stop":
                real_stream_requested = False
                if aai_reader_task is not None:
                    aai_reader_task.cancel()
                    aai_reader_task = None
                if aai_session is not None:
                    await aai_session.__aexit__(None, None, None)
                    aai_session = None
                if orch is not None:
                    orch.state.connection_status = "idle" if orch.state.mock_mode else "disconnected"
                    await send_state()
                await ws.send_json({"type": "system", "message": "Session stopped."})

            else:
                await send_error(f"Unknown action: {action}")

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        real_stream_requested = False
        if aai_reader_task is not None:
            aai_reader_task.cancel()
        if aai_session is not None:
            try:
                await aai_session.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
        if orch is not None:
            record_session(orch.state)


# Serve the built dashboard from the same process when `npm run build` has been run,
# so `uvicorn app.main:app` alone gives you the full app at http://localhost:8000.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="dashboard")
