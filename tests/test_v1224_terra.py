"""12.2.4 Terra: Passwortwechsel, Verbindungsgrenzen und Urteilscaches."""

from __future__ import annotations

import socket
import sqlite3
import threading
from collections import OrderedDict
from dataclasses import replace
from socketserver import BaseRequestHandler
from unittest.mock import Mock

import pytest

from aquaticy import aiguard, linked, system, web
from aquaticy.auth import AuthStore
from aquaticy.config import Settings

OLD = "eine lange alte Passphrase"
NEW = "eine andere neue Passphrase"
MODEL = "mistral/terra-main-chat"
NEXT = "mistral/terra-next-chat"


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


@pytest.mark.parametrize("action", ["wipe_data", "remove_account"])
def test_a_forged_account_snapshot_cannot_erase_a_profile(tmp_path, action):
    store = AuthStore(tmp_path, "PRO123456")
    account = store.register("terra@example.org", OLD, "normal",
                             terms_accepted=True, terms_version="test")
    marker = store.profile_dir(account.id) / "keep.txt"
    marker.write_text("private data")
    with pytest.raises(ValueError, match="Passwort"):
        getattr(store, action)(replace(account, _credential=b""))
    assert marker.read_text() == "private data"


@pytest.mark.parametrize("action", ["wipe_data", "remove_account"])
def test_erasure_holds_the_database_write_lock_until_files_are_deleted(
        tmp_path, monkeypatch, action):
    import shutil

    store = AuthStore(tmp_path, "PRO123456")
    account = store.register("terra@example.org", OLD, "normal",
                             terms_accepted=True, terms_version="test")
    marker = store.profile_dir(account.id) / "keep.txt"
    marker.write_text("private data")
    remove = shutil.rmtree
    checked = []

    def check_and_remove(path):
        with (sqlite3.connect(store.db_path, timeout=0) as concurrent,
              pytest.raises(sqlite3.OperationalError, match="locked")):
            concurrent.execute("UPDATE users SET username='changed' WHERE id=?", (account.id,))
        checked.append(path)
        remove(path)

    monkeypatch.setattr("aquaticy.auth.shutil.rmtree", check_and_remove)
    getattr(store, action)(account)
    assert checked and not marker.exists()


def test_slow_connections_are_bounded_before_http_headers_are_available(monkeypatch):
    monkeypatch.setattr(web.AquaticyServer, "max_connections", 2, raising=False)
    entered = threading.Barrier(3)
    release = threading.Event()

    class WaitingHandler(BaseRequestHandler):
        def handle(self):
            entered.wait(timeout=3)
            release.wait(timeout=5)

    server = web.AquaticyServer(("127.0.0.1", 0), WaitingHandler)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    clients = []
    try:
        clients = [socket.create_connection(server.server_address, timeout=2) for _ in range(2)]
        entered.wait(timeout=3)
        with socket.create_connection(server.server_address, timeout=2) as overloaded:
            with overloaded.makefile("rb") as response:
                data = response.read()
            assert data.startswith(b"HTTP/1.1 503 ")
            assert b"Retry-After: 1\r\n" in data
            assert b"Cache-Control: no-store\r\n" in data
            assert b"X-Content-Type-Options: nosniff\r\n" in data
            assert b"Content-Security-Policy: default-src 'none';" in data
    finally:
        release.set()
        for client in clients:
            client.close()
        server.shutdown()
        server.server_close()
        serving.join(timeout=3)


def test_a_handler_error_returns_the_connection_slot(monkeypatch):
    monkeypatch.setattr(web.AquaticyServer, "max_connections", 1)
    server = web.AquaticyServer(("127.0.0.1", 0), web.Handler)
    request = Mock()
    monkeypatch.setattr(server, "finish_request", Mock(side_effect=ValueError("synthetic error")))
    monkeypatch.setattr(server, "handle_error", Mock())
    try:
        assert server._connection_slots.acquire(blocking=False)
        server.process_request_thread(request, ("127.0.0.1", 1))
        assert server._connection_slots.acquire(blocking=False)
        request.close.assert_called_once()
        server.handle_error.assert_called_once()
    finally:
        server.server_close()


