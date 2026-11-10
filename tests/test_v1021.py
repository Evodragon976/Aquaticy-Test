"""10.2.1 Terra: Isolation, vollstaendige Pruefung, Datenschutz und Prozessende."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from aquaticy import aiguard, guardrails, metering
from aquaticy.guardrails import Guard
from aquaticy.legal import LEGAL_VERSION
from tests.test_guardrails import Pruefer
from tests.test_v965 import parallel_site  # noqa: F401
from tests.test_v967 import QUESTION, contribute, learners  # noqa: F401
from tests.test_v1003 import compressed_response, upgrade_page  # noqa: F401


def verdict(allowed=True, rule="", abuse=""):
    return json.dumps({"zulaessig": allowed, "regel": rule, "grund": "Test",
                       "missbrauch": bool(abuse), "missbrauch_art": abuse,
                       "missbrauch_schwere": 3 if abuse else 0})


@pytest.mark.parametrize("change", ["account", "model", "endpoint", "key"])
@pytest.mark.parametrize("checker", ["legal", "input", "answer"])
def test_judgements_are_scoped_to_account_and_model_configuration(settings, change, checker):
    aiguard.forget_judgements()
    settings.model = settings.subagent_model = "openai/test-model"
    settings.api_keys = {"AQUATICY_API_KEY": "first"}
    other = replace(settings)
    if change == "account":
        other.data_dir = settings.data_dir / "other"
    elif change == "model":
        other.model = other.subagent_model = "openai/other-model"
    elif change == "endpoint":
        other.api_base = "https://other.example/v1"
    else:
        other.api_keys = {"AQUATICY_API_KEY": "second"}
    calls = []

    def ask(*args):
        calls.append(args)
        return verdict() if checker == "legal" else '{"missbrauch": false, "art": ""}'

    def check(config):
        if checker == "legal":
            return guardrails.judge("Wie funktioniert Phishing-Schutz?", config, ask=ask)
        if checker == "input":
            return aiguard.classify("Wie funktioniert Phishing-Schutz?", config, ask=ask)
        return aiguard.answer_problem("Phishing ist eine Form des Zugangsdatenbetrugs.",
                                      config, ask=ask)

    check(settings)
    check(settings)
    assert len(calls) == 1
    check(other)
    assert len(calls) == 2


def test_cache_key_has_no_delimiter_collision(settings):
    ask = Pruefer(verdict(), verdict(False, "name"))
    assert guardrails.judge("c", settings, context="a\x1fb", ask=ask).allowed
    assert not guardrails.judge("b\x1fc", settings, context="a", ask=ask).allowed


@pytest.mark.parametrize("baseline", [False, True])
@pytest.mark.parametrize("allowed", [False, True])
@pytest.mark.parametrize("failure", [RuntimeError("offline"), "not json"])
def test_unconfirmed_dangerous_tool_is_blocked_without_punishment(
        settings, baseline, allowed, failure):
    settings.subagent_model = "openai/fast"
    settings.model = "openai/main"
    ask = Pruefer(verdict(allowed, "eigentum" if not allowed else "", "malware"), failure)
    result = Guard(settings, ask=ask, baseline=baseline).check_call("vm_run", {"command": "x"})
    assert not result.allowed
    assert not result.abuse and result.abuse_severity == 0
    assert result.source in ("unklar", "ausfall")
    assert len(ask.gefragt) == 2


def test_baseline_keeps_main_model_confirmation(settings):
    settings.subagent_model = "openai/fast"
    settings.model = "openai/main"
    ask = Pruefer(verdict(False, "vertrag"), verdict(False, "persoenlichkeit"))
    result = Guard(settings, ask=ask, baseline=True).check_call("create_image", {"prompt": "x"})
    assert not result.allowed and result.rule.id == "persoenlichkeit"
    assert len(ask.gefragt) == 2


@pytest.mark.parametrize("tool", sorted(guardrails.BASELINE_TOOLS))
def test_middle_of_long_tool_arguments_is_checked(settings, tool):
    marker = "TEST_GESPERRT"

    def ask(prompt, *_):
        return verdict(False, "persoenlichkeit", "malware") if marker in prompt else verdict()

    result = Guard(settings, ask=ask, baseline=True).check_call(
        tool, {"text": "a" * 5000 + marker + "b" * 5000})
    assert not result.allowed or result.abuse


@pytest.mark.parametrize("payload", [
    {"zulaessig": True},
    {"zulaessig": True, "missbrauch": "maybe"},
    {"zulaessig": True, "missbrauch": False, "missbrauch_art": "malware"},
    {"zulaessig": True, "missbrauch": True, "missbrauch_art": "unknown"},
])
def test_incomplete_vm_verdict_cannot_allow_execution(settings, payload):
    result = Guard(settings, ask=lambda *_: json.dumps(payload), baseline=True).check_call(
        "vm_write", {"path": "demo.py", "content": "print(1)"})
    assert not result.allowed and result.source == "unklar"


@pytest.mark.parametrize("payload", [{"zulaessig": False},
                                      {"zulaessig": False, "regel": "unknown"}])
def test_image_baseline_needs_an_explicit_rule(settings, payload):
    result = Guard(settings, ask=lambda *_: json.dumps(payload), baseline=True).check_call(
        "create_image", {"prompt": "demo"})
    assert not result.allowed and result.source == "unklar"


@pytest.mark.parametrize("enabled,version", [(1, "old"), (0, LEGAL_VERSION)])
def test_recall_ignores_outdated_or_disabled_contributors(learners, enabled, version):  # noqa: F811
    _, _, (first, second) = learners
    for store in (first, second):
        store.set_consent(True, LEGAL_VERSION)
        assert contribute(store) == 1
    with first.connect() as conn:
        conn.execute("UPDATE learning_consent SET enabled=?,version=?", (enabled, version))
    assert first.recall(QUESTION) == []
    assert second.recall(QUESTION) == []


@pytest.mark.parametrize("checker", ["input", "answer"])
def test_checker_outage_is_not_cached(settings, checker):
    aiguard.forget_judgements()
    calls = []

    def ask(*_):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("offline")
        return '{"missbrauch": true, "art": "malware"}'

    def check():
        text = "Phishing ist ein Thema fuer die Sicherheitspruefung."
        if checker == "input":
            return aiguard.classify(text, settings, ask=ask)
        return aiguard.answer_problem(text, settings, ask=ask)

    assert not check()
    assert check()
    assert len(calls) == 2


# 16.0.1 (Aquaticy-Test): 8 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_legal_cache_expires(settings, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(guardrails.time, "monotonic", lambda: clock[0])
    ask = Pruefer(verdict(), verdict(False, "name"))
    assert guardrails.judge("test", settings, ask=ask).allowed
    assert guardrails.judge("test", settings, ask=ask).allowed
    clock[0] += guardrails.CACHE_TTL + 1
    assert not guardrails.judge("test", settings, ask=ask).allowed


@pytest.mark.parametrize("checker", ["legal", "input", "answer"])
def test_erasure_during_judgement_cannot_repopulate_the_cache(settings, checker):
    aiguard.forget_judgements()
    calls = []

    def ask(*_):
        calls.append(1)
        guardrails.forget_verdicts()
        aiguard.forget_judgements()
        return verdict() if checker == "legal" else '{"missbrauch": false, "art": ""}'

    for _ in range(2):
        if checker == "legal":
            guardrails.judge("Wie funktioniert Phishing-Schutz?", settings, ask=ask)
        elif checker == "input":
            aiguard.classify("Wie funktioniert Phishing-Schutz?", settings, ask=ask)
        else:
            aiguard.answer_problem("Phishing ist ein Thema der Sicherheitspruefung.",
                                    settings, ask=ask)
    assert len(calls) == 2


@pytest.mark.parametrize("action", ["wipe_data", "remove_account"])
def test_account_erasure_clears_judgements(learners, action):  # noqa: F811
    from aquaticy.config import Settings

    auth, accounts, _ = learners
    settings = Settings(model="openai/test-model", data_dir=auth.profile_dir(accounts[0].id))
    guardrails.judge("Wie funktioniert Phishing-Schutz?", settings,
                     ask=lambda *_: verdict())
    aiguard.classify("Wie funktioniert Phishing-Schutz?", settings,
                     ask=lambda *_: '{"missbrauch": false, "art": ""}')
    assert guardrails._cache and aiguard._cache
    getattr(auth, action)(accounts[0])
    assert not guardrails._cache and not aiguard._cache


@pytest.mark.parametrize("learned", [False, True])
def test_local_guard_context_includes_rules_material_and_prepared_knowledge(
        settings, monkeypatch, learned):
    from tests.test_guardrails import _reply

    settings.model = settings.subagent_model = "ollama/test"
    prompt = guardrails.judge_prompt("a" * 3500)
    seen = []

    def completion(**kwargs):
        seen.append(kwargs)
        return _reply(verdict())

    monkeypatch.setattr("litellm.completion", completion)
    if learned:
        monkeypatch.setattr(metering, "prepare_messages", lambda s, m, messages: [
            {"role": "system", "content": "learned " * 1000}, *messages])
    metering.completion(settings, enforce=False, model=settings.model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=160, **settings.fast_kwargs_for(settings.model))
    required = sum(len(m["content"].encode()) for m in seen[0]["messages"]) + 160
    assert seen[0]["num_ctx"] >= required


def test_short_local_checks_keep_the_fast_context(settings, monkeypatch):
    from tests.test_guardrails import _reply

    seen = []
    monkeypatch.setattr("litellm.completion", lambda **kw: (seen.append(kw) or _reply("ok")))
    metering.completion(settings, enforce=False, model="ollama/test", num_ctx=2048,
                        messages=[{"role": "user", "content": "Hallo"}], max_tokens=160)
    assert seen[0]["num_ctx"] == 2048


def test_long_harmless_file_is_fully_checked_and_cached(settings):
    ask = Pruefer(verdict())
    guard = Guard(settings, ask=ask, baseline=True)
    arguments = {"content": "print('hello')\n" * 1500}
    assert guard.check_call("vm_write", arguments).allowed
    count = len(ask.gefragt)
    assert count > 4
    assert guard.check_call("vm_write", arguments).allowed
    assert len(ask.gefragt) == count


def test_baseline_irrelevant_denial_does_not_skip_later_tool_checks(settings):
    def ask(prompt, *_):
        if "TEST_GESPERRT" in prompt:
            return verdict(True, abuse="malware")
        return verdict(False, "vertrag")

    result = Guard(settings, ask=ask, baseline=True).check_call(
        "vm_write", {"content": "x" * 5000 + "TEST_GESPERRT" + "y" * 5000})
    assert result.abuse and result.abuse_kind == "malware"


def test_tool_check_windows_overlap(settings):

    marker = "TEST_GESPERRT"
    seen = []

    def ask(prompt, *_):
        seen.append(prompt)
        return verdict(True, abuse="malware") if marker in prompt else verdict()

    result = Guard(settings, ask=ask, baseline=True).check_call(
        "vm_write", {"text": "x" * 3485 + marker + "y" * 3500})
    assert result.abuse
    assert any(marker in prompt for prompt in seen)


def test_confirmed_false_alarm_does_not_block_a_tool(settings):
    settings.subagent_model = "openai/fast"
    settings.model = "openai/main"
    ask = Pruefer(verdict(True, abuse="malware"), verdict())
    result = Guard(settings, ask=ask, baseline=True).check_call("vm_run", {"command": "echo ok"})
    assert result.allowed and not result.abuse
    assert len(ask.gefragt) == 2


def test_revoked_model_access_cannot_hit_an_old_cache(settings, monkeypatch):
    ask = Pruefer(verdict())
    guardrails.judge("test", settings, ask=ask)
    checks = []

    def denied(model):
        checks.append(model)
        raise ValueError("model revoked")

    monkeypatch.setattr(settings, "model_access", denied)
    guardrails.judge("test", settings, ask=ask)
    assert checks and len(ask.gefragt) == 2


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).
