import pytest

from app import risk_engine
from app.entity_detector import detect_critical_entity
from app.risk_engine import RiskContext, assess_risk, assess_risk_learned, assess_risk_rules
from app.risk_model import FEATURES, extract_features, load_model, sigmoid
from tests.conftest import toy_model, words


def detect(text, conf=0.95, **overrides):
    return detect_critical_entity(text, words(text, conf, **overrides))


CLEAR = "my order number is one five eight zero"


# ---- evidence model ---------------------------------------------------------

def test_clear_capture_is_not_questioned():
    r = assess_risk_learned(detect(CLEAR), RiskContext(), toy_model())
    assert r.should_clarify is False
    assert r.risk_score < 0.4


def test_weak_digit_triggers_a_question_about_that_digit():
    r = assess_risk_learned(detect(CLEAR, five=0.25), RiskContext(), toy_model())
    assert r.should_clarify is True
    assert 1 in r.weak_positions                      # the "five" is digit index 1
    assert any("weakest number word" in x for x in r.reasons)


def test_score_rises_as_confidence_falls():
    scores = [assess_risk_learned(detect(CLEAR, five=c), RiskContext(), toy_model()).risk_score
              for c in (0.95, 0.7, 0.4, 0.1)]
    assert scores == sorted(scores)
    assert scores[-1] > scores[0] + 0.3


def test_flags_that_are_off_never_appear_as_reasons():
    # a clean digit-by-digit capture has no "pairs" problem: it must not be blamed on it
    r = assess_risk_learned(detect(CLEAR, five=0.25), RiskContext(), toy_model())
    assert all("in pairs" not in x for x in r.reasons)
    assert r.breakdown["pairs"] == pytest.approx(0.0)


def test_pair_style_is_blamed_when_it_is_the_cause():
    e = detect("order number fifteen eighty")
    r = assess_risk_learned(e, RiskContext(), toy_model())
    assert r.breakdown["pairs"] > 0
    assert any("pairs" in x for x in r.reasons)


def test_contributions_are_relative_to_a_typical_clean_capture():
    m = toy_model()
    clean = m.contributions(extract_features(detect(CLEAR, 0.95)))
    assert clean["tok_min"] == pytest.approx(0.0, abs=1e-6)       # same as the reference
    weak = m.contributions(extract_features(detect(CLEAR, 0.95, five=0.25)))
    assert weak["tok_min"] > 3


def test_logit_and_score_agree():
    m = toy_model()
    feats = extract_features(detect(CLEAR, five=0.5))
    assert m.predict(feats) == pytest.approx(sigmoid(m.logit(feats)))


def test_threshold_controls_how_often_it_asks():
    e = detect(CLEAR, five=0.6)
    lenient = assess_risk_learned(e, RiskContext(), toy_model(), threshold=0.95)
    strict = assess_risk_learned(e, RiskContext(), toy_model(), threshold=0.05)
    assert lenient.should_clarify is False
    assert strict.should_clarify is True


# ---- conversation evidence ---------------------------------------------------

def test_contradiction_forces_a_question_even_when_audio_is_clear():
    e = detect("no i said one five eight zero")
    ctx = RiskContext(prior_values=["1850"], correction_language_seen=True)
    r = assess_risk_learned(e, ctx, toy_model())
    assert r.should_clarify is True
    assert "conflicting_captures" in r.signals
    assert "user_correction_language" in r.signals


def test_unprompted_repetition_forces_a_question():
    r = assess_risk_learned(detect(CLEAR), RiskContext(user_repeated_entity=True), toy_model())
    assert r.should_clarify is True
    assert "entity_repetition" in r.signals


def test_no_false_alarm_for_a_restated_number_inside_a_clarification():
    ctx = RiskContext(prior_values=["1850"], correction_language_seen=True, in_clarification=True)
    r = assess_risk_learned(detect("no it's one five eight zero"), ctx, toy_model())
    assert r.should_clarify is False


# ---- v1 rules and dispatcher ---------------------------------------------------

def test_rules_engine_still_works_as_baseline():
    assert assess_risk_rules(detect(CLEAR), RiskContext()).should_clarify is False
    assert assess_risk_rules(detect(CLEAR, 0.45), RiskContext()).should_clarify is True


def test_end_of_turn_confidence_is_used():
    words_ = words("order 7744", 0.95)
    hi = detect_critical_entity("order 7744", words_)
    lo = detect_critical_entity("order 7744", words_, end_of_turn_confidence=0.2)
    assert assess_risk_rules(lo, RiskContext()).risk_score > assess_risk_rules(hi, RiskContext()).risk_score


def test_dispatcher_falls_back_to_rules_without_a_model(monkeypatch):
    monkeypatch.setattr(risk_engine, "load_model", lambda: None)
    assert assess_risk(detect(CLEAR, 0.4), RiskContext()).engine == "rules-v1"


# ---- the model file that ships with the project ----------------------------------

shipped = load_model()


@pytest.mark.skipif(shipped is None, reason="no trained risk_model.json")
class TestShippedModel:
    def test_has_everything_the_engine_needs(self):
        assert tuple(shipped.names) == tuple(FEATURES)
        assert len(shipped.ref) == len(FEATURES)
        assert 0.0 < shipped.threshold < 1.0

    def test_a_clean_digit_by_digit_capture_is_not_questioned(self):
        assert assess_risk(detect(CLEAR, 0.98), RiskContext()).should_clarify is False

    def test_a_wrong_digit_count_is_always_questioned(self):
        r = assess_risk(detect("order number one five zero", 0.95), RiskContext())
        assert r.should_clarify is True and r.risk_score > 0.9
        assert any("expected 4" in x for x in r.reasons)

    def test_lower_confidence_never_lowers_the_score(self):
        scores = [assess_risk(detect("order number one thousand five hundred eighty", c), RiskContext()).risk_score
                  for c in (0.95, 0.7, 0.5, 0.3)]
        assert scores == sorted(scores)

    def test_a_shaky_big_number_is_questioned(self):
        e = detect("my order number is one thousand five hundred eighty", 0.97,
                   one=0.3, thousand=0.3, five=0.3, hundred=0.3, eighty=0.3)
        r = assess_risk(e, RiskContext())
        assert r.should_clarify is True
        assert r.breakdown["tok_mean"] > 0 and r.breakdown["cardinal"] > 0

    def test_the_hard_conversation_rules_still_apply(self):
        r = assess_risk(detect(CLEAR, 0.98), RiskContext(prior_values=["1850"], correction_language_seen=True))
        assert r.should_clarify is True
