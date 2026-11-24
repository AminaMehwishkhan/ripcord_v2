"""
benchmark.py — evaluate Ripcord on recorded recogniser output.

The data comes from benchmark/build_dataset.py: synthetic speech, degraded with
noise / phone band / reverb / fast speech, transcribed by a REAL streaming
recogniser, with ground truth for every number. Every number reported here is
computed by running the actual pipeline (entity_detector -> risk engine ->
SessionOrchestrator) over those recordings — nothing is typed by hand.

Pure Python on purpose: no numpy needed to run the evaluation from the API.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Callable, Iterable, Optional

from .entity_detector import detect_critical_entity
from .models import CriticalEntity, RiskAssessment, Word
from .risk_engine import RiskContext, assess_risk_learned, assess_risk_rules
from .risk_model import RiskModel
from .session import SessionOrchestrator

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "benchmark" / "data"
RESULTS_PATH = ROOT / "benchmark" / "results" / "benchmark_results.json"

CONDITION_GROUPS = {
    "clean": "Clean", "snr25": "Light noise (25 dB)", "snr15": "Moderate noise (15 dB)",
    "snr10": "Heavy noise (10 dB)", "snr5": "Very heavy noise (5 dB)", "snr0": "Extreme noise (0 dB)",
    "phone": "Phone line", "reverb": "Echoey room",
}
CONDITION_ORDER = list(CONDITION_GROUPS)


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

def load_items(data_dir: Path = DATA_DIR) -> list[dict]:
    items: list[dict] = []
    for p in sorted(data_dir.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                items.append(json.loads(line))
    items.sort(key=lambda r: r["id"])
    return items


def _turn(asr: dict, order: int = 0) -> dict:
    return {"transcript": asr["transcript"], "end_of_turn": True, "turn_order": order, "words": asr["words"]}


def entity_of(item: dict) -> Optional[CriticalEntity]:
    words = [Word(**w) for w in item["asr"]["words"]]
    return detect_critical_entity(item["asr"]["transcript"], words)


def reply_entity_of(item: dict) -> Optional[CriticalEntity]:
    """The restated number in the stored 'no, it's …' reply, if any."""
    r = item.get("reply_no")
    if not r:
        return None
    return detect_critical_entity(r["transcript"], [Word(**w) for w in r["words"]])


# ---------------------------------------------------------------------------
# policies: how a system decides "ask" vs "accept"
# ---------------------------------------------------------------------------

def _fixed(should: bool, score: float = 0.0) -> RiskAssessment:
    return RiskAssessment(risk_score=score, risk_level="LOW", should_clarify=should, signals=[],  # type: ignore[arg-type]
                          breakdown={}, engine="baseline")


def make_policies(model: Optional[RiskModel], conf_threshold: float, min_threshold: float,
                  rules_threshold: float = 0.35) -> dict[str, Callable[[CriticalEntity, RiskContext], RiskAssessment]]:
    pol: dict[str, Callable] = {
        "no_check": lambda e, c: _fixed(False),
        "always_confirm": lambda e, c: _fixed(True, 1.0),
        "asr_mean_conf": lambda e, c: _fixed(e.confidence < conf_threshold or not e.format_valid, 1 - e.confidence),
        "asr_min_conf": lambda e, c: _fixed(e.min_confidence < min_threshold or not e.format_valid, 1 - e.min_confidence),
        "ripcord_v1_rules": lambda e, c: assess_risk_rules(e, c, rules_threshold),
    }
    if model is not None:
        pol["ripcord_v2"] = lambda e, c: assess_risk_learned(e, c, model)
    return pol


POLICY_LABELS = {
    "no_check": "No check (plain voice agent)",
    "always_confirm": "Always read back",
    "asr_mean_conf": "ASR confidence threshold",
    "asr_min_conf": "Weakest-digit threshold",
    "ripcord_v1_rules": "Ripcord v1 (hand-tuned rules)",
    "ripcord_v2": "Ripcord v2 (learned)",
}


