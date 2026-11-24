"""
event_log.py

Minimal local persistence for session summaries, so the dashboard can show
"past sessions" across page reloads/restarts without requiring Supabase to
be configured (Supabase remains a drop-in upgrade path — see
docs/architecture.md — this just means the project isn't dead in the water
without it).

Appends one JSON line per finished session to backend/data/sessions.jsonl.
Never stores raw audio or full transcripts beyond what's already visible in
the UI during the session — just the same summary the client already saw.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from .models import SessionState

LOG_DIR = Path(__file__).resolve().parents[2] / "backend" / "data"
LOG_PATH = LOG_DIR / "sessions.jsonl"

MAX_SESSIONS_RETURNED = 50


def record_session(state: SessionState) -> None:
    """Append a compact summary of a finished session. Best-effort: a
    logging failure should never take down the live session."""
    if not state.history and not state.transcript:
        return  # nothing happened worth remembering
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "session_id": state.session_id,
            "ended_at": time.time(),
            "ripcord_enabled": state.ripcord_enabled,
            "mock_mode": state.mock_mode,
            "entity_count": len(state.history),
            "clarifications_required": sum(1 for h in state.history if h.required_clarification),
            "final_transcript": state.transcript,
            "history": [h.model_dump() for h in state.history],
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # persistence is a convenience, not a dependency


def list_recent_sessions(limit: int = MAX_SESSIONS_RETURNED) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    lines: list[dict] = []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return lines[-limit:][::-1]  # most recent first
