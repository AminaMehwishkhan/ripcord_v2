"""
make_demo_scenarios.py — turn a handful of REAL recorded utterances into dashboard demos.

Writes demo/recorded_scenarios.json. Every clip is genuine recogniser output (transcript
and per-word confidence), taken from the VALIDATION split, never the test split.

The clips are picked to show each kind of outcome — including failures. They are
illustrations, not a sample: the honest numbers are on the Benchmark tab.

    python make_demo_scenarios.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.benchmark import entity_of, load_items, make_policies, reply_entity_of, run_item  # noqa: E402
from app.risk_model import load_model  # noqa: E402

OUT = ROOT / "demo" / "recorded_scenarios.json"
FIRST_ID = 101

# (category, title, how to describe it)
CATEGORIES = [
    ("clean-pass", "Clean line, no question needed", 2),
    ("noisy-caught", "Heard wrong in noise, caught and fixed", 2),
    ("phone-line", "Phone-line audio", 1),
    ("restated-wrong", "Caller repeats it and is misheard again: it asks again, never guesses", 1),
    ("confidently-wrong", "Heard wrong and Ripcord did NOT catch it (a miss)", 2),
]


def spaced(digits: str) -> str:
    return " ".join(digits)


def main() -> None:
    model = load_model()
    if model is None:
        sys.exit("Train the model first: python benchmark/train_risk_model.py")
    base = model.meta["baselines"]
    policy = make_policies(model, base["asr_mean_conf_threshold"], base["asr_min_conf_threshold"])["ripcord_v2"]

    val = [i for i in load_items() if i["split"] == "val"]
    buckets: dict[str, list[dict]] = {c: [] for c, _, _ in CATEGORIES}
    for it in val:
        e = entity_of(it)
        if e is None:
            continue
        run = run_item(it, policy)
        ok = e.value == it["true_value"]
        asked = run["asked"]
        r = reply_entity_of(it)
        info = {"item": it, "entity": e, "run": run}
        noisy = it["condition"] in ("snr10", "snr5", "snr0")
        if ok and not asked and it["condition"] in ("clean", "snr25"):
            buckets["clean-pass"].append(info)
        if not ok and asked and run["outcome"] == "correct" and noisy:
            buckets["noisy-caught"].append(info)
        if it["condition"] == "phone" and (ok or run["outcome"] == "correct"):
            buckets["phone-line"].append(info)
        if not ok and asked and r is not None and r.value != it["true_value"]:
            buckets["restated-wrong"].append(info)
        if not ok and not asked and e.format_valid:
            buckets["confidently-wrong"].append(info)

    scenarios, used, next_id = [], set(), FIRST_ID
    for cat, title, count in CATEGORIES:
        # prefer the clearest examples: for catches, the ones with the lowest min-confidence
        pool = [b for b in buckets[cat] if b["item"]["id"] not in used]
        if cat == "clean-pass":
            pool.sort(key=lambda b: -b["entity"].min_confidence)
        elif cat == "confidently-wrong":
            pool.sort(key=lambda b: b["entity"].min_confidence)
        pool = pool[:count]
        if len(pool) < count:
            print(f"  note: only {len(pool)} clip(s) found for '{cat}'")
        for b in pool:
            it = b["item"]
            used.add(it["id"])
            asr = it["asr"]
            truth = it["true_value"]
            scenarios.append({
                "id": next_id,
                "title": title,
                "spoken": truth,
                "category": cat,
                "condition": it["condition"],
                "speaker": it["speaker"],
                "clip_id": it["id"],
                "turns": [{"transcript": asr["transcript"], "end_of_turn": True, "words": asr["words"]}],
                "replies": {k: {"transcript": it[f"reply_{k}"]["transcript"], "words": it[f"reply_{k}"]["words"]}
                            for k in ("yes", "no") if it.get(f"reply_{k}")},
                "expect": {"final_value": truth, "heard": b["entity"].value, "ripcord_asked": b["run"]["asked"]},
            })
            next_id += 1

    OUT.write_text(json.dumps({
        "note": ("Real recogniser output (sherpa-onnx Zipformer) on synthetic speech, taken from the validation "
                 "split and picked to show each kind of outcome. Not a representative sample."),
        "scenarios": scenarios,
    }, indent=1))
    print(f"wrote {len(scenarios)} scenarios -> {OUT.relative_to(ROOT)}")
    for s in scenarios:
        print(f"  {s['id']}  {s['category']:<20} {s['condition']:<7} truth {s['spoken']}  heard {s['expect']['heard']}  "
              f"-> \"{s['turns'][0]['transcript']}\"")


if __name__ == "__main__":
    main()
