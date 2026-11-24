"""
risk_model.py

The learned half of Ripcord's risk engine: a small, transparent logistic
regression that turns the evidence collected by entity_detector.py into the
probability that the captured number is WRONG.

Why logistic regression and not something bigger?
  * every feature's contribution to the decision can be shown to the user
    ("weakest digit heard at 41% confidence: +1.3"),
  * it runs in microseconds in pure Python (no numpy / torch at runtime),
  * it is trained and tested on separate data (see benchmark/), instead of
    having its weights tuned by hand against the demo scenarios.

The trained weights live in risk_model.json next to this file. Retrain with
`python benchmark/train_risk_model.py` — ideally on recordings from YOUR
speech recogniser, because confidence scores from different engines are not
interchangeable.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import CriticalEntity

MODEL_PATH = Path(__file__).with_name("risk_model.json")

# Order matters: it is the column order of the trained weights.
FEATURES = [
    "tok_min",       # least-confident number word
    "tok_mean",      # mean confidence of the number words
    "low_frac",      # share of number words under 70% confidence
    "context_conf",  # mean confidence of the words around the number
    "len_dev",       # how far the digit count is from 4 (0..1)
    "pairs",         # spoken as pairs: "fifteen eighty"
    "cardinal",      # spoken as "one thousand five hundred eighty"
    "teen_ten",      # contains fifteen/fifty-type words (0..1)
    "homophones",    # digits heard as "to", "for", "won"… (0..1)
    "no_carrier",    # no "order number" phrase before the digits
    "competing",     # other numbers in the same turn (0..1)
    "rate",          # digits per second (fast speech is riskier)
]


def extract_features(entity: CriticalEntity) -> dict[str, Optional[float]]:
    conf = entity.confidence
    if entity.end_of_turn_confidence is not None:
        # AssemblyAI also reports how sure it is that the turn was heard
        # correctly as a whole; blend it in like the original engine did.
        conf = 0.7 * conf + 0.3 * entity.end_of_turn_confidence
    return {
        "tok_min": entity.min_confidence,
        "tok_mean": conf,
        "low_frac": entity.low_conf_fraction,
        "context_conf": entity.context_confidence if entity.context_confidence is not None else conf,
        "len_dev": min(abs(len(entity.value) - 4), 3) / 3.0,
        "pairs": 1.0 if entity.style == "pairs" else 0.0,
        "cardinal": 1.0 if entity.style == "cardinal" else 0.0,
        "teen_ten": min(entity.teen_ten_words, 2) / 2.0,
        "homophones": min(entity.homophone_digits, 2) / 2.0,
        "no_carrier": 0.0 if entity.carrier_found else 1.0,
        "competing": min(entity.competing_spans, 2) / 2.0,
        "rate": min(max(entity.speech_rate, 0.0), 8.0) if entity.speech_rate is not None else None,
    }


def logit_of(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


@dataclass(frozen=True)
class RiskModel:
    names: tuple[str, ...]
    mean: tuple[float, ...]
    std: tuple[float, ...]
    weights: tuple[float, ...]
    bias: float
    threshold: float
    ref: tuple[float, ...]  # a typical correctly-heard capture, per feature (flags: 0)
    meta: dict
    # Probability that a capture that is NOT 4 digits long is wrong, measured on the training data.
    # The model itself is fitted on well-formed captures only (the hard case); this covers the rest.
    invalid_format_p: float = 0.97

    def _z(self, feats: dict[str, Optional[float]]) -> list[float]:
        out = []
        for n, m, s in zip(self.names, self.mean, self.std):
            x = feats.get(n)
            out.append(0.0 if x is None else (x - m) / s)
        return out

    def logit(self, feats: dict[str, Optional[float]]) -> float:
        return self.bias + sum(w * z for w, z in zip(self.weights, self._z(feats)))

    def contributions(self, feats: dict[str, Optional[float]]) -> dict[str, float]:
        """
        Each feature's push on the log-odds of 'wrong', measured against a typical
        correctly-heard capture: positive = riskier than that reference, negative =
        safer, and a flag that is switched off contributes exactly 0.
        """
        zs = self._z(feats)
        return {
            n: w * (z - (r - m) / s)
            for n, w, z, r, m, s in zip(self.names, self.weights, zs, self.ref, self.mean, self.std)
        }

    def predict(self, feats: dict[str, Optional[float]]) -> float:
        return sigmoid(self.logit(feats))


_cached: Optional[RiskModel] = None
_cached_mtime: float = -1.0


def load_model(path: Path = MODEL_PATH) -> Optional[RiskModel]:
    """Load (and cache) the trained model. Returns None when no model file exists."""
    global _cached, _cached_mtime
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    if _cached is not None and mtime == _cached_mtime:
        return _cached
    raw = json.loads(path.read_text(encoding="utf-8"))
    _cached = RiskModel(
        names=tuple(raw["features"]),
        mean=tuple(raw["mean"]),
        std=tuple(max(s, 1e-6) for s in raw["std"]),
        weights=tuple(raw["weights"]),
        bias=float(raw["bias"]),
        threshold=float(raw["threshold"]),
        ref=tuple(raw.get("ref", raw["mean"])),
        meta=raw.get("meta", {}),
        invalid_format_p=float(raw.get("invalid_format_p", 0.97)),
    )
    _cached_mtime = mtime
    return _cached
