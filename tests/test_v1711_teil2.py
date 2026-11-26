"""17.1.1 (Teil 2): Aquaticy Standard -- Funde 149 bis 157 (je nachgestellt, vorher falsch)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from aquaticy import standard

JETZT = datetime(2026, 11, 19, 10, 30, tzinfo=ZoneInfo("Europe/Berlin"))


def frag(frage: str) -> str:
    return standard._antwort(frage, [], holen=lambda url: None, jetzt=JETZT)


@pytest.mark.parametrize("frage", ["Was ist ein Würfel?", "Wie schwer ist eine 2-Euro-Münze?",
                                   "Wie viele Ecken hat ein Würfel?",
                                   "Ich habe einen Würfel gefunden"])
def test_questions_about_dice_and_coins_do_not_roll(frage: str) -> None:
    antwort = frag(frage)
    assert "🎲" not in antwort and "🪙" not in antwort


@pytest.mark.parametrize("frage, muster", [
    ("Würfle zweimal", r"^🎲 Gewürfelt: [1-6] \+ [1-6] = \*\*\d+\*\*$"),
    ("Würfle dreimal", r"^🎲 Gewürfelt: [1-6] \+ [1-6] \+ [1-6] = \*\*\d+\*\*$"),
    ("Kannst du würfeln?", r"^🎲 Gewürfelt: \*\*[1-6]\*\*$"),
    ("Wirf zwei Münzen", r"^🪙 \*\*(Kopf|Zahl)\*\*, \*\*(Kopf|Zahl)\*\*$"),
    ("Münzwurf", r"^🪙 \*\*(Kopf|Zahl)\*\*$"),
    ("Kopf oder Zahl?", r"^🪙 \*\*(Kopf|Zahl)\*\*$"),
    ("Roll two dice", r"^🎲 Rolled: [1-6] \+ [1-6] = \*\*\d+\*\*$"),
    ("Roll a die twice", r"^🎲 Rolled: [1-6] \+ [1-6] = \*\*\d+\*\*$"),
    ("Roll a d20", r"^🎲 Rolled \(d20\): \*\*\d+\*\*$"),
    ("Roll a die", r"^🎲 Rolled: \*\*[1-6]\*\*$"),
    ("Flip two coins", r"^🪙 \*\*(Heads|Tails)\*\*, \*\*(Heads|Tails)\*\*$"),
])
def test_dice_and_coins(frage: str, muster: str) -> None:
    assert re.match(muster, frag(frage)), frag(frage)


@pytest.mark.parametrize("frage, antwort", [
    ("Zerlege 360 in Primfaktoren", "360 = **2 × 2 × 2 × 3 × 3 × 5**"),
    ("20 % Rabatt auf 50 €", "20 % Rabatt auf 50 € sind **40 €** (Unterschied: 10 €)."),
    ("Preis 80 Euro, 25 % Rabatt", "25 % Rabatt auf 80 € sind **60 €** (Unterschied: 20 €)."),
    ("15 % Rabatt auf 80", "15 % Rabatt auf 80 sind **68** (Unterschied: 12)."),
    ("Prime factors of 360", "360 = **2 × 2 × 2 × 3 × 3 × 5**"),
    ("Factorize 360", "360 = **2 × 2 × 2 × 3 × 3 × 5**"),
    ("Is 91 prime?", "No, 91 is not a prime number: it can be divided by 7 (7 × 13)."),
    ("Is 97 a prime number?", "Yes, **97** is a prime number."),
    ("How many days are in this year?", "2026 has **365 days**."),
    ("20% off 50 dollars", "20 % off 50 $ is **40 $** (you save 10 $)."),
])
def test_fixed_answers(frage: str, antwort: str) -> None:
    assert frag(frage) == antwort


@pytest.mark.parametrize("frage, antwort", [
    ("How many minutes in a week?", "1 week is **10,080 minutes**."),
    ("How many hours in a week?", "1 week is **168 hours**."),
    ("Median of 3, 1, 4, 1, 5", "The median is **3**."),
    ("0.75 as a fraction", "0.75 as a fraction is **3/4**."),
    ("How many letters in Mississippi?", "“Mississippi” has **11 letters**."),
    ("Reverse hello", "“hello” backwards is **olleh**."),
    ("Write Hello backwards", "“Hello” backwards is **olleH**."),
    ("What's the sum of digits of 12345?", "The digit sum of 12345 is **15**."),
    ("Digit sum of 999", "The digit sum of 999 is **27**."),
    ("Tip 15% on 45 dollars", "A 15 % tip on 45 $ is **6.75 $** – 51.75 $ in total."),
])
def test_english_forms_that_worked_in_german(frage: str, antwort: str) -> None:
    # 158 bis 164: vorher "Sorry" oder sogar die deutsche Absage.
    assert frag(frage) == antwort


@pytest.mark.parametrize("frage, antwort", [
    ("What day is it in 10 days?", "In 10 days it will be **Sunday, November 29, 2026**."),
    ("What date is it in 3 months?", "In 3 months it will be **Friday, February 19, 2027**."),
    ("What was the date 2 years ago?", "2 years ago it was **Tuesday, November 19, 2024**."),
    ("What is 15 divided by 4 with remainder?", "15 ÷ 4 = **3 remainder 3** (3 × 4 + 3 = 15)."),
    ("Round 3.456 to two decimals", "Rounded: **3.46**"),
    ("Round 1234 to the nearest hundred", "Rounded: **1,200**"),
    ("Is 12 even?", "Yes, **12** is even."),
    ("Is 7 even?", "No, 7 is odd."),
    ("Is 1001 divisible by 7?", "Yes, 1,001 is divisible by 7 (1,001 ÷ 7 = **143**)."),
    ("What are the divisors of 28?", "28 has **6 divisors**: 1, 2, 4, 7, 14, 28."),
    ("How many vowels are in banana?", "“banana” has **3 vowels**."),
    ("Count the e in strawberry", "“e” appears **1 time** in “strawberry”."),
    ("What's double 21?", "Double 21 is **42**."),
    ("Sort: banana, apple, cherry", "Sorted: **apple, banana, cherry**"),
    ("How long until midnight?", "There are **13 hours and 30 minutes** until midnight."),
    ("How many working days are in December?", "December 2026 has **22 working days** (Monday "
     "to Friday, without nationwide public holidays in Germany)."),
    ("What is my zodiac sign if I was born on March 3?", "Someone born on March 3 is a "
     "**Pisces ♓**."),
    ("What is 19% VAT on 100 euros?", "19 % VAT on 100 € is **19 €** (gross 119 €)."),
])
def test_more_english_forms(frage: str, antwort: str) -> None:
    # 168 bis 184: vorher das Datum von heute, "Sorry" oder die deutsche Absage.
    assert frag(frage) == antwort


def test_english_random_answers() -> None:
    assert frag("Tell me a fun fact").startswith("Did you know? ")
    assert frag("Yes or no?") in ("My answer: **Yes**.", "My answer: **No**.")
    assert frag("Choose between pizza and pasta") in ("I'd say: **pizza**.", "I'd say: **pasta**.")


@pytest.mark.parametrize("frage", ["Mein Chef hat mich beleidigt, was kann ich tun?",
                                   "Mobbing: jemand nennt mich Opfer, was kann ich tun?"])
def test_a_problem_does_not_get_ideas_against_boredom(frage: str) -> None:
    # 185: vorher "Räum eine Schublade auf" und Co.
    assert "Ideen für dich" not in frag(frage)
    assert "Ideen für dich" in frag("Was kann ich tun?")


@pytest.mark.parametrize("frage, antwort", [
    ("Wie viele Minuten sind 1 Stunde 20 Minuten?", "1 Std. 20 Min. sind **80 Minuten**."),
    ("Wie viele Sekunden sind 2 Stunden und 30 Minuten?",
     "2 Std. 30 Min. sind **9.000 Sekunden**."),
    ("How many seconds are 2 hours and 30 minutes?", "2 h 30 min is **9,000 seconds**."),
    ("2 hours 30 minutes in seconds", "2 h 30 min is **9,000 seconds**."),
])
def test_compound_durations(frage: str, antwort: str) -> None:
    # 186 und 187: vorher nur die Stunden bzw. "9.000 seconds".
    assert frag(frage) == antwort


@pytest.mark.parametrize("frage, anfang", [
    ("Hi there", "Hello! I'm Aquaticy Standard."),
    ("Thank you so much", "You're welcome!"),
    ("You are great", "Thank you for the kind words!"),
    ("I love you", "Thank you for the kind words!"),
    ("I am scared", "I'm sorry you feel scared."),
    ("I am afraid", "I'm sorry you feel afraid."),
])
def test_english_small_talk(frage: str, anfang: str) -> None:
    # 188 bis 191: vorher "Sorry" oder die deutsche Absage.
    assert frag(frage).startswith(anfang)
    assert frag("Hey").startswith(("Hallo", "Hi", "Hey")) or "Sprachmodell" in frag("Hey")


@pytest.mark.parametrize("frage, antwort", [
    ("1 acre in square meters", "1 acre is **4,046.8564 m²**."),
    ("How many megabytes in a gigabyte?", "1 GB is **1,000 MB**."),
    ("How many tablespoons in a cup?", "1 cup is **16 tablespoons**."),
    ("2 Esslöffel in ml", "2 Esslöffel sind **30 ml**."),
    ("Was sind 15 % von 80 €?", "15 % von 80 € sind **12 €**."),
    ("Wann ist der 1. Mai?", "Der 01.05.2027 (Tag der Arbeit, bundesweiter Feiertag) ist ein "
     "**Samstag** – in 163 Tagen."),
    ("Wie viele Monate bis Weihnachten?", "Bis Weihnachten (24.12.2026) sind es noch **35 Tage**. "
     "Das sind **1 Monat und 5 Tage**."),
])
def test_english_units(frage: str, antwort: str) -> None:
    # 192 und 193; dazu US-Löffel (16 tablespoons je cup, vorher 15,77).
    assert frag(frage) == antwort
