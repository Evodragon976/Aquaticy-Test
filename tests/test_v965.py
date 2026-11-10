"""Normalmodus-Tempo und voneinander unabhaengige Chats ueber HTTP/Chromium."""

from __future__ import annotations

import secrets
import threading
import time
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import httpx
import pytest

from aquaticy import agent as agents
from aquaticy import web
from aquaticy.auth import AuthStore, pro_code_for, ultra_code_for
from aquaticy.config import Settings
from tests.anmeldung import AGENT, FETCH, SPRACHE, wie_die_app
from tests.test_web import FakeAgent


@pytest.fixture
def parallel_site(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, model="mistral/mistral-large-latest",
                        subagents_auto=False)
    gates = {name: threading.Event() for name in ("Recherche A", "Recherche B")}
    started = {name: threading.Event() for name in gates}
    made = []

    class TestAgent(FakeAgent):
        def __init__(self, settings, cache=None):
            super().__init__()
            self.cache = cache
            self.session_id = secrets.token_hex(12)
            self.messages = []
            self.cancelled = False
            made.append(self)

        def clear(self):
            self.session_id = secrets.token_hex(12)
            self.messages = []

        def resume(self, session_id, turns):
            self.session_id = session_id
            self.messages = [{"role": "user", "content": turn[0]} for turn in turns]

        def ask(self, question, **kwargs):
            self.asked.append(question)
            self.messages.append({"role": "user", "content": question})
            if question in gates:
                self.on_event("answer_chunk", {"text": f"Zwischenstand {question}"})
                started[question].set()
                assert gates[question].wait(30)
            answer = f"Antwort auf {question}"
            self.on_event("answer_chunk", {"text": answer})
            self.cache.add_history(self.session_id, question, answer)
            self.on_event("done", {})

        def cancel(self):
            self.cancelled = True
            for question in self.asked:
                if question in gates:
                    gates[question].set()

    monkeypatch.setattr(agents, "Agent", TestAgent)
    monkeypatch.setattr(web, "get_settings", lambda: settings)
    monkeypatch.setattr(web, "SESSIONS", web.SessionRegistry())
    monkeypatch.setattr(web, "DEFAULT_SESSION", web.ChatSession())
    monkeypatch.setattr(web, "RUNS", web.RunBook())
    monkeypatch.setattr(web, "CLUSTER", None)
    monkeypatch.setattr(web, "AIGUARD", None)
    monkeypatch.setattr(web, "TOKEN", "")
    monkeypatch.setattr(web, "SESSION", web.SessionProxy())
    monkeypatch.setattr(web, "start_user_scheduler", lambda account: None)
    store = AuthStore(tmp_path, pro_code_for(tmp_path), ultra_code_for(tmp_path))
    monkeypatch.setattr(web, "AUTH", store)
    account = store.register("parallel@example.org", "parallel-test-passwort", "normal",
                             username="Parallel", terms_accepted=True, terms_version="1")
    server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    client = httpx.Client(base_url=url, trust_env=False, timeout=5,
                         headers={"User-Agent": AGENT, "Accept-Language": SPRACHE})
    try:
        client.post("/api/consent", json={"accepted": True})
        response = client.post("/api/auth/login", headers=FETCH,
                               json=wie_die_app({"email": account.email,
                                                 "password": "parallel-test-passwort"}))
        assert response.status_code == 200
        yield client, gates, started, made, account, url
    finally:
        for gate in gates.values():
            gate.set()
        client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


@pytest.mark.parametrize("mode", ["normal", "pro", "code"])
def test_read_groups_keep_writes_ordered_and_pro_unchanged(mode):
    calls = [{"function": {"name": n}, "id": str(i)} for i, n in enumerate(
        ["fetch_page", "fetch_page", "remember", "fetch_page", "fetch_page"])]
    finished = []
    lock = threading.Lock()
    active = peak = 0

    def runner(call):
        nonlocal active, peak
        if call["function"]["name"] == "remember":
            assert set(finished) == {"0", "1"}
        else:
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with lock:
                active -= 1
        with lock:
            finished.append(call["id"])
        return {"id": call["id"]}

    began = time.monotonic()
    agent = agents.Agent.__new__(agents.Agent)
    agent.mode = mode
    agent.messages = []
    agent.toolbox = SimpleNamespace(stats=SimpleNamespace(searches=[]))
    agent._tool_result = runner
    agent._run_round(calls)
    result = agent.messages
    elapsed = time.monotonic() - began
    assert result == [{"id": str(i)} for i in range(5)]
    assert peak == (2 if mode == "normal" else 1)
    if mode != "normal":
        assert finished == [str(i) for i in range(5)]
    print(f"{mode}: {elapsed:.3f}s")
