"""17.1.1: Speicher-Verbund auf Vercel -- eine Instanz ueberschreibt keine neuere Fassung mehr.

Nachgestellt: Instanz eins speichert eine Nachricht. Instanz zwei hatte eben erst nachgesehen
(weniger als PRUEF_ABSTAND vorher) und speichert dann ihren alten Stand samt eigener
Aenderung -- die Nachricht von eins war weg.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest

from aquaticy import vercel_verbund as vv
from aquaticy.auth import SEEN_INTERVAL, AuthStore
from tests.test_vercel_modus import call, vercel_app  # noqa: F401
from tests.test_vercel_verbund import (  # noqa: F401
    A,
    chat_db,
    lies,
    schluessel,
    schreibe,
    stand_aus_dem_blob,
    verbund_app,
    vier,
)


def test_a_saving_request_looks_for_newer_versions_first(schluessel: bytes,  # noqa: F811
                                                        tmp_path: Path) -> None:
    dbs = vier()
    eins = vv.Verbund(dbs, schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    zwei = vv.Verbund(dbs, schluessel, tmp_path / "zwei")  # type: ignore[arg-type]
    zwei.start_laden()
    zwei.konto_laden(A)
    assert zwei.auffrischen(jetzt=1000.0) == 0
    schreibe(chat_db(tmp_path / "eins", A), "chat-a2")
    assert eins.sichern() == 1
    # Eine Sekunde spaeter: ohne "sofort" fragt zwei noch nicht nach ...
    assert zwei.auffrischen(jetzt=1001.0) == 0
    # ... vor einer Anfrage, die speichert, schon.
    assert zwei.auffrischen(jetzt=1001.0, sofort=True) == 1
    schreibe(chat_db(tmp_path / "zwei", A), "chat-a3")
    assert zwei.sichern() == 1
    eins.auffrischen(jetzt=2000.0)
    assert lies(chat_db(tmp_path / "eins", A)) == ["chat-a1", "chat-a2", "chat-a3"]


def test_the_vercel_entry_refreshes_before_every_saving_request(
        verbund_app, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    vercel, _ = verbund_app
    assert call(vercel.app, "/")[0].startswith("200")
    gerufen: list[bool] = []
    echt = vv.Verbund.auffrischen

    def merken(self: Any, jetzt: float | None = None, sofort: bool = False) -> int:
        gerufen.append(sofort)
        return int(echt(self, jetzt, sofort))

    monkeypatch.setattr(vv.Verbund, "auffrischen", merken)
    call(vercel.app, "/api/auth/status")
    call(vercel.app, "/api/consent", method="POST", body=b'{"accepted": true}',
         headers={"Content-Type": "application/json", "Origin": "https://aquaticy.vercel.app",
                  "Sec-Fetch-Site": "same-origin"})
    assert gerufen == [False, True]


def test_a_chat_message_no_longer_rewrites_the_core(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    store = AuthStore(tmp_path / "konten", "PRO234567")
    konto = store.register("ana@example.org", "ein-langes-Passwort-42", "normal",
                           terms_accepted=True, terms_version="1", ip="198.51.100.7")

    def stand() -> tuple[Any, ...]:
        with sqlite3.connect(store.db_path) as conn:
            return tuple(conn.execute("SELECT last_ip, last_seen FROM users WHERE id=?",
                                      (konto.id,)).fetchone())

    jetzt = [time.time()]
    monkeypatch.setattr(time, "time", lambda: jetzt[0])
    store.note_seen(konto.id, "198.51.100.7")
    zuerst = stand()
    jetzt[0] += 60
    store.note_seen(konto.id, "198.51.100.7")
    assert stand() == zuerst, "dieselbe Adresse kurz danach: nichts geschrieben"
    store.note_seen(konto.id, "203.0.113.9")
    assert stand()[0] != zuerst[0], "eine neue Adresse zaehlt sofort (Sperren nach Adresse)"
    neu = stand()
    jetzt[0] += SEEN_INTERVAL + 1
    store.note_seen(konto.id, "203.0.113.9")
    assert stand()[1] > neu[1]
