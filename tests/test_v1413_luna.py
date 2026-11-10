"""14.1.3 Luna: Secure Pro ueberwacht, kennt Malware, prueft Pakete und wehrt per SSH ab.

Dazu: Aufgaben wie "Melde dich bei neuen Geraeten", Zeitplan wie bei Coworkern, nur Wichtiges
geht in Chat und Messenger. Die Einstellungen sind aufgeraeumt, und das Setup fragt nicht mehr
nach den Agenten.
"""

from __future__ import annotations

import re
import socket
import struct
from pathlib import Path
from typing import Any

from aquaticy import secure_knowledge, web
from aquaticy.cache import Cache
from aquaticy.tools import Toolbox
from tests.test_v1300_luna import server  # noqa: F401
from tests.test_v1401 import owner  # noqa: F401

NETZ = "192.168.1.0/24"


# 16.0.1 (Aquaticy-Test): 25 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


# -- Paket-Kopfdaten ----------------------------------------------------------------------------
def _eth(art: int, nutzlast: bytes) -> bytes:
    return b"\xff" * 6 + b"\x02\x00\x00\x00\x00\x01" + struct.pack("!H", art) + nutzlast


def _ipv4(src: str, dst: str, proto: int, rest: bytes) -> bytes:
    kopf = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(rest), 0, 0, 64, proto, 0,
                       socket.inet_aton(src), socket.inet_aton(dst))
    return kopf + rest


# -- Wissen ---------------------------------------------------------------------------------------
def test_knowledge_explains_ports_malware_and_weaknesses() -> None:
    assert secure_knowledge.port_info(4444)["art"] == "verdächtig"
    assert "Ransomware" in secure_knowledge.port_info(3389)["text"]
    assert secure_knowledge.port_info(443) == {}
    treffer = secure_knowledge.lookup("Port 31337")["results"]
    assert treffer[0]["name"] == "Back Orifice"
    assert any("Mirai" in r.get("name", "") for r in secure_knowledge.lookup("mirai")["results"])
    assert any(r["art"] == "schwachstelle" for r in secure_knowledge.lookup("UPnP")["results"])
    assert "error" in secure_knowledge.lookup("  ")
    assert len(secure_knowledge.topics()["malware"]) >= 8


def _box(settings, vm: dict[str, Any]) -> tuple[Toolbox, list[dict[str, Any]]]:
    box = Toolbox(settings)
    box.secure_mode = True
    box.secure_provider = lambda name, args: vm if name == "secure_vm" else {"allowed": True}
    aufrufe: list[dict[str, Any]] = []
    box.lan_ssh = lambda **kw: aufrufe.append(kw) or {"exit_code": 0}  # type: ignore[method-assign]
    return box, aufrufe


# 16.0.0 (Aquaticy-Test): test_defense_needs_the_vm_switch entfaellt.
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH


# 16.0.0 (Aquaticy-Test): test_defense_runs_the_built_command_through_ssh entfaellt.
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH


# 16.0.0 (Aquaticy-Test): test_defense_tools_are_offered_only_when_allowed entfaellt.
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH


def test_latest_secure_chat(tmp_path: Path) -> None:
    cache = Cache(tmp_path / "db.sqlite")
    assert cache.latest_secure_chat() == ""
    cache.mark_secure_chat("alt")
    cache.add_history("alt", "a", "b")
    cache.mark_secure_chat("neu")
    cache.add_history("neu", "a", "b")
    assert cache.latest_secure_chat() == "neu"


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# -- Oberflaeche ----------------------------------------------------------------------------------
def _ui() -> str:
    return (Path(web.__file__).parent / "webui.html").read_text(encoding="utf-8")


def test_settings_are_grouped() -> None:
    html = _ui()
    formular = html[html.index('<form id="settings">'):html.index('id="savenote"')]
    legenden = re.findall(r"<legend>(.*?)</legend>", formular)
    # 16.0.0 (Aquaticy-Test): ohne Mitlesen, Auslastung, Zuhause & Netz, VM und Messenger;
    # Add-ons und Secure Pro (nur Fragen) haben eigene Abschnitte.
    # 16.0.2 (Aquaticy-Test): ohne Gemeinsames Lernen und ohne Helfer & Grenzen.
    assert legenden == ["Konto", "Nutzung", "Speicher", "Ort &amp; Sprache", "Suche",
                        "Gmail &amp; Kalender", "Add-ons", "Secure Pro", "Dev settings"]

    def abschnitt(legende: str) -> str:
        start = formular.index(f"<legend>{legende}</legend>")
        return formular[start:formular.index("</fieldset>", start)]

    # 16.0.0 (Aquaticy-Test): Secure Pro hat einen eigenen Abschnitt und nur noch den Chat.
    secure = abschnitt("Secure Pro")
    assert 'id="secure-open"' in secure
    for weg in ("secure-setting", "secure-interval", "secure-nmap", "secure-vm", "lanon"):
        assert f'id="{weg}"' not in html, weg
    assert 'id="secure-status"' not in html, "Status zeigt die Seite ohnehin laufend"
    assert 'id="pw"' in abschnitt("Suche")
    assert "OpenSSH" not in formular
    dev = abschnitt("Dev settings")
    assert 'id="secure-setting"' not in dev and 'id="voice-setting"' not in dev
    assert dev.index('id="legalguard"') < dev.index('id="legal-rules"') < dev.index(
        'id="automodel"'), "die Leitplanken stehen bei ihren Regeln"
    assert formular.count('href="/privacy"') == 1, "der Datenschutz-Link stand doppelt da"


