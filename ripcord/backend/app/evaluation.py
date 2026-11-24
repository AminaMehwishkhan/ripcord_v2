"""
evaluation.py

Runs the 10 hand-written scenarios in demo/scenarios.json through the REAL pipeline (entity_detector +
risk_engine + clarification_engine + workflow_guard, via SessionOrchestrator)
twice per scenario — once with Ripcord off (Mode A), once with Ripcord on
(Mode B) — and reports measured outcomes. Per spec section 15: numbers here
are always produced by an actual run of this code, never hand-typed.

Mode B recovery: if a scenario ends with a clarification still pending, this
harness synthesizes ONE follow-up turn representing the user's reply, using
the scenario's own ground-truth `final_value`:
  - if the pending candidate already equals the ground truth, the synthetic
    reply is an affirmation ("Yes, that's right.")
  - otherwise it's a correction restating the true digits ("No, it's 4817.")
  - if the scenario has no recoverable ground truth (e.g. audio cut off
    mid-number), no synthetic reply is injected — leaving the workflow
    correctly un-resolved is the desired behavior, not a failure to patch
    over.
This is clearly a synthesized *evaluation* input, not a real recording —
see docs/evaluation.md.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .mock_service import load_scenarios
from .session import SessionOrchestrator

DIGIT_TO_WORD = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


def _turn_dict(idx: int, turn: dict) -> dict:
    return {
        "transcript": turn["transcript"],
        "end_of_turn": True,
        "turn_order": idx,
        "words": turn["words"],
    }


def _synthetic_reply_turn(idx: int, ground_truth: str, candidate: Optional[str]) -> dict:
    if candidate == ground_truth:
        text, conf_words = "Yes, that's right.", [("Yes,", 0.96), ("that's", 0.97), ("right.", 0.97)]
    else:
        spoken = " ".join(DIGIT_TO_WORD[d] for d in ground_truth)
        text = f"No, it's {spoken}."
        conf_words = [("No,", 0.96), ("it's", 0.97)] + [(w, 0.95) for w in spoken.split()]
        conf_words[-1] = (conf_words[-1][0] + ".", conf_words[-1][1])
    return {
        "transcript": text,
        "end_of_turn": True,
        "turn_order": idx,
        "words": [{"text": t, "confidence": c} for t, c in conf_words],
    }


def _run_pipeline(scenario: dict, ripcord_enabled: bool) -> dict:
    orch = SessionOrchestrator(ripcord_enabled=ripcord_enabled, mock_mode=True)
    ever_clarified = False
    for i, turn in enumerate(scenario["turns"]):
        orch.process_turn(_turn_dict(i, turn))
        if orch.state.clarification is not None:
            ever_clarified = True

    if ripcord_enabled and orch.state.clarification is not None:
        ground_truth = scenario["expect"].get("final_value")
        if ground_truth:
            candidate = orch.state.clarification.candidate_value
            reply = _synthetic_reply_turn(len(scenario["turns"]), ground_truth, candidate)
            orch.process_turn(reply)

    return {
        "final_value": orch.state.verified_value,
        "clarified": ever_clarified,
        "extra_turns": 1 if ever_clarified and orch.state.verified_value else 0,
        "timeline_len": len(orch.state.timeline),
    }


def run_evaluation() -> dict:
    # The recorded (real-ASR) clips are scored properly by app/benchmark.py; this is the quick
    # walk-through of the hand-written illustrations.
    scenarios = [s for s in load_scenarios() if s.get("source") == "scripted"]
    n = len(scenarios)

    without_errors = 0
    with_errors = 0
    recovered = 0
    recoverable = 0
    false_clarifications = 0
    total_clarifications = 0
    extra_turns_total = 0
    per_scenario = []

    for sc in scenarios:
        ground_truth = sc["expect"].get("final_value")
        expect_clarify = bool(sc["expect"].get("should_clarify"))

        mode_a = _run_pipeline(sc, ripcord_enabled=False)
        mode_b = _run_pipeline(sc, ripcord_enabled=True)

        a_wrong = ground_truth is not None and mode_a["final_value"] != ground_truth
        b_wrong = ground_truth is not None and mode_b["final_value"] != ground_truth

        if a_wrong:
            without_errors += 1
        if b_wrong:
            with_errors += 1

        if ground_truth is not None and a_wrong:
            recoverable += 1
            if not b_wrong:
                recovered += 1

        if mode_b["clarified"]:
            total_clarifications += 1
            if not expect_clarify:
                false_clarifications += 1
        extra_turns_total += mode_b["extra_turns"]

        per_scenario.append({
            "id": sc["id"],
            "title": sc["title"],
            "mode_a_value": mode_a["final_value"],
            "mode_b_value": mode_b["final_value"],
            "ground_truth": ground_truth,
            "mode_a_wrong": a_wrong,
            "mode_b_wrong": b_wrong,
            "clarified": mode_b["clarified"],
        })

    return {
        "scenario_count": n,
        "entity_errors_without_ripcord": f"{without_errors} / {n}",
        "entity_errors_with_ripcord": f"{with_errors} / {n}",
        "recovered_correctly": f"{recovered} / {recoverable}" if recoverable else "0 / 0",
        "false_clarifications": f"{false_clarifications} / {n}",
        "verified_entity_rate": f"{n - with_errors} / {n}",
        "avg_extra_turns_from_ripcord": round(extra_turns_total / n, 2) if n else 0,
        "per_scenario": per_scenario,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_evaluation(), indent=2))
