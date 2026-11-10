"""Rechte je Add-on (9.5.10) -- einfach einzustellen, im Code durchgesetzt.

Geprueft wird nicht, ob die Einstellung gespeichert wird, sondern ob sie
WIRKT: ein Messenger auf "Nur lesen" tippt und sendet nichts, auch wenn das
Bildmodell "harmlos" sagt; "Nur Einzelchats" schreibt in keine Gruppe, auch
nicht in eine, die nicht sicher als Einzelchat zu erkennen ist; GitHub auf
"Nur öffentliche" liest kein privates Repo -- geprueft bei GitHub.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest

from aquaticy import addons
from aquaticy.config import Settings


@pytest.fixture
def konto(tmp_path: Path) -> Settings:
    ordner = tmp_path / "konto"
    ordner.mkdir()
    return Settings(data_dir=ordner, env_path=ordner / ".env", vm_user_mode=True)


def _an(konto: Settings, *ids: str) -> None:
    for addon_id in ids:
        addons._update(konto, addon_id, installed=True, enabled=True)


def test_every_addon_has_simple_rights() -> None:


    assert not any(addon_id in addons.RIGHTS for addon_id in addons.MODEL_ADDONS)
    for addon_id in set(addons.CATALOG) - addons.MODEL_ADDONS:
        rechte = addons.RIGHTS[addon_id]
        assert 1 <= len(rechte) <= 2, "einfach: ein, zwei Fragen je Add-on"
        for recht in rechte:
            assert 2 <= len(recht.options) <= 3
            assert recht.default in dict(recht.options)


# 16.0.1 (Aquaticy-Test): 7 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.0 (Aquaticy-Test): test_the_window_shows_rights_with_their_dependency entfaellt.
# Grund: WhatsApp, Signal und Blender brauchen die virtual machine und sind geloescht


# 16.0.0 (Aquaticy-Test): test_the_prompt_knows_the_rights entfaellt.
# Grund: WhatsApp, Signal und Blender brauchen die virtual machine und sind geloescht


def _github(antworten: dict[str, Any], gefragt: list[httpx.Request]) -> httpx.Client:
    def handler(anfrage: httpx.Request) -> httpx.Response:
        gefragt.append(anfrage)
        pfad = anfrage.url.path
        for anfang, antwort in antworten.items():
            if pfad == anfang:
                return httpx.Response(200, json=antwort)
        return httpx.Response(404, json={})

    return httpx.Client(transport=httpx.MockTransport(handler))


TOKEN = "ghp_" + "r" * 36


def test_public_only_hides_private_repos_everywhere() -> None:
    gefragt: list[httpx.Request] = []
    client = _github({
        "/user/repos": [{"full_name": "a/offen", "private": False},
                        {"full_name": "a/geheim", "private": True}],
        "/repos/a/geheim": {"private": True},
        "/repos/a/offen": {"private": False, "full_name": "a/offen"},
        "/search/issues": {"items": []},
    }, gefragt)
    repos = addons.github_call(TOKEN, "repos", client=client, nur_oeffentlich=True)
    assert [r["name"] for r in repos["repos"]] == ["a/offen"]
    assert gefragt[-1].url.params["visibility"] == "public"
    antwort = addons.github_call(TOKEN, "issues", repo="a/geheim", client=client,
                                 nur_oeffentlich=True)
    assert "privat" in antwort["error"]
    assert gefragt[-1].url.path == "/repos/a/geheim", "nach der Pruefung nichts mehr gelesen"
    assert addons.github_call(TOKEN, "repo", repo="a/offen", client=client,
                              nur_oeffentlich=True)["name"] == "a/offen"
    addons.github_call(TOKEN, "suche", query="bug", client=client, nur_oeffentlich=True)
    assert gefragt[-1].url.params["q"].endswith("is:public")


def test_overview_only_reads_no_file_contents() -> None:
    import base64

    gefragt: list[httpx.Request] = []
    client = _github({
        "/repos/a/b/contents/": [{"name": "src", "type": "dir"}],
        "/repos/a/b/contents/src": [{"name": "x.py", "type": "file", "size": 3}],
        "/repos/a/b/contents/src/x.py": {"encoding": "base64", "size": 3,
                                          "content": base64.b64encode(b"geheim").decode()},
    }, gefragt)
    ordner = addons.github_call(TOKEN, "datei", repo="a/b", path="src", client=client,
                                inhalte=False)
    assert ordner["eintraege"][0]["name"] == "x.py"
    datei = addons.github_call(TOKEN, "datei", repo="a/b", path="src/x.py", client=client,
                               inhalte=False)
    assert "text" not in datei and "geheim" not in json.dumps(datei)
    assert all(r.url.path != "/repos/a/b/contents/src/x.py" for r in gefragt)


# 16.0.0 (Aquaticy-Test): test_blender_scripts_only_keeps_the_window_closed entfaellt.
# Grund: WhatsApp, Signal und Blender brauchen die virtual machine und sind geloescht


class Box:
    """Die virtual machine: vorn ist das Fenster, das der Test will."""

    def __init__(self, klasse: str = "Navigator.aquaticy-whatsapp",
                 titel: str = "WhatsApp") -> None:
        self.klasse, self.titel = klasse, titel
        self.aufrufe: list[tuple[str, ...]] = []

    def screenshot(self, **kwargs: Any) -> bytes:
        return b"\xff\xd8JPEG"

    def desktop(self, *args: str, stdin: bytes | None = None, timeout: float = 60):
        self.aufrufe.append(args)
        antwort: dict[str, Any] = {"ok": True, "fenster": self.titel}
        if args[0] == "windows":
            antwort = {"fenster": [{"id": "0x1", "klasse": self.klasse, "titel": self.titel}],
                       "aktiv": self.titel, "aktiv_klasse": self.klasse}
        return subprocess.CompletedProcess(args, 0, json.dumps(antwort).encode(), b"")

    def handgriffe(self) -> list[str]:
        return [a[0] for a in self.aufrufe if a[0] != "windows"]


class Auge:
    """Das Bildmodell: sagt, was der Test will -- auch fuer den Chat."""

    def __init__(self, art: str = "harmlos", gruppe: Any = False, chat: str = "Mama") -> None:
        self.art, self.gruppe, self.chat = art, gruppe, chat
        self.fragen: list[str] = []

    def __call__(self, bild: bytes, prompt: str) -> str:
        self.fragen.append(prompt)
        if "Messenger" in prompt:
            return json.dumps({"chat": self.chat, "gruppe": self.gruppe})
        if "Eingabefeld" in prompt:
            return json.dumps({"feld": "sonstiges", "art": "harmlos"})
        if "Finde dieses Element" in prompt:
            return json.dumps({"gefunden": True, "x": 900, "y": 700, "was": "Senden-Knopf",
                               "art": self.art})
        return json.dumps({"was": "Nachricht abschicken", "art": self.art})


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


# 16.0.0 (Aquaticy-Test): test_single_chats_only_refuses_groups_and_unclear_chats entfaellt.
# Grund: WhatsApp, Signal und Blender brauchen die virtual machine und sind geloescht


# 16.0.0 (Aquaticy-Test): test_groups_allowed_still_asks_before_sending entfaellt.
# Grund: WhatsApp, Signal und Blender brauchen die virtual machine und sind geloescht


# 16.0.0 (Aquaticy-Test): test_changing_rights_keeps_the_workshop_running entfaellt.
# Grund: WhatsApp, Signal und Blender brauchen die virtual machine und sind geloescht


# 16.0.0 (Aquaticy-Test): test_the_agent_prompt_follows_the_rights entfaellt.
# Grund: WhatsApp, Signal und Blender brauchen die virtual machine und sind geloescht


def test_the_ui_has_simple_rights() -> None:
    from aquaticy import web

    html = web.UI_FILE.read_text(encoding="utf-8")
    for teil in ("function addonRechte", 'action: "rights"', "role\", \"radiogroup",
                 ".seg button.on"):
        assert teil in html, teil
