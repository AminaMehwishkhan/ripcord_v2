"""The orchestrator is the part that makes the real decisions, so these tests drive it end to end."""
import pytest

from app.models import EntityStatus
from app.risk_engine import assess_risk_learned
from app.session import MAX_ATTEMPTS, SessionOrchestrator
from app.workflow_guard import UnverifiedEntityError, execute_order_lookup
from tests.conftest import toy_model, turn, words
from app.entity_detector import detect_critical_entity


MODEL = toy_model()


def ask_if_shaky(entity, ctx):
    """The real learned engine, with a small fixed model so tests don't depend on training."""
    return assess_risk_learned(entity, ctx, MODEL)


def ripcord() -> SessionOrchestrator:
    return SessionOrchestrator(ripcord_enabled=True, risk_fn=ask_if_shaky)


SHAKY = turn("my order number is one five zero", 0.98, one=0.55, five=0.51, zero=0.48)   # heard "150"
CLEAR = turn("my order number is one five eight zero")


# ---- Mode A / Mode B ---------------------------------------------------------

def test_mode_a_accepts_whatever_it_heard():
    orch = SessionOrchestrator(ripcord_enabled=False)
    s = orch.process_turn(SHAKY)
    assert s.verified_value == "150"            # wrong, and nothing stopped it
    assert s.workflow_paused is False
    assert s.risk is None                       # nothing was scored
    assert orch.questions_asked == 0


def test_mode_b_lets_a_clear_number_straight_through():
    orch = ripcord()
    s = orch.process_turn(CLEAR)
    assert s.verified_value == "1580"
    assert s.clarification is None
    assert orch.questions_asked == 0
    assert s.entity.status == EntityStatus.VERIFIED


def test_mode_b_pauses_on_a_shaky_number_and_does_not_act():
    orch = ripcord()
    s = orch.process_turn(SHAKY)
    assert s.workflow_paused is True
    assert s.clarification is not None
    assert s.verified_value is None
    assert s.action_result is None
    assert s.entity.status == EntityStatus.CLARIFYING


# ---- answering the question -----------------------------------------------------

def test_yes_to_a_correct_read_back_verifies_the_number():
    orch = ripcord()
    orch.process_turn(turn("my order number is one five eight zero", 0.98, five=0.4))
    assert orch.state.clarification is not None
    s = orch.process_turn(turn("yes that's right", order=1))
    assert s.verified_value == "1580"
    assert s.workflow_paused is False
    assert "1580" in s.action_result


def test_a_clean_restated_number_replaces_the_wrong_one():
    orch = ripcord()
    orch.process_turn(SHAKY)
    s = orch.process_turn(turn("no it's one five eight zero", order=1))
    assert s.verified_value == "1580"
    assert s.workflow_paused is False


def test_a_restated_number_is_not_trusted_blindly():
    """The caller's answer comes from the same noisy recogniser, so it is scored again and read back."""
    orch = ripcord()
    orch.process_turn(SHAKY)
    s = orch.process_turn(turn("no it's one five eight zero", 0.95, five=0.3, order=1))
    assert s.verified_value is None
    assert s.clarification is not None and s.clarification.kind == "read_back"
    assert s.clarification.candidate_value == "1580"
    # ...and once the caller confirms that read-back, the number is accepted
    s = orch.process_turn(turn("yes", order=2))
    assert s.verified_value == "1580"


def test_a_plain_no_asks_for_the_digits_one_at_a_time():
    orch = ripcord()
    orch.process_turn(SHAKY)
    s = orch.process_turn(turn("no", order=1))
    assert s.verified_value is None
    assert s.clarification is not None
    assert "one digit at a time" in s.clarification.question
    assert s.entity is None                      # the old capture was thrown away


def test_an_unclear_answer_never_counts_as_a_yes():
    orch = ripcord()
    orch.process_turn(SHAKY)
    s = orch.process_turn(turn("uh hmm maybe", order=1))
    assert s.verified_value is None
    assert s.workflow_paused is True


def test_a_yes_the_recogniser_barely_heard_is_not_accepted():
    orch = ripcord()
    orch.process_turn(SHAKY)
    s = orch.process_turn(turn("yes", 0.15, order=1))
    assert s.verified_value is None


def test_it_gives_up_and_hands_off_after_the_attempt_limit():
    orch = ripcord()
    orch.process_turn(SHAKY)
    for i in range(1, MAX_ATTEMPTS + 2):
        orch.process_turn(turn("uh", order=i))
    s = orch.state
    assert s.escalated is True
    assert s.verified_value is None
    assert s.action_result is None                # it never guessed
    assert orch.questions_asked <= MAX_ATTEMPTS


