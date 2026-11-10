"""Erkennt Fragen an die eigenen Dienste (Mails, Kalender) -- dann ohne Websuche.

"Was sind meine Mails?", "Welche Termine habe ich morgen?" -- die Antwort steht im eigenen
Postfach oder im Kalender. Im Netz steht sie nie.
Bis 12.5.5 Luna entschied das Modell selbst, wo es nachsieht, und der Planer
schickte bei "Strukturiert" oder im Pro-Modus Agenten ins Web.

Erkannt wird bewusst eng, mit einem Besitzwort ("meine Mails", "my calendar"),
"habe ich ..." oder einem Befehl am Satzanfang ("Zeig ..."). "Wie schreibe ich eine
gute E-Mail?" oder "Welche Termine hat das Bürgeramt?" bleiben normale Fragen.
"""

from __future__ import annotations

import re

SOURCES = ("calendar", "mail")

_BESITZ = r"(?:mein|meine|meinen|meinem|meiner|meines|my|unser|unsere|unseren|unserem|our)"

_LUECKE = r"(?:[\w'-]+\s+){0,3}"
_ICH_HABE = (r"(?:hab(?:e)?\s+ich|habe\s+ich|hast\s+du\s+(?:f(?:ü|ue)r\s+mich)|"
             r"do\s+i\s+have|have\s+i\s+(?:got|received)|did\s+i\s+(?:get|receive)|"
             r"gibt\s+es|is\s+there|are\s+there|any)")

_DAVOR_ICH = r"\s+(?:hab(?:e)?\s+ich|hast\s+du\s+f(?:ü|ue)r\s+mich|do\s+i\s+have)\b"

_MAIL_WORT = r"(?:e-?mails?|mails?|posteingang|postfach|inbox|gmail)"
_MAIL = re.compile(
    rf"\b{_BESITZ}\s+{_LUECKE}{_MAIL_WORT}\b"
    rf"|\b{_ICH_HABE}\s+{_LUECKE}{_MAIL_WORT}\b"
    rf"|\b{_MAIL_WORT}{_DAVOR_ICH}"
    rf"|\b(?:neue|neuen|ungelesene|ungelesenen|new|unread)\s+{_MAIL_WORT}\b"
    rf"|^\s*(?:lies|lese|zeig|zeige|check|checke|pr(?:ü|ue)fe?|read|show|open|"
    rf"(?:ö|oe)ffne)\s+(?:mir\s+|me\s+)?(?:die\s+|the\s+)?{_LUECKE}{_MAIL_WORT}\b",
    re.IGNORECASE,
)

_TERMIN_WORT = (r"(?:termin\w*|kalender\w*|calendar|appointments?|meetings?|"
                r"besprechung\w*|verabredung\w*|events?|schedule|agenda)")
_KALENDER = re.compile(
    rf"\b{_BESITZ}\s+{_LUECKE}{_TERMIN_WORT}\b"
    rf"|\b{_ICH_HABE}\s+{_LUECKE}{_TERMIN_WORT}\b"
    rf"|\b{_TERMIN_WORT}{_DAVOR_ICH}"
    r"|\bwas\s+steht\s+(?:(?:heute|morgen|(?:ü|ue)bermorgen|diese\s+woche|am\s+\w+)\s+)?"
    r"(?:bei\s+mir\s+)?an\b"
    r"|\bwhat(?:'s|\s+is)\s+on\s+my\s+(?:calendar|schedule|agenda)\b"
    rf"|^\s*(?:trag|trage|zeig|zeige|lies|check|add|show)\s+(?:mir\s+|me\s+)?"
    rf"(?:die\s+|den\s+|einen\s+|the\s+|an?\s+)?{_LUECKE}{_TERMIN_WORT}\b",
    re.IGNORECASE,
)

# "Bitte sende mir den ganzen Text von der Email xy" (13.0.1 Luna): Ein Befehl, der eine Mail
# zeigen, vorlesen oder schicken soll -- mit Bitte davor und etwas mehr Platz bis zum Mail-Wort.
_MAIL_BEFEHL = re.compile(
    r"^\s*(?:(?:bitte|please|kannst\s+du|k(?:ö|oe)nntest\s+du|can\s+you|could\s+you)\s+)?"
    r"(?:lies|lese|zeig|zeige|sende|send|schick|schicke|gib|give|show|read|open|"
    r"(?:ö|oe)ffne|kopier\w*|copy|fass|fasse)\s+(?:mir\s+|me\s+)?(?:[\w'-]+\s+){0,6}"
    rf"{_MAIL_WORT}\b",
    re.IGNORECASE,
)

# "Kannst du mir die letzte Mail vorlesen?" -- das Verb steht am Ende.
_MAIL_BITTE = re.compile(
    r"\b(?:kannst|k(?:ö|oe)nntest|w(?:ü|ue)rdest)\s+du\s+(?:mir\s+)?(?:[\w'-]+\s+){0,4}"
    rf"{_MAIL_WORT}\s+(?:[\w'-]+\s+){{0,3}}(?:vor)?(?:lesen|zeigen|schicken|senden|geben|"
    r"(?:ö|oe)ffnen|kopieren)\b",
    re.IGNORECASE,
)

