"""
spoken.py — turn a 4-digit order number into the different ways people say it.

Used only by the benchmark generator (dev-time). Three styles are produced
because real callers use all of them, and each stresses the recogniser in a
different way:

  digits    "one five eight zero"            (also "oh" for 0, "double five")
  pairs     "fifteen eighty"                 (15/50 style confusions live here)
  cardinal  "one thousand five hundred eighty"
"""
from __future__ import annotations

import random

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

TEMPLATES = [
    "my order number is {n}",
    "it's order {n}",
    "order number {n}",
    "the order id is {n}",
    "yeah so the order number is {n} please",
    "um my order number is {n}",
    "booking reference {n}",
    "my confirmation code is {n}",
    "ticket number {n}",
    "i'm calling about order {n}",
]

YES_REPLIES = ["yes that's right", "yeah that's correct", "yes", "correct", "yep that's right"]
NO_TEMPLATES = ["no it's {n}", "no that's wrong it's {n}", "no the number is {n}", "sorry i said {n}"]


def two_digit_words(n: int, leading_oh: bool = True) -> str:
    if n < 10:
        return ("oh " if leading_oh else "") + ONES[n]
    if n < 20:
        return TEENS[n - 10]
    t, u = divmod(n, 10)
    return TENS[t] if u == 0 else f"{TENS[t]} {ONES[u]}"


def digits_style(value: str, rng: random.Random, use_oh: bool, use_double: bool) -> str:
    words: list[str] = []
    i = 0
    while i < len(value):
        d = value[i]
        run = 1
        while i + run < len(value) and value[i + run] == d:
            run += 1
        name = "oh" if (d == "0" and use_oh) else ONES[int(d)]
        if use_double and run == 2:
            words += ["double", name]
            i += 2
        elif use_double and run >= 3:
            words += ["triple", name]
            i += 3
        else:
            words.append(name)
            i += 1
    return " ".join(words)


def pairs_style(value: str) -> str:
    a, b = int(value[:2]), int(value[2:])
    first = two_digit_words(a)
    second = "hundred" if b == 0 else two_digit_words(b)
    if b == 0 and a < 10:
        return digits_style(value, random.Random(0), False, False)
    return f"{first} {second}"


def cardinal_style(value: str) -> str:
    n = int(value)
    th, rest = divmod(n, 1000)
    parts = [ONES[th], "thousand"]
    h, r = divmod(rest, 100)
    if h:
        parts += [ONES[h], "hundred"]
    if r:
        parts.append(two_digit_words(r, leading_oh=False))
    return " ".join(parts)


def speak(value: str, style: str, rng: random.Random) -> str:
    if style == "digits":
        return digits_style(value, rng, use_oh=rng.random() < 0.3, use_double=rng.random() < 0.5)
    if style == "pairs":
        return pairs_style(value)
    if style == "cardinal":
        return cardinal_style(value)
    raise ValueError(style)


def pick_style(rng: random.Random) -> str:
    r = rng.random()
    return "digits" if r < 0.62 else "pairs" if r < 0.87 else "cardinal"
