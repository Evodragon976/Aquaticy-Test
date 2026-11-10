"""15.0.0: GitHub wie Codex, Auftraege per Messenger, Klartext-Befehle, Coworker aus dem Chat
und ein besseres Secure Pro (Geraete, Namen, Sicherheitswert, Verlauf, UPnP)."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from aquaticy import addons, web
from aquaticy.config import Settings
from aquaticy.tools import Toolbox
from tests.test_v1401 import owner  # noqa: F401

TOKEN = "ghp_" + "a" * 36
BASE = "1" * 40
TREE = "2" * 40
NETZ = "192.168.1.0/24"


# -- GitHub: ein nachgebautes GitHub --------------------------------------------------------------
class FakeGitHub:
    def __init__(self) -> None:
        self.refs: dict[str, str] = {"main": BASE}
        self.calls: list[tuple[str, str, Any]] = []
        self.private = False
        self.non_ff = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        pfad = request.url.path
        daten = json.loads(request.content or b"null") if request.content else None
        self.calls.append((request.method, pfad, daten))
        if request.url.host == "codeload.github.com":
            assert "authorization" not in request.headers, "der Schluessel geht nicht mit"
            return httpx.Response(200, content=_tarball({"README.md": b"Hallo\n"}))
        assert request.url.host == "api.github.com"
        if request.method == "GET":
            if pfad == "/repos/o/r":
                return httpx.Response(200, json={"private": self.private,
                                                 "default_branch": "main"})
            if pfad.startswith("/repos/o/r/commits/"):
                return httpx.Response(200, json={"sha": BASE})
            if pfad.startswith("/repos/o/r/git/ref/heads/"):
                name = pfad.split("/git/ref/heads/", 1)[1]
                if name in self.refs:
                    return httpx.Response(200, json={"ref": f"refs/heads/{name}",
                                                     "object": {"sha": self.refs[name]}})
                return httpx.Response(404, json={})
            if pfad.startswith("/repos/o/r/git/commits/"):
                return httpx.Response(200, json={"tree": {"sha": TREE}})
            if pfad == f"/repos/o/r/tarball/{BASE}":
                return httpx.Response(302, headers={
                    "location": f"https://codeload.github.com/o/r/legacy.tar.gz/{BASE}"})
            return httpx.Response(404, json={})
        if pfad == "/repos/o/r/git/blobs":
            return httpx.Response(201, json={"sha": "3" * 40})
        if pfad == "/repos/o/r/git/trees":
            return httpx.Response(201, json={"sha": "4" * 40})
        if pfad == "/repos/o/r/git/commits":
            return httpx.Response(201, json={"sha": "5" * 40})
        if pfad == "/repos/o/r/git/refs":
            self.refs[daten["ref"].removeprefix("refs/heads/")] = daten["sha"]
            return httpx.Response(201, json={})
        if pfad.startswith("/repos/o/r/git/refs/heads/") and request.method == "PATCH":
            assert daten["force"] is False, "nie force"
            if self.non_ff:
                return httpx.Response(422, json={"message": "Update is not a fast forward"})
            self.refs[pfad.split("/refs/heads/", 1)[1]] = daten["sha"]
            return httpx.Response(200, json={})
        if pfad == "/repos/o/r/pulls":
            return httpx.Response(201, json={"number": 7, "state": "open",
                                             "html_url": "https://github.com/o/r/pull/7"})
        if pfad == "/repos/o/r/issues/5/comments":
            return httpx.Response(201, json={"id": 9, "html_url": "https://github.com/x"})
        return httpx.Response(404, json={})

    def writes(self) -> list[tuple[str, str, Any]]:
        return [c for c in self.calls if c[0] != "GET"]


def _tarball(dateien: dict[str, bytes]) -> bytes:
    puffer = io.BytesIO()
    with tarfile.open(fileobj=puffer, mode="w:gz") as tar:
        for name, inhalt in dateien.items():
            info = tarfile.TarInfo(f"o-r-123/{name}")
            info.size = len(inhalt)
            tar.addfile(info, io.BytesIO(inhalt))
    return puffer.getvalue()


@pytest.fixture
def github(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    fake = FakeGitHub()
    echt = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **kw: echt(
        *a, **{"transport": httpx.MockTransport(fake), **kw}))
    monkeypatch.setattr(addons, "_takt", lambda host, abstand=1.05: None)
    addons.install(settings, "github", pro=False)
    settings.github_token = TOKEN
    box = Toolbox(settings)
    fragen: list[str] = []
    antwort = {"text": "ja"}
    box.ask_handler = lambda frage, optionen: fragen.append(frage) or antwort["text"]
    yield box, fake, fragen, antwort
    box.close()


# 16.0.1 (Aquaticy-Test): 6 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 19 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


class FakeBox:
    """Eine VM, die nur aufzeichnet: Dateien, Befehle, Ausgaben."""

    def __init__(self, diff: list[dict[str, Any]] | None = None) -> None:
        self.gelegt: dict[str, bytes] = {}
        self.befehle: list[str] = []
        self.diff = diff or []
        self.dateien = {"/work/r/src/a.py": b"neu\n"}

    def put_bytes(self, path: str, data: bytes) -> dict[str, Any]:
        self.gelegt[path] = data
        return {"written": path}

    def run(self, command: str, timeout: int = 0) -> Any:
        self.befehle.append(command)
        if command.endswith(" diff"):
            return SimpleNamespace(exit_code=0, stdout=json.dumps({"changes": self.diff}))
        if command.endswith(" write"):
            return SimpleNamespace(exit_code=0, stdout=json.dumps({"files": 3}))
        return SimpleNamespace(exit_code=0, stdout="")

    def get_bytes(self, path: str, max_bytes: int = 0) -> bytes:
        return self.dateien[path]


# 16.0.1 (Aquaticy-Test): 5 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


def test_reading_commits_and_comparisons(settings: Settings) -> None:
    routes = {
        f"/repos/o/r/commits/{BASE}": {
            "sha": BASE, "commit": {"message": "Fix", "author": {"name": "Jonas"}},
            "parents": [{"sha": TREE}], "stats": {"additions": 1, "deletions": 0},
            "files": [{"filename": "a.py", "status": "modified", "additions": 1,
                       "deletions": 0, "patch": "+print(1)"}]},
        "/repos/o/r/compare/main...fix": {
            "status": "ahead", "ahead_by": 1, "behind_by": 0,
            "commits": [{"sha": BASE, "commit": {"message": "Fix"}}], "files": []},
        "/repos/o/r/commits": [{"sha": BASE, "commit": {"message": "Fix", "author": {}}}],
        "/repos/o/r": {"private": False},
    }

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        wert = routes.get(request.url.path)
        return httpx.Response(200, json=wert) if wert is not None else httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        commit = addons.github_call(TOKEN, "commit", repo="o/r", ref=BASE, client=client)
        assert commit["sha"] == BASE and commit["dateien"][0]["patch"] == "+print(1)"
        vergleich = addons.github_call(TOKEN, "vergleich", repo="o/r", ref="fix", base="main",
                                       client=client)
        assert vergleich["voraus"] == 1 and vergleich["commits"][0]["sha"] == BASE
        liste = addons.github_call(TOKEN, "commits", repo="o/r", client=client)
        assert liste["commits"][0]["sha"] == BASE, "voller SHA"
        assert "base" in addons.github_call(TOKEN, "vergleich", repo="o/r", ref="fix",
                                            client=client)["error"]


def test_settings_for_a_task_are_asked_first(settings) -> None:
    box = Toolbox(settings)
    try:
        fragen: list[str] = []
        box.ask_handler = lambda frage, optionen: fragen.append(frage) or "nein"
        abgelehnt = box.call("change_setting", {"setting": "sprache", "value": "en",
                                                "reason": "auftrag", "why": "englische Quellen"})
        assert "error" in abgelehnt and "englische Quellen" in fragen[0]
        box.ask_handler = lambda frage, optionen: fragen.append(frage) or "ja"
        assert box.call("change_setting", {"setting": "sprache", "value": "en",
                                           "reason": "auftrag"})["changed"]
        anzahl = len(fragen)
        assert box.call("change_setting", {"setting": "sprache", "value": "de"})["changed"]
        assert len(fragen) == anzahl, "ausdruecklich gewuenscht: keine Rueckfrage"
        assert "error" in box.call("change_setting", {"setting": "AQUATICY_LAN_ENABLED",
                                                      "value": "true", "reason": "auftrag"})
    finally:
        box.close()


# 16.0.0 (Aquaticy-Test): test_settings_show_messenger_switches entfaellt.
# Grund: virtual machine, Heimnetz, Messenger, Upgrading und Verbund sind aus der Oberflaeche
# geloescht


# -- Alte Version laeuft noch (Terminal 15.0.0, Browser 14.3.4) ----------------------------------
def test_the_running_version_is_read_from_the_page(monkeypatch) -> None:
    from aquaticy import old_server

    seite = '<script>window.__AQUATICY_VERSION__ = "14.3.4 Luna";</script>'
    echt = httpx.Client
    monkeypatch.setattr(old_server.httpx, "Client", lambda **kw: echt(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=seite)), **kw))
    assert old_server.running_version(8765) == "14.3.4 Luna"
    monkeypatch.setattr(old_server.httpx, "Client", lambda **kw: echt(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="anderes")), **kw))
    assert old_server.running_version(8765) == ""


@pytest.mark.parametrize("laeuft", ["14.3.4 Luna", "15.0.0"])
def test_web_start_replaces_another_aquaticy(monkeypatch, laeuft) -> None:
    from aquaticy import cli, old_server

    monkeypatch.setattr(old_server, "running_version", lambda port: laeuft)
    monkeypatch.setattr(old_server, "listener_pids", lambda port: [4242])
    monkeypatch.setattr(old_server, "is_aquaticy", lambda pid: True)
    beendet: list[int] = []
    monkeypatch.setattr(old_server, "stop", lambda pid: beendet.append(pid) or True)
    monkeypatch.setattr(cli.typer, "confirm", lambda *a, **kw: pytest.fail("ohne Rückfrage"))
    cli._altes_aquaticy(8765)
    assert beendet == [4242], "der andere Prozess wird beendet, der neue startet"


def test_web_start_leaves_foreign_programs_alone(monkeypatch) -> None:
    from aquaticy import cli, old_server

    monkeypatch.setattr(old_server, "running_version", lambda port: "")
    monkeypatch.setattr(old_server, "listener_pids", lambda port: [4242])
    monkeypatch.setattr(old_server, "stop", lambda pid: pytest.fail("kein Aquaticy"))
    cli._altes_aquaticy(8765)
    monkeypatch.setattr(old_server, "running_version", lambda port: "14.3.4 Luna")
    monkeypatch.setattr(old_server, "is_aquaticy", lambda pid: False)
    cli._altes_aquaticy(8765)


def test_only_aquaticy_processes_are_stopped(monkeypatch) -> None:
    import os

    from aquaticy import old_server

    assert not old_server.is_aquaticy(os.getpid()), "nie sich selbst"
    getoetet: list[int] = []
    monkeypatch.setattr(old_server, "is_aquaticy", lambda pid: False)
    monkeypatch.setattr(old_server.os, "kill", lambda pid, sig: getoetet.append(pid))
    assert old_server.stop(99999) is False and getoetet == []


def test_the_page_says_when_a_newer_version_is_installed(monkeypatch) -> None:
    from aquaticy import old_server

    monkeypatch.setattr(old_server, "installed_label", lambda: "99.0.0")
    assert web.installed_version() == "99.0.0"
    monkeypatch.setattr(old_server, "installed_label", lambda: web.VERSION_LABEL)
    assert web.installed_version() == ""
    html = (Path(web.__file__).parent / "webui.html").read_text(encoding="utf-8")
    assert "window.__AQUATICY_INSTALLED__" in html
