"""9.6.8 Ultra: Fehlerkorrekturen zu Sol -- Start, Offline-Hinweis, Abgabe im
Verbund und technische Fehlertexte im Chat."""

from __future__ import annotations

import json

from aquaticy import web
from tests.test_version import LABEL


def test_version_label() -> None:
    import aquaticy

    assert aquaticy.VERSION_LABEL == LABEL


def _fehler(art: type[BaseException], text: str) -> BaseException:
    try:
        raise art(text)
    except BaseException as exc:
        return exc


def test_library_errors_never_reach_the_chat() -> None:
    try:
        int("abc")
    except ValueError as exc:
        assert web.user_hint(exc) == web.GENERIC_ERROR
    try:
        b"\xff".decode("utf-8")
    except UnicodeDecodeError as exc:
        assert web.user_hint(exc) == web.GENERIC_ERROR
    try:
        json.loads("nicht json")
    except ValueError as exc:
        assert web.user_hint(exc) == web.GENERIC_ERROR
    assert web.user_hint(_fehler(RuntimeError, "Das sieht aus wie ein Satz.")) \
        == web.GENERIC_ERROR
    assert web.user_hint(_fehler(ValueError, "Antwort 500")) == web.GENERIC_ERROR
    assert web.user_hint(_fehler(ValueError, "could not convert string to float: 'x'")) \
        == web.GENERIC_ERROR


def test_intended_hints_still_reach_the_chat() -> None:
    satz = "Nutzung: /image pfad/zum/bild.jpg (oder .png)"
    assert web.user_hint(_fehler(ValueError, satz)) == satz
    assert web.user_hint(_fehler(FileNotFoundError, "Bild nicht gefunden: x.png")) \
        == "Bild nicht gefunden: x.png"

    assert web.user_hint(_fehler(ValueError, ".env ist kein Bild (.png).")) \
        == ".env ist kein Bild (.png)."

    from aquaticy.calc import CalcError

    assert web.user_hint(_fehler(CalcError, "Durch null teilen geht nicht.")) \
        == "Durch null teilen geht nicht."


# 16.0.1 (Aquaticy-Test): 3 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_offline_shows_the_banner_not_the_error_window() -> None:
    html = web.UI_FILE.read_text(encoding="utf-8")
    assert "grund.gezeigt || grund.netz" in html
    rejection = html[html.index('window.addEventListener("unhandledrejection"'):]
    assert rejection.index("if (!navigator.onLine) return;") < rejection.index("zeigeFehler();")
    assert 'err.netz = true; } catch {}\n        $("#offline-hinweis").hidden = false;' in html