def run_item(item: dict, policy: Callable, ripcord: bool = True) -> dict:
    """Run ONE recorded utterance through the real orchestrator under a policy.

    ripcord=False is the plain voice agent (Mode A): it accepts whatever it heard.
    """
    truth = item["true_value"]
    entity = entity_of(item)
    out = {"id": item["id"], "truth": truth, "captured": entity.value if entity else None,
           "capture_ok": bool(entity and entity.value == truth), "asked": False, "questions": 0,
           "outcome": None, "final": None, "format_valid": bool(entity and entity.format_valid)}
    if entity is None:
        out.update(outcome="unresolved", asked=True, questions=1)  # nothing to act on: agent re-prompts
        return out

    orch = SessionOrchestrator(ripcord_enabled=ripcord, mock_mode=True, risk_fn=policy)
    orch.process_turn(_turn(item["asr"]))
    if orch.state.clarification is not None:
        reply = item["reply_yes"] if entity.value == truth else item.get("reply_no")
        if reply is not None:
            orch.process_turn(_turn(reply, 1))
    out["asked"] = orch.questions_asked > 0
    out["questions"] = orch.questions_asked
    if orch.state.action_result is not None and orch.state.verified_value is not None:
        out["final"] = orch.state.verified_value
        out["outcome"] = "correct" if orch.state.verified_value == truth else "wrong"
    else:
        out["outcome"] = "unresolved"
    return out


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def auroc(scores: list[float], labels: list[int]) -> Optional[float]:
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    ranked = sorted([(s, y) for s, y in zip(scores, labels)], key=lambda t: t[0])
    # Mann-Whitney U with tie handling via average ranks
    ranks = [0.0] * len(ranked)
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = (i + j) / 2 + 1
        i = j + 1
    r_pos = sum(r for r, (_, y) in zip(ranks, ranked) if y == 1)
    u = r_pos - len(pos) * (len(pos) + 1) / 2
    return round(u / (len(pos) * len(neg)), 4)


def bootstrap_ci(values: list[float], reps: int = 1000, seed: int = 11) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    return round(means[int(0.025 * reps)], 4), round(means[int(0.975 * reps) - 1], 4)


def rate(values: list[float]) -> dict:
    n = len(values)
    m = sum(values) / n if n else 0.0
    lo, hi = bootstrap_ci(values)
    return {"value": round(m, 4), "ci": [lo, hi], "n": n}


def summarise(runs: list[dict]) -> dict:
    n = len(runs)
    has_ent = [r for r in runs if r["captured"] is not None]
    wrong_cap = [r for r in has_ent if not r["capture_ok"]]
    right_cap = [r for r in has_ent if r["capture_ok"]]
    # The hard case: a wrong number that still LOOKS like a normal 4-digit order number.
    # A bad length is easy to spot; these are the ones that slip through.
    wrong_valid = [r for r in wrong_cap if r.get("format_valid", True)]
    return {
        "n": n,
        "wrong_action": rate([1.0 if r["outcome"] == "wrong" else 0.0 for r in runs]),
        "correct_action": rate([1.0 if r["outcome"] == "correct" else 0.0 for r in runs]),
        "unresolved": rate([1.0 if r["outcome"] == "unresolved" else 0.0 for r in runs]),
        "questions_per_call": rate([float(r["questions"]) for r in runs]),
        "error_catch_rate": rate([1.0 if r["asked"] else 0.0 for r in wrong_cap]) if wrong_cap else None,
        "false_alarm_rate": rate([1.0 if r["asked"] else 0.0 for r in right_cap]) if right_cap else None,
        "silent_catch_rate": rate([1.0 if r["asked"] else 0.0 for r in wrong_valid]) if wrong_valid else None,
        "misheard_valid_format_calls": len(wrong_valid),
        "misheard_calls": len(wrong_cap),
        "clean_capture_calls": len(right_cap),
    }


def reliability(preds: list[float], labels: list[int], bins: int = 8) -> dict:
    """Calibration: predicted probability of 'wrong' vs how often the capture really was wrong."""
    rows = []
    ece = 0.0
    n = len(preds)
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(preds) if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if not idx:
            continue
        mp = sum(preds[i] for i in idx) / len(idx)
        obs = sum(labels[i] for i in idx) / len(idx)
        ece += len(idx) / n * abs(mp - obs)
        rows.append({"bin": f"{lo:.2f}-{hi:.2f}", "predicted": round(mp, 3), "observed": round(obs, 3), "n": len(idx)})
    return {"bins": rows, "ece": round(ece, 4)}


