"""
session.py

SessionOrchestrator runs ONE conversation (Mode A: Ripcord off, Mode B:
Ripcord on) through the same pipeline whether the Turn messages come from the
real AssemblyAI client, a recorded replay, or the benchmark. The before/after
demo therefore shows the real risk engine running, not two hard-coded UI states.

State machine for one entity
----------------------------
    new turn -> detect_critical_entity()
        none                -> nothing to do yet
        entity, Ripcord OFF -> accept blindly (Mode A)
        entity, Ripcord ON  -> risk engine
              low risk      -> VERIFIED -> workflow_guard -> action
              high risk     -> PAUSE -> ask ONE targeted question
                    caller says yes / same number -> VERIFIED -> action
                    caller says no / unclear      -> ask again, digit by digit
                    caller restates a NEW number  -> score it like any capture:
                         low risk  -> VERIFIED -> action
                         high risk -> read it back ("I heard 1-5-8-0, right?")
                    after MAX_ATTEMPTS failed rounds -> ESCALATE to a human

If the caller corrects a number that was already accepted ("no, I said 9021"), the old one is
un-verified, the action already taken is flagged, and the new number is checked with the
contradiction on record — so even a confident-but-wrong first capture gets a second chance.

The restated number is deliberately NOT trusted just because the caller said
it in answer to a question — it is a fresh capture from the same noisy
recogniser, so it gets the same scrutiny.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable, Optional

from . import risk_engine
from .clarification_engine import build_clarification
from .entity_detector import classify_reply, contains_correction_language, detect_critical_entity
from .models import (
    ClarificationQuestion,
    ConversationTurn,
    CriticalEntity,
    EntityStatus,
    ResolvedEntry,
    RiskAssessment,
    SessionState,
    TimelineEvent,
    Word,
)
from .risk_engine import RiskContext
from .workflow_guard import execute_order_lookup

MAX_ATTEMPTS = 3  # clarification rounds per entity before handing off to a human

RiskFn = Callable[[CriticalEntity, RiskContext], RiskAssessment]


def naive_agent_accept(entity: CriticalEntity) -> str:
    """
    Mode A behaviour: a normal voice agent with no reliability layer. It accepts
    whatever was captured and proceeds. This intentionally does NOT go through
    workflow_guard — that guard is what Ripcord adds.
    """
    return f"Looking up order {entity.value}"


class SessionOrchestrator:
    def __init__(
        self,
        session_id: Optional[str] = None,
        ripcord_enabled: bool = True,
        mock_mode: bool = True,
        risk_fn: Optional[RiskFn] = None,
    ):
        self.state = SessionState(
            session_id=session_id or str(uuid.uuid4()),
            ripcord_enabled=ripcord_enabled,
            mock_mode=mock_mode,
            connection_status="live" if mock_mode else "idle",
        )
        self._start_ts = time.monotonic()
        self._ctx = RiskContext()
        self._last_value: Optional[str] = None
        self._last_verified: Optional[str] = None  # the number we most recently acted on
        self._risk_fn: RiskFn = risk_fn or (lambda e, c: risk_engine.assess_risk(e, c))
        self.questions_asked = 0

    # -- helpers -----------------------------------------------------
    def _ts_ms(self) -> int:
        return int((time.monotonic() - self._start_ts) * 1000)

    def _log(self, label: str, kind: str, detail: Optional[str] = None) -> None:
        self.state.timeline.append(TimelineEvent(ts_ms=self._ts_ms(), label=label, detail=detail, kind=kind))

    def _say(self, role: str, text: str, words: Optional[list[Word]] = None, note: Optional[str] = None) -> None:
        self.state.conversation.append(
            ConversationTurn(role=role, text=text, words=words or [], ts_ms=self._ts_ms(), note=note)  # type: ignore[arg-type]
        )

    def set_ripcord_enabled(self, enabled: bool) -> None:
        self.state.ripcord_enabled = enabled

    # -- main entry point ---------------------------------------------
    def process_turn(self, turn: dict) -> SessionState:
        started = time.monotonic()
        transcript: str = turn.get("transcript", "")
        end_of_turn: bool = turn.get("end_of_turn", True)

        if not end_of_turn:
            self.state.live_partial = transcript
            return self.state

        self.state.live_partial = ""
        self.state.transcript = (self.state.transcript + " " + transcript).strip()
        words = [Word(**w) for w in turn.get("words", [])]
        self._log("Speech captured", "speech", transcript)
        self._say("caller", transcript, words)

        if self.state.escalated:
            return self.state

        if self.state.clarification is not None:
            self._handle_clarification_response(transcript, words, turn)
            self._record_latency(started)
            return self.state

        entity = detect_critical_entity(
            transcript, words, turn_order=turn.get("turn_order", 0),
            end_of_turn_confidence=turn.get("end_of_turn_confidence"),
        )
        if entity is None:
            return self.state

        if (self.state.ripcord_enabled and self._last_verified is not None
                and entity.value != self._last_verified and contains_correction_language(transcript)):
            self._supersede_verified(entity)
        self._update_context(entity, transcript)
        self._log(f"Critical entity captured: {entity.value}", "capture", f"confidence={entity.confidence:.2f}")

        if not self.state.ripcord_enabled:
            self._run_mode_a(entity)
        else:
            self._run_mode_b(entity)
        self._record_latency(started)
        return self.state

    def _record_latency(self, started_at: float) -> None:
        self.state.last_decision_latency_ms = max(0, int((time.monotonic() - started_at) * 1000))

    # -- internals ------------------------------------------------------
    def _update_context(self, entity: CriticalEntity, transcript: str) -> None:
        if entity.value == self._last_value:
            self._ctx.user_repeated_entity = True
        if self._last_value and self._last_value != entity.value:
            self._ctx.prior_values.append(self._last_value)
        if contains_correction_language(transcript):
            self._ctx.correction_language_seen = True
        self._last_value = entity.value

    def _supersede_verified(self, new: CriticalEntity) -> None:
        """
        The caller corrects a number we already accepted and acted on ("no, I said 9021").
        A confident-but-wrong capture can slip through the first check; the caller's own
        correction is the second chance to catch it. The old number stops counting as
        verified, the earlier action is flagged, and the new one is checked with the
        contradiction already on the record (which forces a question).
        """
        old = self._last_verified
        assert old is not None
        self._log(f"Caller corrected a number we had already accepted: {old} → {new.value}", "system",
                  "the action taken on the earlier number needs to be reviewed or rolled back")
        if self.state.history and self.state.history[-1].value == old:
            self.state.history[-1].status = EntityStatus.INVALIDATED
        self.state.verified_value = None
        self.state.action_result = None
        self._ctx = RiskContext(prior_values=[old], correction_language_seen=True)
        self._last_value = old
        self._last_verified = None

    def _run_mode_a(self, entity: CriticalEntity) -> None:
        entity.status = EntityStatus.VERIFIED  # Mode A trusts the raw capture
        self.state.entity = entity
        self.state.risk = None
        self.state.verified_value = entity.value
        result = naive_agent_accept(entity)
        self.state.action_result = result
        self._log("Workflow proceeded without verification (Ripcord OFF)", "action", result)
        self._say("agent", result, note="no verification")
        self._record_history(entity, required_clarification=False)

    @staticmethod
    def _enforce_format(entity: CriticalEntity, assessment: RiskAssessment) -> RiskAssessment:
        """
        Invariant that does not depend on whichever scoring policy is plugged in: a number with
        the wrong digit count is never acted on. If a policy let one through, turn it into a question.
        """
        if assessment.should_clarify or entity.format_valid:
            return assessment
        return assessment.model_copy(update={
            "should_clarify": True,
            "signals": [*assessment.signals, "format_mismatch"],
            "reasons": [f"heard {len(entity.value)} digits, expected 4", *assessment.reasons],
        })

    def _run_mode_b(self, entity: CriticalEntity) -> None:
        assessment = self._enforce_format(entity, self._risk_fn(entity, self._ctx))
        self.state.risk = assessment
        self._log(
            f"Risk of a wrong number: {int(assessment.risk_score * 100)}% ({assessment.risk_level.value})",
            "risk",
            "; ".join(assessment.reasons) if assessment.reasons else "no risk signals",
        )
        if not assessment.should_clarify:
            self._verify_and_act(entity, assessment, required_clarification=False)
            return
        self._pause_and_ask(entity, assessment)

    def _pause_and_ask(self, entity: CriticalEntity, assessment: RiskAssessment, read_back: bool = False) -> None:
        if self.state.attempts >= MAX_ATTEMPTS:
            self._escalate(entity)
            return
        entity.status = EntityStatus.UNCERTAIN
        self.state.entity = entity
        self.state.workflow_paused = True
        self.state.action_result = None
        self._log("Workflow paused — possible silent failure detected", "pause")

        alt = self._ctx.prior_values[-1] if self._ctx.prior_values and not read_back else None
        question = build_clarification(entity, assessment, alternative_value=alt, read_back=read_back)
        entity.status = EntityStatus.CLARIFYING
        self.state.clarification = question
        self.state.attempts += 1
        self.questions_asked += 1
        self._log("Clarification requested", "clarify", question.question)
        self._say("agent", question.question, note=f"attempt {self.state.attempts}/{MAX_ATTEMPTS}")

    def _ask_again(self, text: str, kind: str = "repeat_digit_by_digit") -> None:
        if self.state.attempts >= MAX_ATTEMPTS:
            self._escalate(self.state.entity)
            return
        self.state.clarification = ClarificationQuestion(question=text, kind=kind)  # type: ignore[arg-type]
        self.state.attempts += 1
        self.questions_asked += 1
        self._log("Clarification requested", "clarify", text)
        self._say("agent", text, note=f"attempt {self.state.attempts}/{MAX_ATTEMPTS}")

    def _verify_and_act(
        self, entity: CriticalEntity, assessment: Optional[RiskAssessment], required_clarification: bool
    ) -> None:
        entity.status = EntityStatus.VERIFIED
        self.state.entity = entity
        self.state.verified_value = entity.value
        self.state.workflow_paused = False
        self.state.clarification = None
        self.state.attempts = 0
        self._last_verified = entity.value
        if required_clarification:
            self._log(f"Entity verified: {entity.value}", "verify")
        result = execute_order_lookup(entity)  # raises unless status == VERIFIED
        self.state.action_result = result
        self._log(
            "Workflow resumed" if required_clarification else "Workflow resumed — entity trusted, no clarification needed",
            "resume", result,
        )
        self._say("agent", result, note="verified")
        self._record_history(entity, required_clarification, assessment.risk_score if assessment else None)
        # The next number in this call is a new entity: start from a clean slate.
        self._ctx = RiskContext()
        self._last_value = None

    def _escalate(self, entity: Optional[CriticalEntity]) -> None:
        if entity is not None:
            entity.status = EntityStatus.INVALIDATED
        self.state.escalated = True
        self.state.workflow_paused = True
        self.state.clarification = None
        self.state.action_result = None
        msg = ("I'm still not certain I have that right, so I won't guess. "
               "Let me hand you to a colleague — or you can type the number on your keypad.")
        self._log("Escalated to a human — number could not be verified", "system")
        self._say("agent", msg, note="escalated")

    def _handle_clarification_response(self, transcript: str, words: list[Word], turn: dict) -> None:
        clar = self.state.clarification
        entity = self.state.entity
        assert clar is not None

        restated = detect_critical_entity(transcript, words, turn_order=turn.get("turn_order", 0))
        reply = classify_reply(transcript, words)
        candidate = clar.candidate_value

        # 1. The caller gave a different number: a NEW capture. Score it again.
        if restated is not None and restated.value != candidate:
            self._consider_restated(restated)
            return

        # 2. Plain confirmation (or the same number repeated, without a "no"). A number with the
        #    wrong digit count can never be confirmed: "yes" or saying it again does not make 1-7 an
        #    order number. It needs a fresh, complete capture.
        if entity is not None and entity.format_valid and (
            reply == "affirm" or (restated is not None and restated.format_valid and reply != "negate")
        ):
            self._verify_and_act(entity, self.state.risk, required_clarification=True)
            return

        # 3. Rejection with no new number.
        if reply == "negate" or contains_correction_language(transcript):
            if entity is not None:
                entity.status = EntityStatus.INVALIDATED
            self._log("Previous entity invalidated by caller", "system", transcript)
            self.state.entity = None
            self._ask_again("No problem — could you say the order number one digit at a time?")
            return

        # 4. Could not understand the answer (or it contradicted itself): never guess.
        self._ask_again("Sorry, I didn't catch that — could you say the order number one digit at a time?")

    def _consider_restated(self, restated: CriticalEntity) -> None:
        self._log(f"Caller restated the number: {restated.value}", "capture", f"confidence={restated.confidence:.2f}")
        ctx = RiskContext(in_clarification=True)
        assessment = self._enforce_format(restated, self._risk_fn(restated, ctx))
        self.state.risk = assessment
        self._log(
            f"Risk of a wrong number: {int(assessment.risk_score * 100)}% ({assessment.risk_level.value})",
            "risk", "; ".join(assessment.reasons) if assessment.reasons else "no risk signals",
        )
        self._last_value = restated.value
        if assessment.should_clarify:
            self.state.clarification = None
            self._pause_and_ask(restated, assessment, read_back=True)
        else:
            self._verify_and_act(restated, assessment, required_clarification=True)

    def _record_history(
        self, entity: CriticalEntity, required_clarification: bool, risk_score: Optional[float] = None
    ) -> None:
        self.state.history.append(
            ResolvedEntry(
                entity_type=entity.type, value=entity.value, status=entity.status,
                required_clarification=required_clarification, risk_score=risk_score, ts_ms=self._ts_ms(),
            )
        )
