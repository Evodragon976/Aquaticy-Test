"""17.1.1: Meldungen, die in der englischen Oberflaeche deutsch blieben (Klasse E).

Prueft ueber den Uebersetzer der Seite selbst (EN, EN_MUSTER, aufEnglisch -- mit node). Die
Texte kommen aus dem Code, nicht abgeschrieben: So faellt auf, wenn sich einer aendert.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

import pytest

from aquaticy import aiguard, auth

ROOT = Path(__file__).resolve().parents[1]
SEITE = (ROOT / "aquaticy" / "webui.html").read_text(encoding="utf-8")


#: Nur in Aquaticy-Test (Anmeldung mit Nutzername).
ZUSATZ = ["E-Mail, Nutzername oder Passwort stimmt nicht."]


def _englisch(texte: list[str]) -> list[str]:
    en = re.search(r"const EN = (\{.*?\n\});", SEITE, re.S)
    muster = re.search(r"const EN_MUSTER = (\[.*?\n\]);", SEITE, re.S)
    funktion = SEITE[SEITE.index("function aufEnglisch("):SEITE.index("function enOder(")]
    assert en and muster
    skript = (f"const EN = {en.group(1)};\n"
              "const schluessel = t => t.replace(/\\s+/g, ' ').trim();\n"
              "let sprache = 'en';\nfunction sp(de, en){ return en; }\n"
              "function enOder(t){ return aufEnglisch(t) || t; }\n"
              "function enOderDe(t){ return aufEnglisch(t) || t; }\n"
              f"const EN_MUSTER = {muster.group(1)};\n{funktion}\n"
              "process.stdout.write(JSON.stringify(JSON.parse(process.argv[2]).map("
              "t => aufEnglisch(t))));")
    try:
        lauf = subprocess.run(["node", "-", json.dumps(texte)], input=skript, capture_output=True,
                              text=True, timeout=60)
    except FileNotFoundError:
        pytest.skip("node fehlt")
    assert lauf.returncode == 0, lauf.stderr
    return list(json.loads(lauf.stdout))


def _fehler(funktion, *args) -> str:
    with pytest.raises(ValueError) as fehler:
        funktion(*args)
    return str(fehler.value)


def _ohne_englisch(texte: list[str]) -> list[str]:
    return [t for t, e in zip(texte, _englisch(texte), strict=True) if not e or e == t]


def test_sign_in_and_registration_messages_have_english() -> None:
    texte = [
        _fehler(auth.validate_password, "x" * 200),
        _fehler(auth.validate_password, "kurz"),
        "Bitte gib eine gültige E-Mail-Adresse ein.",
        "Wähle ein normales, ein Pro- oder ein Ultra-Konto.", "Der Pro-Code stimmt nicht.",
        "Mit diesen Angaben lässt sich kein neues Konto anlegen. Hast du schon eins? Dann melde "
        "dich an — sonst wähle einen anderen Nutzernamen.",
        "Das bisherige Passwort stimmt nicht.",
        "Der Nutzername braucht 2 bis 40 sichtbare Zeichen.",
        "Tippe zur Bestätigung LÖSCHEN ein.",
        "(gesetzt)", "Produkt", "Aktuelle Sitzung",
        "5-Stunden-Fenster, beginnt mit deiner ersten Nachricht", "Diese Woche",
        "beginnt mit deiner nächsten Nachricht",
        "setzt sich jeden Montag um 14:30 zurück (Zeit deiner Kontoerstellung)",
        "Setzt sich in 3 Std. 20 Min. (um 18:19) zurück", "Setzt sich morgen um 14:59 zurück",
        "Setzt sich Sonntag, 29.11. um 14:59 zurück", "Aktuelle Sitzung: 42 % genutzt", *ZUSATZ,
    ]
    assert _ohne_englisch(texte) == []


def test_ai_guard_messages_and_ban_details_have_english() -> None:
    gruende = sorted({a.reason for stufe in (1, 2, 3, 4)
                      for art in ("beleidigung", "malware", "angriff", "rechtsbruch", "jailbreak")
                      for a in [aiguard.decide(art, stufe, prior=5)]
                      if a.kind == "ban"} | {aiguard.DEMEANING_REASON})
    sperre = aiguard.Ban("user:x", time.time(), "Ai-guard: schwere Beleidigung (für 1 Tag(e))",
                         "ai-guard", until=time.time() + 3 * 86400 + 5 * 3600)
    info = aiguard.ban_info(sperre)
    texte = [aiguard.BANNED_MESSAGE, aiguard.CHAT_LOCKED_MESSAGE, aiguard.WHAT_TO_DO,
             aiguard.chat_locked_message(aiguard.DEMEANING_REASON), "Dauerhaft",
             f"{info['duration']} (bis {info['until']})", info["reason"],
             "wiederholte Angriffsversuche (für immer)",
             "3 Anhaltspunkte für Missbrauch (zuletzt: malware)", *gruende]
    assert _ohne_englisch(texte) == []
    assert "bloßstellen" in aiguard.chat_locked_message(aiguard.DEMEANING_REASON)
    # Die Blase wird nie uebersetzt -- die Meldung eines gesperrten Kontos oder Chats deshalb
    # vorher.
    assert "bubble.innerHTML = md(enOderDe(message));" in SEITE


def test_more_sign_in_and_key_messages_have_english() -> None:
    from aquaticy import web
    from aquaticy.keyvault import VaultError, check_key

    def tresor(wert: str) -> str:
        with pytest.raises(VaultError) as fehler:
            check_key("MISTRAL_API_KEY", wert)
        return str(fehler.value)

    texte = [
        "Der Ultra-Code stimmt nicht.",
        "Der Einrichtungscode stimmt nicht. Er steht im Terminal, in dem Aquaticy läuft.",
        "Mit diesem Gerät bzw. diesen Angaben gibt es hier schon ein Konto — melde dich mit dem "
        "vorhandenen an. Hältst du das für einen Irrtum (zum Beispiel zwei Personen im selben "
        "Haushalt), wende dich an den Betreiber dieser Installation.",
        auth.SINGLE_TAKEN, web.WRONG_LOGIN_SINGLE, tresor("abc"), tresor("   "),
    ]
    assert _ohne_englisch(texte) == []


@pytest.mark.parametrize("frage,englisch", [
    ("Can you write me a short poem about the sea?", True),
    ("Schreib mir ein kurzes Gedicht über das Meer.", False),
])
def test_a_withdrawn_answer_follows_the_language_of_the_question(settings, frage,
                                                                 englisch) -> None:
    from aquaticy.agent import Agent, AgentResult

    aiguard.forget_judgements()
    agent = Agent(settings)
    try:
        ergebnis = agent._finish(AgentResult(
            answer="You are an idiot and a loser, shut up you stupid moron."), frage)
    finally:
        agent.close()
    erwartet = aiguard.ANSWER_REFUSAL_EN if englisch else aiguard.ANSWER_REFUSAL
    assert ergebnis.answer == erwartet
