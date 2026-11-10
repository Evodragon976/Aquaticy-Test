"""Secure-Pro-Rolle, Netzbereich, Nachbartabelle und defensive Dienstpruefungen."""


import pytest

from aquaticy import secure_chat
from aquaticy.tools import Toolbox
from tests.test_v1300_luna import _anlegen, _zustimmung, server  # noqa: F401
from tests.test_v1401 import owner  # noqa: F401

# 16.0.1 (Aquaticy-Test): 8 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


class Connection:
    def __init__(self, data=b""):
        self.data = data
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, size):
        assert size <= 4096
        return self.data[:size]


@pytest.mark.parametrize("query", ["router 192.168.1.1", "02:aa:bb:cc:dd:02", "user@example.org",
                                  "myrouter.local CVE", "https://server/", "fe80::1234"])
def test_public_research_rejects_local_identifiers(query):
    assert not secure_chat.public_query(query)


def test_secure_tools_reject_raw_actions_and_unknown_urls(settings, monkeypatch):
    box = Toolbox(settings)
    box.secure_mode = True
    box.secure_provider = lambda *a: {"allowed": True}
    try:
        for tool in ("vm_run", "lan_ssh", "change_setting", "ha_call", "lan_scan", "fetch_page",
                     "web_search", "save_memory", "mail_draft"):
            assert "error" in box.call(tool, {})
        monkeypatch.setattr(box, "web_search", lambda *a, **kw: pytest.fail("private web query"))
        assert "error" in box.call("secure_advisories", {"query": "192.168.1.1 CVE"})
        monkeypatch.setattr(box, "fetch_page", lambda *a: pytest.fail("arbitrary URL"))
        assert "error" in box.call("secure_read_advisory", {"url": "https://example.org/"})
    finally:
        box.close()


def test_public_sources_are_bound_to_search_results(settings, monkeypatch):
    box = Toolbox(settings)
    box.secure_mode = True
    box.secure_provider = lambda *a: {"allowed": True}
    monkeypatch.setattr(box, "web_search", lambda **kw: {
        "results": [{"url": "https://vendor.example/advisory/CVE-2026-1234"}]})
    monkeypatch.setattr(box, "fetch_page", lambda url: {"url": url, "text": "Advisory"})
    try:
        result = box.call("secure_advisories", {"query": "OpenSSH 9.6p1"})
        assert result["results"]
        assert box.call("secure_read_advisory", {"url":
                        "https://vendor.example/advisory/CVE-2026-1234"})["text"] == "Advisory"
        box.secure_online = False
        assert "error" in box.call("secure_advisories", {"query": "OpenSSH"})
    finally:
        box.close()


@pytest.mark.parametrize("name,arguments", [
    ("secure_advisories", {"query": "router private-token-49387 CVE"}),
    ("secure_read_advisory", {"url": "https://vendor.example/private-token-49387"}),
])
def test_secure_research_retains_private_data_gate(settings, monkeypatch, name, arguments):
    box = Toolbox(settings)
    box.secure_mode = True
    box.untrusted_seen = True
    box.secure_provider = lambda *a: {"allowed": True}
    box._secure_sources.add("https://vendor.example/private-token-49387")
    monkeypatch.setattr(box, "_private_terms", lambda: (set(), {"private-token-49387"}))
    monkeypatch.setattr(box, "web_search", lambda *a, **kw: pytest.fail("private search"))
    monkeypatch.setattr(box, "fetch_page", lambda *a, **kw: pytest.fail("private URL"))
    try:
        result = box.call(name, arguments)
        assert result["skipped_reason"] == "private_data"
    finally:
        box.close()


# 16.0.0 (Aquaticy-Test): test_llm_gets_own_role_and_uses_defensive_tool entfaellt.
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH


# 16.0.0 (Aquaticy-Test): entfaellt:
# test_secure_chat_streams_real_model_response_and_retains_command_gate
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.0 (Aquaticy-Test): test_inspection_count_is_limited_per_question entfaellt.
# Grund: Secure Pro beantwortet nur noch Fragen: kein Netz, keine Pruefung, kein nmap, keine
# Abwehr per SSH