def operating_curve(scores: list[float], labels: list[int], steps: int = 40) -> list[dict]:
    """Sweep a threshold: how many wrong captures get flagged vs how many right ones get flagged."""
    pos = sum(labels)
    neg = len(labels) - pos
    pts = []
    for k in range(steps + 1):
        t = k / steps
        tp = sum(1 for s, y in zip(scores, labels) if y == 1 and s >= t)
        fp = sum(1 for s, y in zip(scores, labels) if y == 0 and s >= t)
        pts.append({"threshold": round(t, 3), "catch": round(tp / pos, 4) if pos else 0.0,
                    "false_alarm": round(fp / neg, 4) if neg else 0.0})
    return pts


def evaluate(items: Iterable[dict], model: Optional[RiskModel], conf_threshold: float,
             min_threshold: float, split_label: str = "test") -> dict:
    items = list(items)
    policies = make_policies(model, conf_threshold, min_threshold)
    runs: dict[str, list[dict]] = {
        name: [run_item(it, fn, ripcord=(name != "no_check")) for it in items] for name, fn in policies.items()
    }

    # score-quality for the risk scores, on the first capture of each call
    score_fns: dict[str, Callable[[CriticalEntity], float]] = {
        "asr_mean_conf": lambda e: 1.0 if not e.format_valid else 1 - e.confidence,
        "asr_min_conf": lambda e: 1.0 if not e.format_valid else 1 - e.min_confidence,
        "ripcord_v1_rules": lambda e: assess_risk_rules(e, RiskContext()).risk_score,
    }
    if model is not None:
        score_fns["ripcord_v2"] = lambda e: assess_risk_learned(e, RiskContext(), model).risk_score
    ents = [(it, entity_of(it)) for it in items]
    ents = [(it, e) for it, e in ents if e is not None]
    labels = [0 if e.value == it["true_value"] else 1 for it, e in ents]
    scores = {k: [fn(e) for _, e in ents] for k, fn in score_fns.items()}
    # same ranking quality, but only on captures that already look like valid 4-digit numbers
    vf = [i for i, (_, e) in enumerate(ents) if e.format_valid]
    labels_vf = [labels[i] for i in vf]
    auroc_vf = {k: auroc([v[i] for i in vf], labels_vf) for k, v in scores.items()}

    by_cond: dict[str, dict] = {}
    for cond in CONDITION_ORDER:
        idx = [i for i, it in enumerate(items) if it["condition"] == cond]
        if not idx:
            continue
        by_cond[cond] = {"label": CONDITION_GROUPS[cond], "n": len(idx)}
        for name in ("no_check", "ripcord_v2"):
            if name in runs:
                sub = [runs[name][i] for i in idx]
                by_cond[cond][name] = {
                    "wrong_action": round(sum(1 for r in sub if r["outcome"] == "wrong") / len(sub), 4),
                    "asked": round(sum(1 for r in sub if r["asked"]) / len(sub), 4),
                }

    silent = []
    if "ripcord_v2" in runs:
        for it, r in zip(items, runs["ripcord_v2"]):
            if r["outcome"] == "wrong":
                e = entity_of(it)
                silent.append({
                    "id": it["id"], "condition": it["condition"], "truth": it["true_value"],
                    "heard": r["final"], "transcript": it["asr"]["transcript"],
                    "min_conf": e.min_confidence if e else None, "mean_conf": e.confidence if e else None,
                })

    return {
        "split": split_label,
        "n_calls": len(items),
        "capture_error_rate": round(sum(labels) / len(labels), 4) if labels else None,
        "no_entity_rate": round(1 - len(ents) / len(items), 4) if items else None,
        "policies": {name: {"label": POLICY_LABELS[name], **summarise(rs)} for name, rs in runs.items()},
        "auroc": {k: auroc(v, labels) for k, v in scores.items()},
        "auroc_valid_format": auroc_vf,
        "format_valid_rate": round(len(vf) / len(ents), 4) if ents else None,
        "curves": {k: operating_curve(v, labels) for k, v in scores.items()},
        "reliability": reliability(scores["ripcord_v2"], labels) if "ripcord_v2" in scores else None,
        "by_condition": by_cond,
        "silent_failures": silent[:25],
    }
