import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Word  # noqa: E402
from app.risk_model import FEATURES, RiskModel  # noqa: E402


def words(text: str, conf: float = 0.95, **overrides: float) -> list[Word]:
    """Words for `text`, all at `conf`, with per-word overrides keyed by the lower-case word."""
    out = []
    for tok in text.split():
        key = tok.lower().strip(".,?!")
        out.append(Word(text=tok, confidence=overrides.get(key, conf)))
    return out


def turn(text: str, conf: float = 0.95, order: int = 0, **overrides: float) -> dict:
    """A final AssemblyAI-shaped Turn message."""
    return {
        "transcript": text, "end_of_turn": True, "turn_order": order,
        "words": [{"text": w.text, "confidence": w.confidence} for w in words(text, conf, **overrides)],
    }


def toy_model(threshold=0.4) -> RiskModel:
    """A tiny hand-set model so these tests don't depend on a training run."""
    w = {n: 0.0 for n in FEATURES}
    w["tok_min"] = -5.0       # lower weakest-digit confidence -> riskier
    w["pairs"] = 1.0          # "fifteen eighty" style -> riskier
    zeros = tuple(0.0 for _ in FEATURES)
    ones = tuple(1.0 for _ in FEATURES)
    ref = tuple(0.95 if n == "tok_min" else 0.0 for n in FEATURES)
    return RiskModel(names=tuple(FEATURES), mean=zeros, std=ones, weights=tuple(w[n] for n in FEATURES),
                     bias=3.5, threshold=threshold, ref=ref, meta={})