# Nach einer Antwort aus dem eigenen Postfach: "lies mir die zweite vor", "zeig den ganzen
# Text", "und die Nachricht von Anna?" -- gemeint ist dieselbe Post.
_POST_FOLGE = re.compile(
    # bestimmt: "die Mail von Anna", "diese Nachricht" -- nicht "eine gute E-Mail" und nicht
    # "die Nachrichten" (Neuigkeiten)
    r"\b(?:die|der|den|dem|diese\w*|jene\w*|the|that|this)\s+(?:[\w'-]+\s+){0,2}"
    r"(?:e-?mail|mail|nachricht|message)\b(?!en)"
    r"|\b(?:die|der|den|the)\s+(?:erste|zweite|dritte|vierte|f(?:ü|ue)nfte|letzte|neueste|"
    r"oberste|untere|first|second|third|fourth|fifth|last|latest|top)\b"
    r"|\b(?:ganzen?|vollst(?:ä|ae)ndig\w*|komplett\w*|full|whole|entire)\s+"
    r"(?:text|inhalt|content|wortlaut|body)\b"
    r"|\bvor(?:lesen)?\s*[.!?]?\s*$",
    re.IGNORECASE,
)

_MUSTER = {"calendar": _KALENDER, "mail": _MAIL}


READ_TOOL = {"calendar": "calendar_events", "mail": "mail_search"}
TOOLS = {
    "calendar": frozenset({"calendar_events", "calendar_add", "calendar_edit"}),
    "mail": frozenset({"mail_search", "mail_read", "mail_draft"}),
}


NAMES = {
    "de": {"calendar": "dein Kalender", "mail": "dein Postfach"},
    "en": {"calendar": "your calendar", "mail": "your mailbox"},
}


WHERE = {
    "de": {"calendar": "Gmail & Kalender", "mail": "Gmail & Kalender"},
    "en": {"calendar": "Gmail & Calendar", "mail": "Gmail & Calendar"},
}


def own_sources(text: str) -> tuple[str, ...]:
    """Welche eigenen Dienste meint *text*? Leer = keiner (eine normale Frage)."""
    roh = " ".join(str(text or "").split())
    if not roh or len(roh) > 300:
        return ()
    treffer = []
    for quelle in SOURCES:
        if not _MUSTER[quelle].search(roh) and not (
                quelle == "mail" and (_MAIL_BEFEHL.search(roh) or _MAIL_BITTE.search(roh))):
            continue
        treffer.append(quelle)
    return tuple(treffer)


def followup_sources(text: str, previous: tuple[str, ...] | list[str] = ()) -> tuple[str, ...]:
    """Wie :func:`own_sources` -- und eine Folgefrage zur eigenen Post (13.0.1 Luna).

    Kam die vorige Antwort aus dem eigenen Postfach, meint "lies mir die zweite vor" oder
    "schick mir den ganzen Text" dieselbe Post. Ohne so eine vorige Antwort bleibt es eine
    normale Frage.
    """
    eigene = own_sources(text)
    if eigene or "mail" not in tuple(previous or ()):
        return eigene
    roh = " ".join(str(text or "").split())
    if not roh or len(roh) > 300:
        return ()
    return ("mail",) if _POST_FOLGE.search(roh) else ()


def calendar_days(text: str) -> int:
    """Wie viele Tage der Kalender zeigen soll: heute 1, morgen 2, sonst eine Woche."""
    klein = str(text or "").lower()
    if re.search(r"\b(?:monat|month)\b", klein):
        return 31
    if re.search(r"\b(?:woche|week)\b", klein):
        return 7
    if re.search(r"\b(?:(?:ü|ue)bermorgen)\b", klein):
        return 3
    if re.search(r"\b(?:morgen|tomorrow)\b", klein):
        return 2
    if re.search(r"\b(?:heute|today|tonight)\b", klein):
        return 1
    return 7


def missing_text(sources: tuple[str, ...] | list[str], language: str = "de") -> str:
    """Der Satz, wenn keiner der gemeinten Dienste eingerichtet ist."""
    sprache = "en" if language == "en" else "de"
    namen = [NAMES[sprache][q] for q in sources]
    orte = list(dict.fromkeys(WHERE[sprache][q] for q in sources))
    if sprache == "en":
        was = " and ".join(namen)
        wo = " and ".join(f"“{o}”" for o in orte)
        verb, es = ("aren’t", "them") if len(namen) > 1 else ("isn’t", "it")
        return (f"I can’t look that up yet: {was} {verb} connected. "
                f"You can connect {es} in Settings under {wo}. "
                "I won’t search the internet for it, because the answer is only there.")
    was = " und ".join(namen)
    wo = " und ".join(f"„{o}“" for o in orte)
    verb = "sind" if len(namen) > 1 else "ist"
    return (f"Das kann ich noch nicht nachsehen: {was[0].upper() + was[1:]} {verb} nicht "
            f"verbunden. Das geht in den Einstellungen unter {wo}. Im Internet "
            "suche ich dafür nicht, denn die Antwort steht nur dort.")


def turn_note(sources: tuple[str, ...] | list[str]) -> str:
    """Der Hinweis fuer das Modell in diesem Turn."""
    werkzeuge = ", ".join(f"`{w}`" for q in sources for w in sorted(TOOLS[q]))
    return ("[Diese Frage betrifft die eigenen Dienste des Nutzers. Nimm dafür "
            f"{werkzeuge}. Such dafür nicht im Internet -- die Antwort steht nur dort.]")
