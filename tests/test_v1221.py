"""12.2.1 Luna: gemeinsamer Coworker-Speicher und gezielte Besitzerfreigaben."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tests.test_agent import ScriptedLLM, _message, _tool_call


def configured(settings):
    settings.ha_url = "http://100.72.1.2:8123"
    settings.ha_token = "owner-token-123456789"
    settings.ha_control = True
    return settings


# 16.0.1 (Aquaticy-Test): 14 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_research_helper_cannot_call_unadvertised_write_tools(settings, monkeypatch):
    from aquaticy.subagents import _run_one

    llm = ScriptedLLM(
        _message(tool_calls=[_tool_call("ha_call", {"domain": "light", "service": "turn_on",
                                                  "entity_id": "light.room"}, "s1")]),
        _message(content="Keine Berechtigung."),
    )
    monkeypatch.setattr("litellm.completion", llm)
    box = SimpleNamespace(settings=settings, guard=None,
                          stats=SimpleNamespace(sources=[], searches=[]),
                          call=lambda *args: pytest.fail("nicht angebotenes Werkzeug ausgefuehrt"))
    _run_one("Licht", settings, None, None, toolbox=box)
    tool_messages = [m for call in llm.calls for m in call["messages"] if m["role"] == "tool"]
    assert any("gesperrt" in json.loads(m["content"]).get("error", "") for m in tool_messages)


