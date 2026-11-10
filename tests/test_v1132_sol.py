"""11.3.2 Sol: LiteLLM 1.106.0 ohne `mcp`, und was die Pruefung danach fand."""

from __future__ import annotations

import pytest

from aquaticy import llmcall
from tests.test_web import client, session, web_settings  # noqa: F401

WERKZEUG = [{"type": "function", "function": {"name": "f", "parameters": {"type": "object"}}}]


@pytest.fixture(autouse=True)
def _frisch(monkeypatch):
    monkeypatch.setattr(llmcall, "_OHNE_MCP", False)


def _wie_litellm_1106(aufrufe: list[dict]):
    """Greift bei Werkzeugen nach `mcp` -- ausser mit _skip_mcp_handler."""
    def completion(**kwargs):
        aufrufe.append(dict(kwargs))
        if kwargs.get("tools") and not kwargs.get("_skip_mcp_handler"):
            raise ModuleNotFoundError("No module named 'mcp'", name="mcp")
        return "antwort"
    return completion


def test_a_missing_mcp_package_no_longer_breaks_every_question(monkeypatch) -> None:
    import litellm

    aufrufe: list[dict] = []
    monkeypatch.setattr(litellm, "completion", _wie_litellm_1106(aufrufe))
    assert llmcall.completion(model="mistral/m", messages=[], tools=WERKZEUG) == "antwort"
    assert [a.get("_skip_mcp_handler") for a in aufrufe] == [None, True]

    aufrufe.clear()
    assert llmcall.completion(model="mistral/m", messages=[], tools=WERKZEUG) == "antwort"
    assert [a.get("_skip_mcp_handler") for a in aufrufe] == [True]

    aufrufe.clear()
    llmcall.completion(model="mistral/m", messages=[])
    assert "_skip_mcp_handler" not in aufrufe[0]


@pytest.mark.parametrize("fehler", [ModuleNotFoundError("No module named 'x'", name="x"),
                                    ValueError("mcp")])
def test_other_errors_are_not_hidden(monkeypatch, fehler) -> None:
    import litellm

    def completion(**kwargs):
        raise fehler
    monkeypatch.setattr(litellm, "completion", completion)
    with pytest.raises(type(fehler)):
        llmcall.completion(model="mistral/m", messages=[], tools=WERKZEUG)
    assert llmcall._OHNE_MCP is False


def test_the_agent_and_the_meter_go_through_llmcall() -> None:
    import inspect

    from aquaticy import agent, local_model, metering

    assert "llmcall.completion(" in inspect.getsource(agent.Agent._completion)
    assert "llmcall.completion(**kwargs)" in inspect.getsource(metering)
    assert "llmcall.completion(" in inspect.getsource(local_model.verify_tool_calling)


def test_the_broken_litellm_is_excluded() -> None:
    import tomllib
    from pathlib import Path

    from packaging.requirements import Requirement

    text = (Path(llmcall.__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    requirements = [Requirement(value) for value in tomllib.loads(text)["project"]["dependencies"]]
    sdk = next(requirement for requirement in requirements if requirement.name == "litellm")
    for unsafe in ("1.102.1", "1.103.0", "1.106.0", "2.0.0"):
        assert unsafe not in sdk.specifier
    assert "1.102.2" in sdk.specifier


def test_the_slider_minimum_is_accepted_by_the_server(monkeypatch, tmp_path) -> None:
    from aquaticy import local_model, web
    from aquaticy.config import Settings


    monkeypatch.setattr(local_model, "kv_bytes_per_token", lambda *a, **k: 5 * 1024 ** 3 // 1536)
    monkeypatch.setattr(local_model, "trained_context", lambda *a, **k: 0)
    s = Settings(model="ollama_chat/riesig:405b", context_tokens=16384, data_dir=tmp_path)
    sicht = web.context_view(s, s.model)
    assert sicht["max"] == 1024 and sicht["min"] <= 1024
    unten, oben = web.NUMBERS["AQUATICY_CONTEXT_TOKENS"]
    assert unten <= sicht["min"] and oben >= sicht["max"]


SCHWACH = {"cores": 4, "cpu_pct": 30, "ram_gb": 8, "ram_used_gb": 3, "ram_pct": 37,
           "ollama_models": 0}
STARK = {"cores": 16, "cpu_pct": 10, "ram_gb": 64, "ram_used_gb": 20, "ram_pct": 31,
         "gpu": "RTX 4090", "vram_gb": 24, "vram_used_gb": 4, "gpu_pct": 12, "ollama_models": 3}


@pytest.fixture
def staerken(tmp_path):
    """Master A ist schwach (nur Website), Mitglied B hat eine starke Grafikkarte."""
    import time as zeit

    from aquaticy import cluster
    from tests.test_cluster import Netz, _konto, _store, _verbinden

    netz = Netz()
    neustarts: list[str] = []
    gefragt: list[dict] = []
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    _konto(_store(a_dir), "anna@example.org")
    _konto(_store(b_dir), "bert@example.org")
    lokal = lambda user: user.startswith("lokal")  # noqa: E731
    a = cluster.Cluster(a_dir, port=1001, transport=netz, hooks=cluster.Hooks(
        restart=lambda: neustarts.append("a"), hardware=lambda: SCHWACH, wants_models=lokal))
    b = cluster.Cluster(b_dir, port=1002, transport=netz, hooks=cluster.Hooks(
        restart=lambda: neustarts.append("b"), ask=gefragt.append, hardware=lambda: STARK,
        wants_models=lokal))
    netz.knoten = {1001: a, 1002: b}
    for c in (a, b):
        c.state["enabled"] = True
    _verbinden(a, b, gefragt, neustarts)
    b.sync_once()
    a.sync_once()
    a.last_ok[b.node_id] = zeit.time()
    return a, b


# 16.0.1 (Aquaticy-Test): 8 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


def test_a_burst_of_connections_does_not_stall() -> None:
    """Beim Laden oeffnet die Seite zwoelf Anfragen auf einmal; mit der Standard-
    Warteschlange (5) hingen einzelne davon 30 s und mehr (Rundgang, 11.3.2 Sol)."""
    import socket
    import time

    from aquaticy import web

    assert web.AquaticyServer.request_queue_size >= 64
    server = web.AquaticyServer(("127.0.0.1", 0), web.Handler)
    verbindungen = []
    try:
        anfang = time.monotonic()
        for _ in range(40):
            verbindung = socket.create_connection(server.server_address, timeout=2)
            verbindungen.append(verbindung)
        assert time.monotonic() - anfang < 2, "jeder Verbindungsaufbau sofort angenommen"
    finally:
        for verbindung in verbindungen:
            verbindung.close()
        server.server_close()
