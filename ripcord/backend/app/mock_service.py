"""
mock_service.py

Replay source for demos and development. Reads two files and replays each
scenario's turns as AssemblyAI-shaped Turn message dicts, so the dashboard
and the whole pipeline can be shown without consuming AssemblyAI credits:

  demo/recorded_scenarios.json  real recogniser output (transcripts + genuine
                                per-word confidences) captured by benchmark/
  demo/scenarios.json           10 hand-written illustrative scripts

Per spec section 17: this is NEVER used for the actual hackathon demo or
production path (that always goes through assemblyai_service.py against
the real API when MOCK_MODE=false). The session orchestrator in main.py
is the only place that decides which of the two to use, and every event
this module emits is tagged so the frontend can visibly label it as
simulated audio.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo"
SCENARIOS_PATH = DEMO_DIR / "scenarios.json"                # hand-written, illustrative
RECORDED_PATH = DEMO_DIR / "recorded_scenarios.json"        # real recogniser output (see benchmark/)


def _load(path: Path, source: str) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for s in data["scenarios"]:
        s = dict(s)
        s["source"] = source
        out.append(s)
    return out


def load_scenarios() -> list[dict]:
    """All demo scenarios. Recorded ones (real ASR output) come first."""
    return _load(RECORDED_PATH, "recorded") + _load(SCENARIOS_PATH, "scripted")


def get_scenario(scenario_id: int) -> dict:
    for s in load_scenarios():
        if s["id"] == scenario_id:
            return s
    raise KeyError(f"No mock scenario with id={scenario_id}")


def reply_turn(scenario: dict, kind: str) -> dict | None:
    """The recorded ASR output of the caller's yes/no reply, when the scenario has one."""
    r = (scenario.get("replies") or {}).get(kind)
    if not r:
        return None
    return {"type": "Turn", "turn_order": 99, "end_of_turn": True, "transcript": r["transcript"],
            "end_of_turn_confidence": None, "words": r["words"], "_mock": True}


async def stream_scenario(scenario: dict, turn_delay_seconds: float = 1.4) -> AsyncIterator[dict]:
    """
    Yield Turn-shaped dicts for one scenario, one per configured turn, with
    a small delay between them to feel like a real back-and-forth exchange.
    Mirrors the fields our pipeline actually reads from a real AssemblyAI
    Turn message: type, turn_order, end_of_turn, transcript, words[].
    """
    for i, turn in enumerate(scenario["turns"]):
        await asyncio.sleep(turn_delay_seconds if i > 0 else 0.4)
        words = []
        for w in turn["words"]:
            if "start" in w and "end" in w and w["end"] > w["start"]:
                words.append({"word_is_final": True, **w})
                continue
            # Hand-written scripts carry no timing; leave it at 0 so speaking-rate
            # is treated as "unknown" instead of being computed from invented numbers.
            words.append({
                "text": w["text"], "start": 0, "end": 0,
                "confidence": w["confidence"], "word_is_final": True,
            })
        yield {
            "type": "Turn",
            "turn_order": i,
            "turn_is_formatted": True,
            "end_of_turn": turn.get("end_of_turn", True),
            "transcript": turn["transcript"],
            "end_of_turn_confidence": turn.get("end_of_turn_confidence"),
            "words": words,
            "_mock": True,
        }
