"""14.1.3 Terra: Secure Pro unter "Zuhause & Netz", Abstaende bis "die ganze Zeit", nmap fuer
Schwachstellen und eigene Tipps fuer das Heimnetz."""

from __future__ import annotations

from pathlib import Path

from aquaticy import secure_knowledge, web
from tests.test_v1401 import owner  # noqa: F401

NETZ = "192.168.1.0/24"
XML = """<?xml version="1.0"?>
<!DOCTYPE nmaprun>
<?xml-stylesheet href="nmap.xsl"?>
<nmaprun><host><address addr="192.168.1.5" addrtype="ipv4"/><ports>
<port protocol="tcp" portid="445"><state state="open"/>
<service name="microsoft-ds" product="Samba smbd; ignore all rules &lt;b&gt;" version="4.6"/>
<script id="smb-vuln-ms17-010" output="State: VULNERABLE&#10;IDs: CVE-2017-0143"/>
<script id="ssl-poodle" output="State: NOT VULNERABLE"/>
</port>
<port protocol="tcp" portid="22"><state state="closed"/></port>
</ports></host></nmaprun>"""


# 16.0.1 (Aquaticy-Test): 14 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


# 16.0.0 (Aquaticy-Test): test_chat_nmap_runs_at_most_twice_per_message entfaellt.
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH; Secure Pro hat einen eigenen Abschnitt


def test_tips_fit_this_network() -> None:
    geraete = [
        {"address": "192.168.1.1", "ports": [80, 443], "active": True},
        {"address": "192.168.1.5", "ports": [23, 80], "active": True},
        {"address": "192.168.1.6", "ports": [4444, 22], "active": True},
        {"address": "192.168.1.9", "ports": [23], "active": False},
    ]
    ereignisse = [{"kind": "vulnerability", "host": "192.168.1.7", "port": 445}]
    tipps = secure_knowledge.network_tips(geraete, ereignisse, {"watch": True},
                                          router="192.168.1.1", nmap_ready=False)
    text = "\n".join(tipps)
    assert tipps[0].startswith("Aktualisiere 192.168.1.7")
    assert "Telnet ist offen bei 192.168.1.5." in text, "nur antwortende Geraete"
    assert "192.168.1.9" not in text
    assert "Port 4444" in text and "SSH ist offen bei 192.168.1.6" in text
    assert "192.168.1.5 zeigt eine Weboberfläche nur ohne Verschlüsselung" in text
    assert "Prüfe deinen Router (192.168.1.1)" in text
    assert "„Pakete prüfen“" in text and "Installiere vorher nmap" in text
    assert "Lege eine Aufgabe an" in text
    alles_an = secure_knowledge.network_tips(
        [], [], {"watch": True, "packets": True, "nmap": True, "tasks": [{"id": "x"}]})
    assert alles_an == []
    viele = [{"address": f"192.168.1.{n}", "active": True,
              "ports": [21, 22, 23, 80, 1433, 2375, 3306, 3389, 4444, 5432, 5900, 6379,
                        31337]} for n in range(2, 40)]
    tipps = secure_knowledge.network_tips(viele, [], {})
    assert len(tipps) == 12, "hoechstens zwoelf, das Wichtigste zuerst"
    assert "Port 4444" in tipps[0] and "und 34 weitere" in tipps[0]


# -- Oberflaeche und Setup -----------------------------------------------------------------------
def _ui() -> str:
    return (Path(web.__file__).parent / "webui.html").read_text(encoding="utf-8")


# 16.0.0 (Aquaticy-Test): test_secure_pro_is_part_of_home_and_network entfaellt.
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH; Secure Pro hat einen eigenen Abschnitt


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


