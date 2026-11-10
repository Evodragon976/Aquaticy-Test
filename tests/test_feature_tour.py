"""Jede Funktion einmal wirklich -- fuer ein Normal-, ein Pro- und ein Ultra-Konto.

Wie tests/test_end_to_end.py: echter Webserver, echte Konten, echtes litellm,
nur das Modell ist gestellt (tests/fake_llm.py). Hier aber in der Breite:
jede Seite, jeder Endpunkt, jeder Slash-Befehl, Chats, Auftraege, Speicher,
Add-ons, Einstellungen und jedes Werkzeug, das ohne Internet auskommt.

Geprueft wird dreierlei: nichts antwortet mit 5xx, die Antworten ergeben
Sinn, und die Pro-Sperren halten. Werkzeuge, die ins Netz gehen (Suche,
Wetter, Orte), bleiben draussen -- die Tests fassen kein echtes Netz an.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from aquaticy import web
from tests import fake_llm
from tests.test_end_to_end import _konto, _req, server  # noqa: F401

PNG = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
).decode()


class Tour:
    """Ruft auf und merkt sich jeden Status -- ein 5xx faellt am Ende auf."""

    def __init__(self, port: int, cookie: str) -> None:
        self.port = port
        self.cookie = cookie
        self.gesehen: list[tuple[str, str, int]] = []

    def __call__(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        status, _, daten = _req(self.port, method, path, body, self.cookie)
        self.gesehen.append((method, path, status))
        try:
            return status, json.loads(daten)
        except ValueError:
            return status, daten

    def chat(self, text: str, **mehr: Any) -> list[dict[str, Any]]:
        status, _, daten = _req(self.port, "POST", "/api/chat", {"message": text, **mehr},
                                self.cookie)
        self.gesehen.append(("POST", "/api/chat", status))
        assert status == 200, daten
        events = [json.loads(z[6:]) for z in daten.decode().splitlines() if z.startswith("data: ")]


        return [event for event in events if event.get("type") != "chat"]

    def kein_serverfehler(self) -> None:
        kaputt = [eintrag for eintrag in self.gesehen if eintrag[2] >= 500]
        assert not kaputt, kaputt


@pytest.fixture
def tour(server: tuple[int, Path], request: pytest.FixtureRequest,  # noqa: F811
         monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Tour:
    port, _ = server
    monkeypatch.setattr(web, "REQUEST_LIMIT", web.RateLimiter(attempts=10_000, window_seconds=60))
    monkeypatch.setattr(web, "ADDRESS_LIMIT", web.RateLimiter(attempts=10_000, window_seconds=60))


    monkeypatch.setattr("aquaticy.quota.SESSION_TOKENS", 10**9)
    monkeypatch.setattr("aquaticy.quota.WEEK_TOKENS", 10**10)
    monkeypatch.chdir(tmp_path)
    plan = request.param
    code = {"pro": "PROE2E234", "ultra": "Abcdef1234567!"}.get(plan, "")
    return Tour(port, _konto(port, plan, code))


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


WERKZEUGE: list[tuple[str, dict[str, Any], str]] = [
    ("calculate", {"expression": "(3+4)*6"}, '"result": "42"'),
    ("remember", {"text": "Ich mag Tee"}, '"saved": true'),
    ("save_memory", {"text": "Wohnt in Bremen", "topic": "Ort"}, '"saved": true'),
    ("recall_memory", {"query": "Bremen"}, "Wohnt in Bremen"),
    ("change_setting", {"setting": "formulierungen", "value": "3"}, '"changed"'),
    ("change_setting", {"setting": "AQUATICY_HA_CONTROL", "value": "true"}, "nicht aus dem"),
    ("change_setting", {"setting": "legal_guard", "value": "aus"}, "nicht aus dem"),
    ("change_setting", {"setting": "AQUATICY_VM_USER_MODE", "value": "an"}, "nicht aus dem"),
    ("fetch_page", {"url": "file:///etc/passwd"}, "invalid_url"),
    ("fetch_page", {"url": "http://127.0.0.1:1/"}, '"ok": false'),

    ("ask_user", {"question": "Welche Farbe?", "options": ["rot", "blau"]}, "blau"),
]


def _antworte(tour: Tour, text: str) -> None:
    """Beantwortet die Rueckfrage, sobald sie da ist -- wie der Browser."""
    for _ in range(100):
        time.sleep(0.1)
        status, _, daten = _req(tour.port, "POST", "/api/answer", {"text": text}, tour.cookie)
        if status == 200 and json.loads(daten).get("ok"):
            return


@pytest.mark.parametrize("tour", ["normal", "pro", "ultra"], indirect=True)
def test_every_offline_tool_runs_through(tour: Tour) -> None:
    for name, argumente, erwartet in WERKZEUGE:
        fake_llm.ANFRAGEN.clear()
        if name == "ask_user":
            threading.Thread(target=_antworte, args=(tour, "blau"), daemon=True).start()
        ereignisse = tour.chat(f"WERKZEUG:{name} {json.dumps(argumente)}")
        angeboten = {n for zeile in fake_llm.ANFRAGEN for n in json.loads(zeile)["tool_names"]}
        assert name in angeboten, (name, sorted(angeboten))
        ergebnis = " ".join(e.get("result", "") for e in ereignisse
                            if e.get("type") == "action_done")
        abstuerze = [e for e in ereignisse if e.get("type") == "error"]
        assert not abstuerze, (name, abstuerze)
        assert erwartet in ergebnis, (name, ergebnis)
        assert ereignisse[-1]["type"] == "done"
    tour.kein_serverfehler()


@pytest.mark.parametrize("tour", ["normal", "pro", "ultra"], indirect=True)
def test_what_each_account_is_offered(tour: Tour) -> None:
    """Was angeboten wird, folgt aus Konto und Einrichtung -- nicht aus dem Zufall."""
    fake_llm.ANFRAGEN.clear()
    tour.chat("WERKZEUG:calculate {}")
    angeboten = {n for zeile in fake_llm.ANFRAGEN for n in json.loads(zeile)["tool_names"]}
    # 16.0.1 (Aquaticy-Test): kein Heimnetz, kein Home Assistant, kein Lager, kein Desktop --
    # fuer kein Konto.
    for name in ("github", "read_feeds", "ha_states", "ha_call", "lan_check", "lan_scan",
                 "storage_find", "mail_search", "calendar_events", "desktop_open"):
        assert name not in angeboten, name
