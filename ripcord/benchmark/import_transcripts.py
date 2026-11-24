"""
import_transcripts.py — turn transcripts from YOUR recogniser into benchmark lines.

Input: a CSV manifest and a folder of transcript JSON files. Each JSON file looks like an
AssemblyAI transcript (any recogniser that gives per-word confidence can be converted to this):

    {"text": "my order number is one five eight zero",
     "words": [{"text": "my", "start": 320, "end": 480, "confidence": 0.98}, ...]}

Manifest columns:  id, split, speaker, true_value, condition, main, yes, no
(`main` is required; `yes` and `no` are the caller's replies to a question and may be empty;
`split` is train / val / test and must keep speakers and numbers apart.)

    python import_transcripts.py manifest.csv transcripts_dir [--out data/mine.jsonl]

Tested against fixtures only, not against the live AssemblyAI API.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def convert(raw: dict) -> dict:
    words = []
    for w in raw.get("words", []):
        words.append({
            "text": str(w["text"]).lower().strip(),
            "confidence": float(w["confidence"]),
            "start": int(w.get("start", 0)),
            "end": int(w.get("end", 0)),
            "word_is_final": True,
        })
    transcript = raw.get("text") or " ".join(w["text"] for w in words)
    return {"transcript": transcript.lower(), "words": words}


def build_item(row: dict, folder: Path) -> dict:
    def load(key: str):
        name = (row.get(key) or "").strip()
        return convert(json.loads((folder / name).read_text(encoding="utf-8"))) if name else None

    true_value = row["true_value"].strip()
    if not (true_value.isdigit() and len(true_value) in (3, 4)):
        raise ValueError(f"{row['id']}: true_value must be digits, got {true_value!r}")
    if row["split"] not in ("train", "val", "test"):
        raise ValueError(f"{row['id']}: split must be train, val or test")
    main = load("main")
    if main is None:
        raise ValueError(f"{row['id']}: a main transcript is required")
    return {
        "id": row["id"], "split": row["split"], "speaker": row["speaker"], "true_value": true_value,
        "condition": row.get("condition") or "clean", "asr": main,
        "reply_yes": load("yes"), "reply_no": load("no"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data" / "mine.jsonl")
    args = ap.parse_args()
    with open(args.manifest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    items = [build_item(r, args.folder) for r in rows]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")
    spk = {s: {i["speaker"] for i in items if i["split"] == s} for s in ("train", "val", "test")}
    clash = (spk["train"] & spk["test"]) | (spk["train"] & spk["val"]) | (spk["val"] & spk["test"])
    if clash:
        print(f"WARNING: speakers appear in more than one split: {sorted(clash)}", file=sys.stderr)
    print(f"wrote {len(items)} items -> {args.out}")


if __name__ == "__main__":
    main()