def test_successful_connections_reuse_the_server_capacity(monkeypatch):
    monkeypatch.setattr(web.AquaticyServer, "max_connections", 1)

    class ReplyHandler(BaseRequestHandler):
        def handle(self):
            self.request.sendall(b"ok")

    server = web.AquaticyServer(("127.0.0.1", 0), ReplyHandler)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    try:
        for _ in range(3):
            with socket.create_connection(server.server_address, timeout=2) as client:
                assert client.recv(512) == b"ok"
            assert server._connection_slots.acquire(timeout=3)
            server._connection_slots.release()
    finally:
        server.shutdown()
        server.server_close()
        serving.join(timeout=3)


def test_a_failed_thread_start_does_not_lose_a_connection_slot(monkeypatch):
    monkeypatch.setattr(web.AquaticyServer, "max_connections", 1)
    server = web.AquaticyServer(("127.0.0.1", 0), web.Handler)
    monkeypatch.setattr(web.ThreadingHTTPServer, "process_request",
                        Mock(side_effect=RuntimeError("cannot start thread")))
    try:
        with pytest.raises(RuntimeError, match="cannot start thread"):
            server.process_request(Mock(), ("127.0.0.1", 1))
        assert server._connection_slots.acquire(blocking=False)
    finally:
        server.server_close()


@pytest.mark.parametrize("kind", ["request", "answer"])
def test_retirement_eviction_during_a_check_cannot_restore_an_old_cache_binding(
        monkeypatch, tmp_path, kind):
    monkeypatch.setattr(system, "_retired_seen", OrderedDict())
    monkeypatch.setattr(system, "MAX_RETIRED_MODELS", 1)
    monkeypatch.setattr("aquaticy.local_model.installed_models", lambda *a, **kw: [])
    settings = Settings(model=MODEL, subagent_model=MODEL, data_dir=tmp_path,
                        api_keys={"MISTRAL_API_KEY": "synthetic-terra-key"},
                        own_key_names=frozenset({"MISTRAL_API_KEY"}))
    linked.save(tmp_path, "mistral", {"models": [{"id": MODEL}, {"id": NEXT}]})
    called = []
    aiguard.forget_judgements()

    def one(prompt, current, model):
        called.append(model)
        current.fast_kwargs_for(model)
        if model == MODEL:
            raise RuntimeError("410 Gone")

        system.mark_retired("mistral/unrelated-model", current)
        return '{"missbrauch":false,"art":"ok","grund":""}'

    monkeypatch.setattr(aiguard, "_ask_one", one)
    text = "Ich erklaere allgemein, wie man Schadsoftware erkennt und sicher analysiert."

    def check():
        return (aiguard.classify(text, settings) if kind == "request" else
                aiguard.answer_problem(text, settings))

    check()
    assert called == [MODEL, NEXT]

    def access(model):
        if model == NEXT:
            raise ValueError("Modellfreigabe entzogen")

    settings.model_access = access
    check()
    assert called == [MODEL, NEXT, MODEL, NEXT], "Erneut pruefen, kein fremd gebundenes Urteil"


def test_retirements_do_not_flush_other_accounts_cached_judgements(monkeypatch, tmp_path):
    monkeypatch.setattr(system, "_retired_seen", OrderedDict())
    monkeypatch.setattr("aquaticy.local_model.installed_models", lambda *a, **kw: [])
    settings = Settings(model=MODEL, subagent_model=MODEL, data_dir=tmp_path,
                        api_keys={"MISTRAL_API_KEY": "synthetic-terra-key"},
                        own_key_names=frozenset({"MISTRAL_API_KEY"}))
    other = replace(settings, data_dir=tmp_path / "other")
    called = []
    aiguard.forget_judgements()

    def ask(prompt, current):
        called.append(prompt)
        return '{"missbrauch":false,"art":"ok","grund":""}'

    text = "Erklaere mir bitte ausfuehrlich die Funktionsweise einer Waermepumpe."
    assert aiguard.classify(text, settings, ask=ask) == (False, "ok")
    system.mark_retired(MODEL, other)
    assert aiguard.classify(text, settings, ask=ask) == (False, "ok")
    assert len(called) == 1, "Bestehende Urteile anderer Konten bleiben nutzbar"
