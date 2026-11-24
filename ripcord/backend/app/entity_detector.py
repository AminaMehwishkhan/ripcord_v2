"""
entity_detector.py

Extracts a critical numeric entity (a 4-digit order / booking / reference
number) from a finished Turn transcript + word list, and records HOW it was
heard — not just what value came out. That evidence (per-digit confidence,
spoken style, homophone digits, competing numbers…) is what the risk model
scores.

What it understands
-------------------
  digits     "one five eight zero", "one five eight oh", "double five two"
  numerals   "1580" (already normalised by the ASR)
  pairs      "fifteen eighty", "twenty two sixty four", "fifteen hundred"
  cardinal   "one thousand five hundred eighty"
  homophones "won five ate zero", "three for seven two" — accepted only
             INSIDE a run of number words, and counted as a risk signal

A carrier phrase ("order number", "booking reference"…) is preferred so an
unrelated number in the same sentence is not grabbed. Without one, the first
number-like span is used, which is what makes bare replies like
"no it's one five eight zero" work.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .models import CriticalEntity, Word

EXPECTED_PATTERN = r"\d{4}"  # 4-digit order IDs for the demo workflow
EXPECTED_LENGTH = 4

CARRIER_PHRASES = [
    "order number", "order id", "order",
    "booking number", "booking reference", "booking",
    "reference number", "reference",
    "confirmation code", "confirmation number", "confirmation",
    "ticket number", "ticket", "account reference",
]
# Words that may sit between a carrier phrase and the number itself.
FILLERS = {"is", "was", "it's", "its", "number", "no", "id", "the", "a", "um", "uh", "uhm",
           "are", "that's", "thats", "code", "reference", "please", "like"}

UNITS = {"zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4,
         "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
MULTIPLIERS = {"double": 2, "triple": 3}
# Words an ASR commonly writes for a spoken digit. Only trusted inside a run.
HOMOPHONES = {"won": 1, "to": 2, "too": 2, "for": 4, "fore": 4, "ate": 8, "o": 0}

_WORD_CLEAN = re.compile(r"^[^\w']+|[^\w']+$")

CORRECTION_RE = re.compile(
    r"\b(no|nope|that's wrong|thats wrong|not that|i said|sorry|let me repeat|actually|"
    r"i meant|wrong|incorrect|not right)\b"
)
AFFIRM_RE = re.compile(
    r"\b(yes|yeah|yep|yup|correct|that's right|thats right|right|that's correct|"
    r"thats correct|confirmed|exactly|sure)\b"
)
NEGATE_RE = re.compile(
    r"\b(no|nope|nah|incorrect|that's wrong|thats wrong|wrong|not right|not correct|"
    r"that's not|thats not)\b"
)


def _clean(text: str) -> str:
    return _WORD_CLEAN.sub("", text.strip().lower())


@dataclass
class _Run:
    start: int                 # token index of first number word
    end: int                   # one past the last
    value: str = ""
    style: str = "digits"
    digit_idx: list[list[int]] = field(default_factory=list)  # per digit: token indices it came from
    homophones: int = 0
    teen_ten: int = 0


def _kind(tok: str) -> Optional[str]:
    if tok in UNITS:
        return "unit"
    if tok in TEENS:
        return "teen"
    if tok in TENS:
        return "ten"
    if tok in ("hundred", "thousand"):
        return "big"
    if tok in MULTIPLIERS:
        return "mult"
    if tok in HOMOPHONES:
        return "homophone"
    if tok.isdigit():
        return "numeral"
    return None


def _parse_run(tokens: list[str], start: int, allow_leading_homophone: bool) -> Optional[_Run]:
    """Greedy: collect the maximal run of number-like tokens from `start`, trim, parse."""
    j = start
    kinds: list[str] = []
    while j < len(tokens):
        k = _kind(tokens[j])
        if k is None:
            break
        kinds.append(k)
        j += 1
    end = j
    if not kinds:
        return None

    # A homophone that opens the run is almost always the English word
    # ("for", "to") — drop it unless the caller said "oh five…" after a carrier.
    lo = 0
    # ...but right after "order number", a short run that opens with "won"/"to"/
    # "for" is most likely a misheard digit ("won five ate zero").
    keep_leading = allow_leading_homophone and len(kinds) <= EXPECTED_LENGTH
    while lo < len(kinds) and kinds[lo] == "homophone":
        tok = tokens[start + lo]
        if keep_leading or (allow_leading_homophone and tok == "o"):
            break
        lo += 1
    if lo >= len(kinds):
        return None
    # Trailing homophones are kept only while the number is still short.
    hi = len(kinds)
    while hi > lo and kinds[hi - 1] == "homophone" and (hi - lo) > EXPECTED_LENGTH:
        hi -= 1
    if hi <= lo:
        return None

    s, e = start + lo, start + hi
    toks = tokens[s:e]
    ks = kinds[lo:hi]

    run = _Run(start=s, end=e)
    run.homophones = sum(1 for t, k in zip(toks, ks) if k == "homophone" and t != "o")
    run.teen_ten = sum(1 for k in ks if k in ("teen", "ten"))

    if "big" in ks:  # cardinal: "one thousand five hundred eighty"
        total, cur, ok = 0, 0, True
        for t, k in zip(toks, ks):
            if k in ("unit", "homophone"):
                cur += UNITS.get(t, HOMOPHONES.get(t, 0))
            elif k == "teen":
                cur += TEENS[t]
            elif k == "ten":
                cur += TENS[t]
            elif k == "numeral":
                cur += int(t)
            elif t == "hundred":
                cur = max(cur, 1) * 100
            elif t == "thousand":
                total += max(cur, 1) * 1000
                cur = 0
            else:
                ok = False
        value = str(total + cur) if ok else ""
        if value:
            run.value, run.style = value, "cardinal"
            idx = list(range(s, e))
            run.digit_idx = [idx for _ in value]  # every digit shares the whole phrase
            return run
        # fall through to plain digit concatenation if the phrase was malformed

    pair_like = any(k in ("teen", "ten") for k in ks)
    digits: list[str] = []
    didx: list[list[int]] = []
    i = 0
    while i < len(toks):
        t, k = toks[i], ks[i]
        ti = s + i
        if k == "mult" and i + 1 < len(toks) and ks[i + 1] in ("unit", "homophone"):
            d = str(UNITS.get(toks[i + 1], HOMOPHONES.get(toks[i + 1], 0)))
            n = MULTIPLIERS[t]
            digits += [d] * n
            didx += [[ti + 1]] * n
            i += 2
        elif k == "mult":
            i += 1  # dangling "double" — ignore
        elif k == "numeral":
            digits += list(t)
            didx += [[ti]] * len(t)
            i += 1
        elif k == "teen":
            v = str(TEENS[t])
            digits += list(v)
            didx += [[ti]] * 2
            i += 1
        elif k == "ten":
            if i + 1 < len(toks) and ks[i + 1] in ("unit", "homophone") and toks[i + 1] != "oh" \
                    and UNITS.get(toks[i + 1], HOMOPHONES.get(toks[i + 1], 0)) != 0:
                u = UNITS.get(toks[i + 1], HOMOPHONES.get(toks[i + 1], 0))
                digits += [str(TENS[t] // 10), str(u)]
                didx += [[ti], [ti + 1]]
                i += 2
            else:
                digits += [str(TENS[t] // 10), "0"]
                didx += [[ti], [ti]]
                i += 1
        else:  # unit / homophone
            d = UNITS.get(t, HOMOPHONES.get(t))
            digits.append(str(d))
            didx.append([ti])
            i += 1

    if not digits:
        return None
    run.value = "".join(digits)
    run.digit_idx = didx
    run.style = "pairs" if pair_like else ("numeral" if all(k == "numeral" for k in ks) else "digits")
    return run


def _find_runs(tokens: list[str], carrier_end: Optional[int]) -> list[_Run]:
    runs: list[_Run] = []
    i = 0
    while i < len(tokens):
        if _kind(tokens[i]) is None:
            i += 1
            continue
        after_carrier = carrier_end is not None and i == carrier_end
        run = _parse_run(tokens, i, allow_leading_homophone=after_carrier)
        if run is None:
            i += 1
            continue
        runs.append(run)
        i = max(run.end, i + 1)
    return runs


def _carrier_end(tokens: list[str]) -> Optional[int]:
    """Index of the first token after the carrier phrase and any fillers."""
    for phrase in CARRIER_PHRASES:
        p = phrase.split()
        n = len(p)
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == p:
                j = i + n
                while j < len(tokens) and tokens[j] in FILLERS:
                    j += 1
                return j
    return None


def detect_critical_entity(
    transcript: str,
    words: list[Word],
    turn_order: int = 0,
    end_of_turn_confidence: Optional[float] = None,
) -> Optional[CriticalEntity]:
    """
    Look for a critical numeric entity in a finished turn.

    Returns None if nothing number-like was found — the caller treats that as
    "nothing to verify yet", not as a low-confidence entity.
    """
    if not words:
        return None
    tokens = [_clean(w.text) for w in words]
    cend = _carrier_end(tokens)
    runs = [r for r in _find_runs(tokens, cend) if r.value]
    if not runs:
        return None

    chosen: Optional[_Run] = None
    if cend is not None:
        chosen = next((r for r in runs if r.start == cend), None) or \
                 next((r for r in runs if r.start >= cend), None)
    if chosen is None:
        # No carrier phrase (or none followed by a number): prefer a span of
        # plausible length, otherwise the first one.
        chosen = next((r for r in runs if len(r.value) == EXPECTED_LENGTH), runs[0])

    span_idx = sorted({i for d in chosen.digit_idx for i in d})
    span_words = [words[i] for i in span_idx]
    confs = [w.confidence for w in span_words]
    digit_conf = [round(min(words[i].confidence for i in d), 4) if len(d) == 1
                  else round(sum(words[i].confidence for i in d) / len(d), 4)
                  for d in chosen.digit_idx]

    span_set = set(span_idx)
    outside = [w.confidence for i, w in enumerate(words) if i not in span_set]
    mean_conf = sum(confs) / len(confs) if confs else 0.0

    rate = None
    if span_words and span_words[-1].end > span_words[0].start:
        secs = (span_words[-1].end - span_words[0].start) / 1000.0
        if secs > 0.2:
            rate = round(len(chosen.value) / secs, 3)

    return CriticalEntity(
        type="order_id",
        value=chosen.value,
        raw_words=span_words,
        confidence=round(mean_conf, 4),
        expected_pattern=EXPECTED_PATTERN,
        format_valid=bool(re.fullmatch(EXPECTED_PATTERN, chosen.value)),
        turn_order=turn_order,
        end_of_turn_confidence=end_of_turn_confidence,
        digit_confidences=digit_conf,
        style=chosen.style,  # type: ignore[arg-type]
        min_confidence=round(min(confs), 4) if confs else 0.0,
        low_conf_fraction=round(sum(1 for c in confs if c < 0.7) / len(confs), 4) if confs else 1.0,
        context_confidence=round(sum(outside) / len(outside), 4) if outside else None,
        teen_ten_words=chosen.teen_ten,
        homophone_digits=chosen.homophones,
        carrier_found=cend is not None and chosen.start >= cend,
        competing_spans=max(0, sum(1 for r in runs if len(r.value) >= 2) - 1),
        speech_rate=rate,
    )


# ---------------------------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------------------------

def contains_correction_language(transcript: str) -> bool:
    return bool(CORRECTION_RE.search(transcript.lower().replace("’", "'")))


def values_conflict(a: Optional[str], b: Optional[str]) -> bool:
    """Two captured entity values disagree (and neither is empty)."""
    return bool(a) and bool(b) and a != b


def classify_reply(transcript: str, words: list[Word], min_confidence: float = 0.5) -> str:
    """
    Classify a caller's answer to a yes/no question as "affirm", "negate" or
    "unknown". Matches whole words only (so "know" is not "no"), and a yes/no
    the recogniser itself was unsure about counts as "unknown" — acting on a
    misheard "yes" would defeat the point of asking.
    """
    text = transcript.lower().replace("’", "'")
    neg = NEGATE_RE.search(text)
    aff = AFFIRM_RE.search(text)
    hit = neg or aff
    if hit is None:
        return "unknown"
    if neg and aff:
        # "no that's right"/"yes that's wrong" — contradictory; refuse to guess.
        return "unknown"
    # Confidence of the word(s) that triggered the match.
    trigger = set(hit.group(0).replace("'", "").split())
    ws = [w.confidence for w in words if _clean(w.text).replace("'", "") in trigger]
    if ws and max(ws) < min_confidence:
        return "unknown"
    return "negate" if neg else "affirm"