def test_nothing_happens_after_escalation():
    orch = ripcord()
    orch.process_turn(SHAKY)
    for i in range(1, MAX_ATTEMPTS + 2):
        orch.process_turn(turn("uh", order=i))
    s = orch.process_turn(turn("my order number is one five eight zero", order=9))
    assert s.verified_value is None


# ---- audit + guard -------------------------------------------------------------------

def test_history_records_what_was_resolved():
    orch = ripcord()
    orch.process_turn(CLEAR)
    assert [h.value for h in orch.state.history] == ["1580"]
    assert orch.state.history[0].required_clarification is False
    assert orch.state.last_decision_latency_ms is not None


def test_conversation_log_has_both_sides():
    orch = ripcord()
    orch.process_turn(SHAKY)
    roles = [c.role for c in orch.state.conversation]
    assert roles[0] == "caller" and "agent" in roles


def test_the_workflow_guard_refuses_an_unverified_number():
    e = detect_critical_entity("order 1580", words("order 1580", 0.6))
    assert e.status == EntityStatus.UNKNOWN
    with pytest.raises(UnverifiedEntityError):
        execute_order_lookup(e)


def test_the_workflow_guard_runs_once_verified():
    e = detect_critical_entity("order 1580", words("order 1580", 0.95))
    e.status = EntityStatus.VERIFIED
    assert "1580" in execute_order_lookup(e)


def test_partial_transcripts_do_not_trigger_anything():
    orch = ripcord()
    orch.process_turn({"transcript": "my order number is one", "end_of_turn": False, "words": []})
    assert orch.state.live_partial.startswith("my order")
    assert orch.state.entity is None and orch.questions_asked == 0


# ---- a confident-but-wrong capture, caught by the caller's own correction -------------

def test_a_correction_after_an_accepted_number_is_not_ignored():
    """Clear audio, wrong number (3179). The caller notices and says so: Ripcord must not just swallow it."""
    orch = ripcord()
    s = orch.process_turn(turn("my order number is three one seven nine"))
    assert s.verified_value == "3179" and s.action_result          # got through: the audio was clear
    s = orch.process_turn(turn("no i said three seven one nine", order=1))
    assert s.verified_value is None and s.action_result is None    # the old number no longer counts
    assert s.clarification is not None and s.clarification.candidate_value == "3719"
    assert s.history[0].status == EntityStatus.INVALIDATED
    assert any("already accepted" in t.label for t in s.timeline)  # and the earlier action is flagged
    s = orch.process_turn(turn("yes", order=2))
    assert s.verified_value == "3719"


def test_a_second_different_number_without_correction_is_just_a_new_entity():
    orch = ripcord()
    orch.process_turn(turn("my order number is three one seven nine"))
    s = orch.process_turn(turn("and also order two two six four", order=1))
    assert s.verified_value == "2264"        # no "no / I said" language: treated as a separate order


# ---- a malformed number can never be confirmed (bug found in the first benchmark run) --------

def test_the_guard_refuses_a_malformed_number_even_if_marked_verified():
    e = detect_critical_entity("order one seven", words("order one seven", 0.95))
    e.status = EntityStatus.VERIFIED
    assert e.format_valid is False
    with pytest.raises(UnverifiedEntityError):
        execute_order_lookup(e)


def test_repeating_a_malformed_number_does_not_verify_it():
    """Recogniser hears only '17'. The caller answers, the recogniser garbles the 'no' and hears '17' again."""
    orch = ripcord()
    s = orch.process_turn(turn("order number one seven"))
    assert s.clarification is not None and s.entity.value == "17"
    s = orch.process_turn(turn("know that's why it's one seven", 0.95, know=0.2, order=1))
    assert s.verified_value is None and s.action_result is None
    assert s.clarification is not None                     # still asking for the full number


def test_saying_yes_to_a_malformed_number_does_not_verify_it():
    orch = ripcord()
    orch.process_turn(turn("order number one seven"))
    s = orch.process_turn(turn("yes that's right", order=1))
    assert s.verified_value is None and s.action_result is None


def test_a_full_number_after_a_malformed_one_is_accepted():
    orch = ripcord()
    orch.process_turn(turn("order number one seven"))
    s = orch.process_turn(turn("no it's one seven four two", order=1))
    assert s.verified_value == "1742"


def test_a_lenient_policy_cannot_let_a_malformed_number_through():
    """The digit-count rule lives in the orchestrator, so no scoring policy can switch it off."""
    from app.risk_engine import RiskContext
    from app.benchmark import _fixed
    orch = SessionOrchestrator(ripcord_enabled=True, risk_fn=lambda e, c: _fixed(False))
    s = orch.process_turn(turn("order number one seven"))
    assert s.verified_value is None and s.clarification is not None
