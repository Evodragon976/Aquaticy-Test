"""15.5.6: Meldungen von Secure Pro und Coworkern auch an die eingetragenen Nummern."""

from __future__ import annotations

import pytest

# 16.0.1 (Aquaticy-Test): 10 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


NUMMERN = ["+49 151 2345678", "0049 160 1111111", "Anna", "0151 999", "+49 170 00000000"]


def test_an_old_server_behind_a_login_page_is_stopped_too(monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import cli, old_server

    beendet: list[int] = []
    monkeypatch.setattr(old_server, "running_version", lambda port: "")  # nur Anmeldeseite
    monkeypatch.setattr(old_server, "listener_pids", lambda port: [4242])
    monkeypatch.setattr(old_server, "is_aquaticy", lambda pid: True)
    monkeypatch.setattr(old_server, "stop", lambda pid: beendet.append(pid) or True)
    cli._altes_aquaticy(8765)
    assert beendet == [4242]


def test_foreign_programs_on_the_port_stay_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import cli, old_server

    beendet: list[int] = []
    monkeypatch.setattr(old_server, "running_version", lambda port: "")
    monkeypatch.setattr(old_server, "listener_pids", lambda port: [4242])
    monkeypatch.setattr(old_server, "is_aquaticy", lambda pid: False)
    monkeypatch.setattr(old_server, "stop", lambda pid: beendet.append(pid) or True)
    cli._altes_aquaticy(8765)
    assert beendet == []
