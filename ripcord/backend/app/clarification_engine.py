"""
clarification_engine.py

Turns a risky CriticalEntity into ONE targeted spoken question. Templates are
deterministic (no API call, no latency, always available). An optional LLM
rephrasing hook exists, but the LLM is never allowed to change the safety
decision — it can only reword a question the risk engine already decided to ask.
"""
from __future__ import annotations

from typing import Optional

from .models import ClarificationQuestion, CriticalEntity, RiskAssessment

DIGIT_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}
ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth"]


def spell_digits(value: str) -> str:
    return "-".join(DIGIT_WORDS.get(ch, ch) for ch in value)


def _label(entity: CriticalEntity) -> str:
    return {"order_id": "order number"}.get(entity.type, entity.type.replace("_", " "))


def build_clarification(
    entity: CriticalEntity,
    risk: RiskAssessment,
    alternative_value: Optional[str] = None,
    read_back: bool = False,
) -> ClarificationQuestion:
    spoken = spell_digits(entity.value)
    weak = list(risk.weak_positions)

    # Wrong number of digits: confirming a value we already know is invalid
    # would be silly — ask for it again, one digit at a time.
    if not entity.format_valid:
        n = len(entity.value)
        return ClarificationQuestion(
            question=(
                f"I only caught {n} digit{'s' if n != 1 else ''} ({spoken}) — your {_label(entity)} "
                "should have 4. Could you say it one digit at a time?"
            ),
            kind="repeat_digit_by_digit",
            candidate_value=entity.value,
            uncertain_positions=weak,
        )

    # Severely degraded capture.
    if entity.confidence < 0.35:
        return ClarificationQuestion(
            question=(
                f"I want to make sure I get your {_label(entity)} right — "
                "could you say it one digit at a time?"
            ),
            kind="repeat_digit_by_digit",
            candidate_value=entity.value,
            uncertain_positions=weak,
        )

    # The caller restated a number and we are still not sure: read it back.
    if read_back:
        return ClarificationQuestion(
            question=f"Thanks — I heard {spoken}. Is that right?",
            kind="read_back",
            candidate_value=entity.value,
            uncertain_positions=weak,
        )

    # Two plausible values on record: let the caller pick.
    if alternative_value and alternative_value != entity.value:
        return ClarificationQuestion(
            question=f"Did you say {spell_digits(alternative_value)} or {spoken}?",
            kind="disambiguate",
            candidate_value=entity.value,
            alternative_value=alternative_value,
            uncertain_positions=weak,
        )

    question = f"Just to confirm, was your {_label(entity)} {spoken}?"
    if len(weak) == 1 and weak[0] < len(ORDINALS):
        question += f" I'm least sure about the {ORDINALS[weak[0]]} digit."
    return ClarificationQuestion(
        question=question, kind="confirm", candidate_value=entity.value, uncertain_positions=weak,
    )


def rephrase_with_llm(question: ClarificationQuestion) -> ClarificationQuestion:
    """
    Optional hook: an LLM could make `question.question` sound more natural.
    A no-op by default. Never use it to decide WHETHER to clarify — only to
    reword a question the deterministic engine already produced.
    """
    return question
