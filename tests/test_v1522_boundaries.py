"""15.2.2: Gegenproben fuer Zugriffsgrenzen, Quellen und parallele Schreibvorgaenge."""


import httpx
import pytest

from aquaticy import addons, cache, local_model, media, research, webview
from aquaticy.tools import Toolbox
from tests.test_v1500 import FakeGitHub


@pytest.fixture
def github_case(settings, monkeypatch):
    fake = FakeGitHub()
    client_type = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **kw: client_type(
        *a, **{"transport": httpx.MockTransport(fake), **kw}))
    monkeypatch.setattr(addons, "_takt", lambda *a, **kw: None)
    addons.install(settings, "github", pro=False)
    settings.github_token = "ghp_" + "a" * 36
    box = Toolbox(settings)
    questions = []
    box.ask_handler = lambda question, choices: questions.append(question) or "ja"
    yield box, fake, questions
    box.close()


# 16.0.1 (Aquaticy-Test): 10 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f23_missing_capabilities_do_not_leak_between_ollama_endpoints(monkeypatch):
    monkeypatch.setattr(local_model, "_FEHLT", {})
    monkeypatch.setattr(local_model, "ollama_capabilities", lambda *a: frozenset({"tools"}))
    local_model.note_missing("ollama_chat/probe", "tools")
    assert local_model.can("ollama_chat/probe", "tools", "http://other:11434") is True


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 3 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


def test_f28_cache_key_components_are_not_ambiguous():
    assert cache.cache_key("x", "a\x1fb", "c") != cache.cache_key("x", "a", "b\x1fc")


def test_f34_deleting_one_chat_keeps_media_still_referenced_by_another(settings):
    store = cache.Cache(settings.db_path)
    identifier = media.save_snapshot(settings.data_dir, b"image", "image/png")
    meta = {"visuals": [{"media_id": identifier}]}
    store.add_history("a" * 32, "q", "a", meta)
    store.add_history("b" * 32, "q", "a", meta)
    store.delete_chat("a" * 32)
    assert media.load_snapshot(settings.data_dir, identifier) is not None


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), 1e300])
def test_f35_invalid_persisted_timestamps_do_not_break_the_ui(timestamp):
    assert webview.moment_text(timestamp) == ""


def test_f36_research_cache_keeps_person_disambiguation():
    url = "https://de.wikipedia.org/wiki/Karl_Müller_(Politiker)"
    question = "Was weißt du über den Arzt Karl Müller?"
    assert not research.matches_subject(url, research.words(question), question)


def test_qualifiers_still_allow_learning_about_the_right_person():
    url = "https://de.wikipedia.org/wiki/Karl_Müller_(Politiker)"
    question = "Wer ist der Politiker Karl Müller?"
    assert research.matches_subject(url, research.words(question), question)


def test_missing_capability_notes_are_private_to_the_profile_and_expire(monkeypatch):
    monkeypatch.setattr(local_model, "_FEHLT", {})
    clock = [1.0]
    monkeypatch.setattr(local_model.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(local_model, "ollama_capabilities", lambda *a: frozenset({"tools"}))
    model = "ollama_chat/profile-probe"
    local_model.note_missing(model, "tools", scope="one")
    assert local_model.can(model, "tools", scope="one") is False
    assert local_model.can(model, "tools", scope="two") is True
    clock[0] += local_model.CAPABILITY_TTL + 1
    assert local_model.can(model, "tools", scope="one") is True
