"""
engines.py — thin wrappers around two open-source sherpa-onnx models used to
build the benchmark (dev-time only; the Ripcord runtime does not need them):

  * TTS:  VITS / VCTK, 109 voices        -> speech for each test utterance
  * ASR:  streaming Zipformer transducer -> transcript + REAL per-word confidence

Per-word confidence is the mean probability of the word-piece tokens the
decoder actually emitted (exp of the log-prob sherpa-onnx returns in
`ys_probs`). It is a genuine model posterior, not an authored number.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import sherpa_onnx

from augment import SR, resample_to_16k

MODELS = Path(os.environ.get("RIPCORD_MODELS", "/home/claude/models"))


class Tts:
    def __init__(self, num_threads: int = 1):
        d = MODELS / "vits-vctk"
        cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(d / "vits-vctk.onnx"), lexicon=str(d / "lexicon.txt"),
                tokens=str(d / "tokens.txt")),
            num_threads=num_threads, provider="cpu"))
        self.tts = sherpa_onnx.OfflineTts(cfg)
        self.num_speakers = self.tts.num_speakers

    def say(self, text: str, sid: int, speed: float = 1.0) -> np.ndarray:
        a = self.tts.generate(text, sid=sid, speed=speed)
        x = resample_to_16k(np.asarray(a.samples, dtype=np.float32), a.sample_rate)
        # Real recordings have a little silence either side; TTS output starts and
        # ends abruptly, which unfairly hurts a streaming recogniser.
        return np.concatenate([np.zeros(int(0.3 * SR), np.float32), x, np.zeros(int(0.5 * SR), np.float32)])


class Asr:
    def __init__(self, num_threads: int = 1):
        d = MODELS / "sherpa-onnx-streaming-zipformer-en-2023-06-26"
        tag = "epoch-99-avg-1-chunk-16-left-128"
        self.rec = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(d / "tokens.txt"),
            encoder=str(d / f"encoder-{tag}.int8.onnx"),
            decoder=str(d / f"decoder-{tag}.onnx"),
            joiner=str(d / f"joiner-{tag}.int8.onnx"),
            num_threads=num_threads, sample_rate=SR, feature_dim=80,
            decoding_method="greedy_search")

    def transcribe(self, x: np.ndarray) -> dict:
        s = self.rec.create_stream()
        step = SR // 10  # 100 ms chunks, like a live stream
        for i in range(0, len(x), step):
            s.accept_waveform(SR, x[i:i + step])
            while self.rec.is_ready(s):
                self.rec.decode_stream(s)
        # A full second of trailing silence lets the streaming decoder flush its last
        # word-piece; with less, the final word is cut short ("seve" for "seven").
        s.accept_waveform(SR, np.zeros(SR, dtype=np.float32))
        s.input_finished()
        while self.rec.is_ready(s):
            self.rec.decode_stream(s)
        r = self.rec.get_result_all(s)
        return words_from_result(list(r.tokens), list(r.timestamps), list(r.ys_probs), len(x) / SR)


def words_from_result(tokens: list[str], stamps: list[float], logps: list[float], dur: float) -> dict:
    """Group BPE pieces into words (a leading space starts a new word)."""
    groups: list[dict] = []
    for tok, t, lp in zip(tokens, stamps, logps):
        if tok.startswith(" ") or not groups:
            groups.append({"text": "", "probs": [], "start": t, "end": t})
        g = groups[-1]
        g["text"] += tok.strip()
        g["probs"].append(math.exp(lp))
        g["end"] = t
    words = []
    for i, g in enumerate(groups):
        end = groups[i + 1]["start"] if i + 1 < len(groups) else min(dur, g["end"] + 0.3)
        words.append({
            "text": g["text"].lower(),
            "confidence": round(sum(g["probs"]) / len(g["probs"]), 4),
            "start": int(g["start"] * 1000),
            "end": int(max(end, g["start"] + 0.08) * 1000),
            "word_is_final": True,
        })
    return {"transcript": " ".join(w["text"] for w in words), "words": words}
