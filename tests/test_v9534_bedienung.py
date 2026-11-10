"""9.5.34 (intern): VM-Netz je Tarif, Modellmenue unten, Bilderstellung, Antwortpruefung."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from aquaticy import agent as agent_module  # noqa: F401
from aquaticy import web
from aquaticy.agent import Agent
from aquaticy.aiguard import ANSWER_REFUSAL, answer_problem
from aquaticy.config import Settings


def _message(content: str = "", tool_calls: list[Any] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


class ScriptedLLM:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("mehr LLM-Aufrufe als vorbereitete Antworten")
        return self.responses.pop(0)


def _agent(settings: Settings) -> tuple[Agent, list[tuple[str, dict[str, Any]]]]:
    ereignisse: list[tuple[str, dict[str, Any]]] = []
    agent = Agent(settings, cache=None, on_event=lambda n, p: ereignisse.append((n, p)))
    return agent, ereignisse


def _laufzeit() -> Any:
    return SimpleNamespace(binary="docker", extra=[], label="test")


def _flags(**kwargs: Any) -> list[str]:
    from aquaticy.sandbox import Sandbox

    box = Sandbox(**kwargs)
    box.runtime = _laufzeit()
    box._name, box._volume = "kiste", "datentraeger"
    return box._run_flags()


# 16.0.1 (Aquaticy-Test): 9 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


def test_the_model_cannot_switch_the_lan_on() -> None:
    from aquaticy import preferences

    assert "AQUATICY_VM_LAN" in preferences.PROTECTED


def test_an_insulting_answer_is_withdrawn(monkeypatch: pytest.MonkeyPatch,
                                          settings: Settings) -> None:
    monkeypatch.setattr("litellm.completion", ScriptedLLM(
        _message(content="Du bist ein Idiot und ein Versager, halt die Klappe.")))
    agent, ereignisse = _agent(settings)
    result = agent.ask("Wie geht das?", stream=False)
    assert result.answer == ANSWER_REFUSAL
    assert "kann ich nicht helfen" in result.answer
    assert any(n == "answer_reset" and p.get("reason") == "antwort_geprueft"
               for n, p in ereignisse)

    assert agent.messages[-1]["content"] == ANSWER_REFUSAL


def test_a_normal_answer_passes(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setattr("litellm.completion", ScriptedLLM(
        _message(content="Die Hauptstadt von Frankreich ist Paris.")))
    agent, ereignisse = _agent(settings)
    result = agent.ask("Hauptstadt von Frankreich?", stream=False)
    assert "Paris" in result.answer
    assert not any(n == "answer_reset" for n, _ in ereignisse)


def test_the_answer_check_can_be_switched_off_by_the_operator(
        monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    settings.answer_check = False
    monkeypatch.setattr("litellm.completion", ScriptedLLM(
        _message(content="Du bist ein Idiot und ein Versager, halt die Klappe.")))
    agent, _ = _agent(settings)
    assert agent.ask("Hallo zusammen", stream=False).answer != ANSWER_REFUSAL


def test_quoting_an_insult_in_an_explanation_is_fine() -> None:
    assert answer_problem('Ist "du Idiot" eine Beleidigung? Ja, nach § 185 StGB.') == ""
    assert answer_problem(
        "Der Pirat rief: du Idiot, das Schiff sinkt! Dann segelte er weiter.") == ""


def test_the_model_judges_risky_topics_only() -> None:
    aufrufe: list[str] = []

    def urteil(prompt: str, settings: Any) -> str:
        aufrufe.append(prompt)
        return json.dumps({"missbrauch": True, "art": "Schadsoftware"})


    assert answer_problem("Heute scheint die Sonne und es ist warm draußen.", object(),
                          ask=urteil) == ""
    assert not aufrufe

    assert answer_problem("Hier ein Keylogger: ```python\nimport pynput\n``` viel Spaß damit",
                          object(), ask=urteil) == "Schadsoftware"
    assert aufrufe


def test_a_failing_model_never_withdraws_an_answer() -> None:
    def kaputt(prompt: str, settings: Any) -> str:
        raise RuntimeError("Netz weg")

    assert answer_problem("Ein Text über Sprengstoff in der Geschichte des Bergbaus.",
                          object(), ask=kaputt) == ""


def test_the_judge_prompt_for_answers_allows_education() -> None:
    from aquaticy.aiguard import answer_prompt

    text = answer_prompt("Antworttext")
    assert "Bildung" in text and "Im Zweifel: kein Problem" in text


def test_the_removed_mode_is_not_in_the_agent_or_server_signature() -> None:
    import inspect

    assert "image_mode" not in inspect.signature(Agent.ask).parameters
    assert "image_mode" not in inspect.signature(web.ChatSession.ask).parameters


def test_the_model_button_sits_next_to_the_send_button() -> None:
    html = web.UI_FILE.read_text(encoding="utf-8")
    kopf = html[html.index('<div class="topbar">'): html.index('<div class="picker"')]
    assert 'id="btn-model"' not in kopf, "oben ist die Modellauswahl weg"
    crow = html[html.index('<div class="crow">'): html.index('id="send"')]
    assert 'id="btn-model"' in crow, "unten steht sie links neben Senden"


def test_the_menu_has_effort_and_more_settings_without_image_creation() -> None:
    html = web.UI_FILE.read_text(encoding="utf-8")
    menue = html[html.index('id="picker-models"'): html.index('id="win-aufwand"')]
    assert 'id="btn-imagemode"' not in html and "Bilderstellung" not in menue
    assert menue.index('id="btn-aufwand"') < menue.index('id="btn-weitere"')
    aufwand = html[html.index('id="win-aufwand"'): html.index('id="win-weitere"')]
    assert 'id="efforts"' in aufwand and 'id="agents"' in aufwand
    weitere = html[html.index('id="win-weitere"'): html.index('<main id="main">')]
    # 16.0.0 (Aquaticy-Test): ohne virtual machine kein Schalter "werkstatt".
    assert 'id="werkstatt"' not in weitere
    for schalter in ("online", "structure", "recheck", "denken"):
        assert f'id="{schalter}"' in weitere, schalter


def test_the_browser_cannot_send_the_removed_image_mode() -> None:
    html = web.UI_FILE.read_text(encoding="utf-8")
    assert "image_mode: imageMode" not in html
    assert "setImageMode" not in html


# 16.0.0 (Aquaticy-Test): test_the_lan_switch_exists_for_ultra entfaellt.
# Grund: virtual machine, Heimnetz, Messenger, Upgrading und Verbund sind aus der Oberflaeche
# geloescht


