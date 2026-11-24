"""
risk_engine.py

Decides whether a captured critical entity is safe to act on.

Two layers, both deterministic and explainable (no LLM makes this call):

 1. EVIDENCE MODEL — a small logistic regression (risk_model.py) over how the
    number was heard: weakest-digit confidence, mean confidence, spoken style
    ("fifteen eighty" is easier to mishear than "one five eight zero"),
    homophone digits, fast speech, digit count… Its output is the estimated
    probability that the captured number is wrong.

 2. CONVERSATION RULES — direct evidence from the caller's own words:
    contradicting an earlier value, repeating it unprompted, or saying "no,
    that's wrong". These force a clarification on their own, because they are
    not a statistical guess — the caller just told us something is off.

If no trained model file is present the engine falls back to the original
hand-weighted rule set (`assess_risk_rules`), so the project still runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .config import settings
from .models import CriticalEntity, RiskAssessment, RiskLevel
from .risk_model import RiskModel, extract_features, load_model, logit_of, sigmoid

# Extra log-odds for conversation evidence (they also force clarification).
BOOST_CONTRADICTION = 2.4
BOOST_CORRECTION = 2.0
BOOST_REPETITION = 1.4

HIGH_RISK_SCORE = 0.6
WEAK_DIGIT_CONFIDENCE = 0.75


@dataclass
class RiskContext:
    """Conversational history the orchestrator tracks per active entity."""

    prior_values: list[str] = field(default_factory=list)
    user_repeated_entity: bool = False
    correction_language_seen: bool = False
    # True while the caller is answering one of our questions: a restated
    # number then is expected, not a "contradiction" worth a second alarm.
    in_clarification: bool = False


# ---------------------------------------------------------------------------
# helpers shared by both engines
# ---------------------------------------------------------------------------

def _weak_positions(entity: CriticalEntity, force: bool) -> list[int]:
    dc = entity.digit_confidences
    if not dc:
        return []
    ranked = sorted(range(len(dc)), key=lambda i: dc[i])
    weak = [i for i in ranked if dc[i] < WEAK_DIGIT_CONFIDENCE][:2]
    if not weak and force:
        weak = ranked[:1]
    return sorted(weak)


def _distinct_prior(entity: CriticalEntity, ctx: RiskContext) -> bool:
    prior = {v for v in ctx.prior_values if v and v != entity.value}
    return bool(prior)


def _level(score: float, threshold: float) -> RiskLevel:
    if score >= HIGH_RISK_SCORE:
        return RiskLevel.HIGH
    if score >= threshold:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _reasons(entity: CriticalEntity, contrib: dict[str, float], ctx: RiskContext) -> list[str]:
    n = len(entity.value)
    text = {
        "tok_min": f"weakest number word heard at only {entity.min_confidence:.0%} confidence",
        "tok_mean": f"number heard at {entity.confidence:.0%} average confidence",
        "low_frac": f"{round(entity.low_conf_fraction * len(entity.raw_words))} of "
                    f"{len(entity.raw_words)} number words under 70% confidence",
        "context_conf": "the words around the number were also unclear",
        "len_dev": f"heard {n} digits, expected 4",
        "pairs": "said in pairs (\"fifteen eighty\") — easy to mishear",
        "cardinal": "said as one big number — easy to mishear",
        "teen_ten": "contains a fifteen/fifty-type word, a classic confusion",
        "homophones": "a digit was heard as an everyday word (\"to\", \"for\", \"won\")",
        "no_carrier": "no \"order number\" phrase before the digits",
        "competing": "more than one number in the same turn",
        "rate": "spoken very fast",
    }
    ranked = sorted(((v, k) for k, v in contrib.items() if v > 0.15), reverse=True)
    out = [text[k] for _, k in ranked if k in text]
    if ctx.correction_language_seen and not ctx.in_clarification:
        out.insert(0, "caller used correction language (\"no\", \"I said…\")")
    if _distinct_prior(entity, ctx) and not ctx.in_clarification:
        out.insert(0, "caller gave a different number earlier")
    if ctx.user_repeated_entity and not ctx.in_clarification:
        out.insert(0, "caller repeated the number unprompted")
    return out


_SIGNAL_OF = {
    "tok_min": "low_entity_confidence", "tok_mean": "low_entity_confidence",
    "low_frac": "low_entity_confidence", "context_conf": "noisy_context",
    "len_dev": "format_mismatch", "pairs": "ambiguous_wording", "cardinal": "ambiguous_wording",
    "teen_ten": "ambiguous_wording", "homophones": "homophone_digits",
    "no_carrier": "no_carrier_phrase", "competing": "competing_numbers", "rate": "fast_speech",
}


# ---------------------------------------------------------------------------
# learned engine
# ---------------------------------------------------------------------------

def assess_risk_learned(
    entity: CriticalEntity,
    ctx: RiskContext,
    model: RiskModel,
    threshold: Optional[float] = None,
) -> RiskAssessment:
    if threshold is None:
        threshold = settings.risk_clarify_threshold_override
    if threshold is None:
        threshold = model.threshold

    feats = extract_features(entity)
    contrib = model.contributions(feats)
    logit = model.logit(feats)
    if not entity.format_valid:
        # The model is fitted on well-formed captures. A wrong digit count is almost always a
        # mishearing, so lift the score to the rate measured on the training data.
        floor = logit_of(model.invalid_format_p)
        if logit < floor:
            contrib["len_dev"] = contrib.get("len_dev", 0.0) + (floor - logit)
            logit = floor

    breakdown = {k: round(v, 4) for k, v in contrib.items()}
    signals: list[str] = []
    for k, v in contrib.items():
        if v > 0.15 and _SIGNAL_OF[k] not in signals:
            signals.append(_SIGNAL_OF[k])

    hard = False
    if not ctx.in_clarification:
        if _distinct_prior(entity, ctx):
            logit += BOOST_CONTRADICTION
            breakdown["contradiction"] = BOOST_CONTRADICTION
            signals.append("conflicting_captures")
            hard = True
        if ctx.correction_language_seen:
            logit += BOOST_CORRECTION
            breakdown["correction_language"] = BOOST_CORRECTION
            signals.append("user_correction_language")
            hard = True
        if ctx.user_repeated_entity:
            logit += BOOST_REPETITION
            breakdown["repetition"] = BOOST_REPETITION
            signals.append("entity_repetition")
            hard = True

    score = round(sigmoid(logit), 4)
    should = hard or score >= threshold
    return RiskAssessment(
        risk_score=score,
        risk_level=_level(score, threshold),
        signals=signals,
        should_clarify=should,
        breakdown=breakdown,
        reasons=_reasons(entity, contrib, ctx),
        weak_positions=_weak_positions(entity, force=should),
        threshold=round(threshold, 4),
        engine="learned-v2",
    )


# ---------------------------------------------------------------------------
# original hand-weighted engine (fallback + comparison baseline)
# ---------------------------------------------------------------------------

W_CONFIDENCE, W_FORMAT, W_REPETITION, W_CONTRADICTION, W_CORRECTION = 0.50, 0.20, 0.10, 0.10, 0.10
CONFIDENCE_FLOOR, CONFIDENCE_CEILING = 0.85, 0.55
RULES_THRESHOLD = 0.35


def _rules_confidence_risk(c: float) -> float:
    if c >= CONFIDENCE_FLOOR:
        return 0.0
    if c <= CONFIDENCE_CEILING:
        return 1.0
    return round((CONFIDENCE_FLOOR - c) / (CONFIDENCE_FLOOR - CONFIDENCE_CEILING), 4)


def assess_risk_rules(
    entity: CriticalEntity, ctx: Optional[RiskContext] = None, threshold: Optional[float] = None
) -> RiskAssessment:
    """The v1 engine: five hand-weighted signals summed into a 0-1 score."""
    ctx = ctx or RiskContext()
    threshold = RULES_THRESHOLD if threshold is None else threshold
    conf = entity.confidence
    if entity.end_of_turn_confidence is not None:
        conf = 0.7 * conf + 0.3 * entity.end_of_turn_confidence
    fmt = 0.0 if entity.format_valid else (1.0 if len(entity.value) < 2 else 0.7)
    breakdown = {
        "confidence_risk": round(_rules_confidence_risk(conf) * W_CONFIDENCE, 4),
        "format_risk": round(fmt * W_FORMAT, 4),
        "repetition_risk": round((1.0 if ctx.user_repeated_entity else 0.0) * W_REPETITION, 4),
        "contradiction_risk": round((1.0 if _distinct_prior(entity, ctx) else 0.0) * W_CONTRADICTION, 4),
        "correction_risk": round((1.0 if ctx.correction_language_seen else 0.0) * W_CORRECTION, 4),
    }
    score = round(min(1.0, sum(breakdown.values())), 4)
    names = {"confidence_risk": "low_entity_confidence", "format_risk": "format_mismatch",
             "repetition_risk": "entity_repetition", "contradiction_risk": "conflicting_captures",
             "correction_risk": "user_correction_language"}
    signals = [names[k] for k, v in breakdown.items() if v > 0]
    hard = any(breakdown[k] > 0 for k in ("repetition_risk", "contradiction_risk", "correction_risk"))
    should = hard or score >= threshold
    return RiskAssessment(
        risk_score=score, risk_level=_level(score, threshold), signals=signals,
        should_clarify=should, breakdown=breakdown, reasons=[],
        weak_positions=_weak_positions(entity, force=should), threshold=threshold, engine="rules-v1",
    )


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------

def assess_risk(
    entity: CriticalEntity,
    ctx: Optional[RiskContext] = None,
    threshold: Optional[float] = None,
) -> RiskAssessment:
    """Score one captured entity with the trained model (rules if none is installed)."""
    ctx = ctx or RiskContext()
    model = load_model()
    if model is None:
        return assess_risk_rules(entity, ctx, threshold)
    return assess_risk_learned(entity, ctx, model, threshold)
