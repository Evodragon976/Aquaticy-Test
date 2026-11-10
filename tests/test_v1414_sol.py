"""Freigabeentzug, begrenzte Prozesse, Paketdaten und vollstaendige Warnungen."""

import struct

import pytest

from aquaticy.tools import Toolbox
from tests.test_v1401 import owner  # noqa: F401
from tests.test_v1413_luna import _eth, _ipv4

# 16.0.1 (Aquaticy-Test): 14 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


# 16.0.0 (Aquaticy-Test): test_custom_ssh_port_cannot_be_blocked entfaellt.
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH


def tcp_frame(src="192.168.1.2", dst="192.168.1.1"):
    tcp = struct.pack("!HHIIBBHHH", 50000, 4444, 0, 0, 0x50, 0x02, 0, 0, 0)
    return _eth(0x0800, _ipv4(src, dst, 6, tcp))


@pytest.mark.parametrize("tool", ["secure_advisories", "secure_read_advisory"])
def test_observed_dns_names_do_not_leave_in_public_research(settings, monkeypatch, tool):
    box = Toolbox(settings)
    domain = "qxzkvbtrplmnwshgd7k2.example.com"
    box.secure_mode = True
    box.untrusted_seen = True
    # 16.0.1 (Aquaticy-Test): Die Netzueberwachung (secure_provider) gibt es nicht mehr. Der
    # Schutz gilt weiter fuer jeden Namen, den Secure Pro sich gemerkt hat.
    box.remember_secure_dns({"domains": [domain]})
    url = "https://vendor.example/report?domain=" + domain
    box._secure_sources.add(url)
    monkeypatch.setattr(box, "web_search", lambda *a, **kw: pytest.fail("private DNS search"))
    monkeypatch.setattr(box, "fetch_page", lambda *a: pytest.fail("private DNS URL"))
    try:
        arguments = {"query": domain} if tool == "secure_advisories" else {"url": url}
        assert box.call(tool, arguments)["skipped_reason"] == "private_data"
        box.remember_secure_dns({"domains": []})
        assert box.call(tool, arguments)["skipped_reason"] == "private_data"
    finally:
        box.close()


# 16.0.0 (Aquaticy-Test): entfaellt:
# test_dns_names_from_status_are_registered_before_public_research
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH


