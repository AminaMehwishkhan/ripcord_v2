"""
evaluate.py — score every system on the held-out TEST split and write
benchmark/results/benchmark_results.json (the file the dashboard's Benchmark tab reads).

    python evaluate.py            # test split
    python evaluate.py --split val
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.benchmark import RESULTS_PATH, evaluate, load_items  # noqa: E402
from app.risk_model import load_model  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", type=Path, default=RESULTS_PATH)
    args = ap.parse_args()

    model = load_model()
    if model is None:
        sys.exit("No trained model: run train_risk_model.py first.")
    base = model.meta["baselines"]
    items = [i for i in load_items() if i["split"] == args.split]
    print(f"evaluating {len(items)} '{args.split}' utterances …")
    res = evaluate(items, model, base["asr_mean_conf_threshold"], base["asr_min_conf_threshold"], args.split)
    res["model"] = {
        "features": list(model.names), "weights": list(model.weights), "mean": list(model.mean),
        "std": list(model.std), "ref": list(model.ref), "bias": model.bias, "threshold": model.threshold, "invalid_format_p": model.invalid_format_p,
        "meta": model.meta,
    }
    res["hard_case"] = model.meta.get("hard_case")
    res["generated"] = time.strftime("%Y-%m-%d %H:%M")
    all_items = load_items()
    res["dataset"] = {
        "total": len(all_items),
        "per_split": {s: sum(1 for i in all_items if i["split"] == s) for s in ("train", "val", "test")},
        "speakers": len({i["speaker"] for i in all_items}),
        "asr": "sherpa-onnx streaming Zipformer (English, int8)",
        "tts": "VITS / VCTK (109 voices)",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=1))
    p = res["policies"]
    print(f"capture error rate {res['capture_error_rate']:.1%}, AUROC {res['auroc']}")
    print(f"  AUROC on valid-format captures only: {res['auroc_valid_format']}")
    for name, v in p.items():
        wa, ec, fa = v["wrong_action"]["value"], v["error_catch_rate"], v["false_alarm_rate"]
        print(f"  {name:<18} wrong actions {wa:6.1%}  caught {ec['value'] if ec else float('nan'):6.1%}  "
              f"false alarms {fa['value'] if fa else float('nan'):6.1%}  questions/call {v['questions_per_call']['value']:.2f}  "
              f"unresolved {v['unresolved']['value']:.1%}  "
              f"valid-looking errors caught {v['silent_catch_rate']['value'] if v['silent_catch_rate'] else float('nan'):6.1%}")


if __name__ == "__main__":
    main()
