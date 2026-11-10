"""Deutsche Rechtschreibung und verlustfreie Unicode-Ausgabe."""

import pytest

from aquaticy.agent import GERMAN_ORTHOGRAPHY_PROMPT, Agent
from tests.test_agent import ScriptedLLM, _message, _stream


@pytest.mark.parametrize("mode", ["normal", "pro", "code"])
def test_german_rule_reaches_every_mode_and_language_switch(settings, mode):
    agent = Agent(settings, cache=None)
    try:
        agent._apply_mode(mode)
        assert GERMAN_ORTHOGRAPHY_PROMPT in agent.messages[0]["content"]
        agent.set_answer_language("en")
        assert GERMAN_ORTHOGRAPHY_PROMPT not in agent.messages[0]["content"]
        agent.set_answer_language("de")
        assert GERMAN_ORTHOGRAPHY_PROMPT in agent.messages[0]["content"]
    finally:
        agent.close()


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


@pytest.mark.parametrize("stream", [False, True])
def test_final_answer_preserves_unicode_code_and_names(settings, monkeypatch, stream):
    text = 'Übung öffnen: äöü ÄÖÜ ß. Goethe, Queue, neue. `oeffnen = "ue"` https://x.test/ue'
    llm = ScriptedLLM(_stream(content=text) if stream else _message(content=text))
    monkeypatch.setattr("litellm.completion", llm)
    chunks = []
    agent = Agent(settings, cache=None,
                  on_event=lambda name, data: chunks.append(data["text"])
                  if name == "answer_chunk" else None)
    try:
        answer = agent._final_answer(stream=stream)
        assert answer.strip() == text
        assert "".join(chunks).strip() == text
        assert GERMAN_ORTHOGRAPHY_PROMPT in llm.calls[0]["messages"][0]["content"]
    finally:
        agent.close()
