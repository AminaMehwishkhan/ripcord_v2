"""
build_dataset.py — generate the Ripcord benchmark.

For every item: pick a voice, a 4-digit order number, a way of saying it and a
carrier sentence; synthesise it; degrade it (noise / babble / phone band /
reverb / fast speech); run a REAL streaming recogniser; store the transcript
with real per-word confidences and the ground-truth number.

For the clarification loop we also store what the caller's reply to a
question would sound like, run through the same recogniser and the same
acoustic conditions:
    reply_yes  "yes that's right"
    reply_no   "no it's <true digits>"   (only when the first pass deviated)

Splits are by speaker AND by number, so nothing in `test` shares a voice or an
order number with `train`/`val`.

    python build_dataset.py --n 1200 --shard 0 --nshards 2
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

import spoken
from augment import CONDITIONS, apply_condition
from engines import Asr, Tts

GENERIC = [
    "please check the status of my package", "i would like to change my delivery address",
    "can you tell me when it will arrive", "thanks for your help today",
    "i was charged twice for the same item", "could you send me a confirmation email",
    "i need to speak to someone about a refund", "the tracking page is not loading for me",
    "yes i am still on the line", "it was supposed to come on tuesday",
    "i ordered a blue jacket last week", "no problem i can wait a moment",
]


def norm_words(s: str) -> list[str]:
    return [w for w in s.lower().replace("'", "").replace(",", " ").split() if w]


def make_plan(n: int, seed: int, n_speakers: int) -> list[dict]:
    rng = random.Random(seed)
    speakers = list(range(n_speakers))
    rng.shuffle(speakers)
    n_val, n_test = 14, 30
    spk = {"val": speakers[:n_val], "test": speakers[n_val:n_val + n_test],
           "train": speakers[n_val + n_test:]}
    counts = {"train": int(n * 0.5), "val": int(n * 0.17)}
    counts["test"] = n - counts["train"] - counts["val"]
    used: set[str] = set()
    plan = []
    names = [c for c, _ in CONDITIONS]
    probs = np.array([w for _, w in CONDITIONS], dtype=float)
    probs /= probs.sum()
    nprng = np.random.default_rng(seed)
    for split, cnt in counts.items():
        for _ in range(cnt):
            while True:
                v = rng.randint(1000, 9999) if rng.random() > 0.05 else rng.randint(100, 999)
                value = f"{v:04d}"
                if value not in used:
                    used.add(value)
                    break
            style = spoken.pick_style(rng) if value[0] != "0" else "digits"
            template = rng.choice(spoken.TEMPLATES)
            plan.append({
                "split": split, "speaker": rng.choice(spk[split]), "true_value": value,
                "style": style, "template": template,
                "speed": round(float(np.clip(rng.gauss(1.0, 0.13), 0.78, 1.4)), 2),
                "condition": str(nprng.choice(names, p=probs)),
                "yes_variant": rng.randrange(len(spoken.YES_REPLIES)),
                "no_variant": rng.randrange(len(spoken.NO_TEMPLATES)),
                "seed": rng.randrange(1 << 30),
            })
    rng.shuffle(plan)
    for i, p in enumerate(plan):
        p["id"] = f"b{i:05d}"
    return plan


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or Path(__file__).parent / "data" / f"shard{args.shard}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    tts, asr = Tts(1), Asr(1)
    plan = make_plan(args.n, args.seed, tts.num_speakers)
    done = set()
    if out.exists():
        done = {json.loads(l)["id"] for l in out.read_text().splitlines() if l.strip()}

    boot = np.random.default_rng(args.seed + args.shard)
    pool = [tts.say(t, int(boot.integers(0, tts.num_speakers))) for t in GENERIC]
    yes_cache: dict[tuple[int, int], np.ndarray] = {}

    with open(out, "a", encoding="utf-8") as f:
        for idx, item in enumerate(plan):
            if idx % args.nshards != args.shard or item["id"] in done:
                continue
            rng = random.Random(item["seed"])
            nprng = np.random.default_rng(item["seed"])
            value = item["true_value"]
            said = spoken.speak(value, item["style"], rng)
            text = item["template"].format(n=said)

            clean = tts.say(text, item["speaker"], item["speed"])
            audio, info = apply_condition(clean, item["condition"], nprng, pool)
            main_asr = asr.transcribe(audio)

            key = (item["speaker"], item["yes_variant"])
            if key not in yes_cache:
                yes_cache[key] = tts.say(spoken.YES_REPLIES[item["yes_variant"]], item["speaker"], 1.0)
            yes_audio, _ = apply_condition(yes_cache[key], item["condition"], nprng, pool)
            yes_asr = asr.transcribe(yes_audio)

            no_asr = None
            if norm_words(main_asr["transcript"]) != norm_words(text):
                digits = spoken.speak(value, "digits" if rng.random() < 0.85 else item["style"], rng)
                no_text = spoken.NO_TEMPLATES[item["no_variant"]].format(n=digits)
                no_clean = tts.say(no_text, item["speaker"], 1.0)
                no_audio, _ = apply_condition(no_clean, item["condition"], nprng, pool)
                no_asr = asr.transcribe(no_audio)
                no_asr["spoken"] = no_text

            rec = {**item, **{k: v for k, v in info.items() if k != "condition"},
                   "spoken_text": text, "asr": main_asr,
                   "reply_yes": {**yes_asr, "spoken": spoken.YES_REPLIES[item["yes_variant"]]},
                   "reply_no": no_asr}
            f.write(json.dumps(rec) + "\n")
            f.flush()
            if (idx // args.nshards) % 25 == 0:
                print(f"[shard {args.shard}] item {idx}/{len(plan)}  {item['condition']:7s} "
                      f"{text!r} -> {main_asr['transcript']!r}", flush=True)


if __name__ == "__main__":
    main()
