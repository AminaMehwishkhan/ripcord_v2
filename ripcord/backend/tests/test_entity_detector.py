import pytest

from app.entity_detector import (
    classify_reply,
    contains_correction_language,
    detect_critical_entity,
    values_conflict,
)
from tests.conftest import words


def detect(text, conf=0.95, **kw):
    return detect_critical_entity(text, words(text, conf), **kw)


@pytest.mark.parametrize("text, expected, style", [
    ("my order number is one five eight zero", "1580", "digits"),
    ("my order number is one five eight oh", "1580", "digits"),
    ("order number fifteen eighty", "1580", "pairs"),
    ("order seventy seven forty four", "7744", "pairs"),
    ("order number one thousand five hundred eighty", "1580", "cardinal"),
    ("it is fifteen hundred eighty", "1580", "cardinal"),
    ("order double one five oh", "1150", "digits"),
    ("order triple five two", "5552", "digits"),
    ("it's 1580", "1580", "numeral"),
    ("order number is 15 80", "1580", "numeral"),
])
def test_parses_every_way_people_say_a_number(text, expected, style):
    e = detect(text)
    assert e is not None
    assert e.value == expected
    assert e.style == style
    assert e.format_valid


def test_homophone_digits_are_recovered_and_flagged():
    e = detect("order number won five ate zero")
    assert e.value == "1580"
    assert e.homophone_digits >= 1


def test_wrong_length_is_marked_invalid():
    assert detect("order number one five eight").format_valid is False
    assert detect("my order is one five eight zero two").format_valid is False


def test_no_number_means_no_entity():
    assert detect("hello there") is None


def test_carrier_phrase_is_detected():
    assert detect("my order number is one five eight zero").carrier_found is True
    assert detect("one five eight zero").carrier_found is False


def test_per_digit_confidence_follows_the_digit_words():
    text = "order one five eight zero"
    ws = words(text, 0.95, five=0.31)
    e = detect_critical_entity(text, ws)
    assert e.digit_confidences[1] == pytest.approx(0.31)
    assert e.min_confidence == pytest.approx(0.31)
    assert e.confidence < 0.95


def test_end_of_turn_confidence_is_kept():
    e = detect("order 7744", end_of_turn_confidence=0.3)
    assert e.end_of_turn_confidence == pytest.approx(0.3)


@pytest.mark.parametrize("text, label", [
    ("yes that's correct", "affirm"), ("yeah", "affirm"), ("that is right", "affirm"),
    ("no", "negate"), ("nope", "negate"), ("no it's wrong", "negate"),
    ("uh", "unknown"), ("what", "unknown"),
])
def test_classify_reply(text, label):
    assert classify_reply(text, words(text, 0.9)) == label


def test_classify_reply_never_acts_on_a_yes_or_no_it_barely_heard():
    # acting on a misheard "yes" would defeat the point of asking
    assert classify_reply("yes", words("yes", 0.95, yes=0.2)) == "unknown"
    assert classify_reply("no", words("no", 0.95, no=0.2)) == "unknown"


def test_classify_reply_refuses_to_guess_when_it_contradicts_itself():
    text = "no that's right"
    assert classify_reply(text, words(text, 0.95)) == "unknown"


def test_value_conflict():
    assert values_conflict("1580", "1850") is True
    assert values_conflict("1580", "1580") is False


def test_correction_language():
    assert contains_correction_language("No, that's wrong, I said 3719.")
    assert not contains_correction_language("My order number is 1580.")
