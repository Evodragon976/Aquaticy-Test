"""11.2.3 Luna: widerrufene Rechte, Freigaben, Archivpfade und Website-Stopp."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

# 16.0.1 (Aquaticy-Test): 17 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_cache_waits_for_another_store_to_finish_initializing(tmp_path, monkeypatch):
    from aquaticy import cache

    path = tmp_path / "history.db"
    connect = sqlite3.connect
    blocked = Event()

    class Connection(sqlite3.Connection):
        def execute(self, statement, *args, **kwargs):
            try:
                return super().execute(statement, *args, **kwargs)
            except sqlite3.OperationalError:
                if statement == "PRAGMA journal_mode=WAL":
                    blocked.set()
                raise

    writer = connect(path)
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("CREATE TABLE first_store (value TEXT)")
        monkeypatch.setattr(cache.sqlite3, "connect",
                            lambda *args, **kwargs: connect(*args, factory=Connection, **kwargs))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(cache.Cache, path)
            try:
                assert blocked.wait(timeout=3), "Der Test muss die echte Sperre treffen"
            finally:
                writer.commit()
            db = future.result(timeout=3)
            assert db.get("missing") is None
            with db._connect() as conn:
                assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 10_000
    finally:
        writer.close()


@pytest.mark.parametrize("code", [
    sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_ERROR,
    sqlite3.SQLITE_BUSY_RECOVERY, sqlite3.SQLITE_LOCKED_SHAREDCACHE,
])
def test_wal_retry_is_bounded_and_only_for_lock_errors(tmp_path, monkeypatch, code):
    from aquaticy import cache

    calls = []
    closed = []

    class Connection:
        def execute(self, statement):
            calls.append(statement)
            error = sqlite3.OperationalError("gestellt")
            error.sqlite_errorcode = code
            raise error

        def close(self):
            closed.append(True)

    db = object.__new__(cache.Cache)
    db.db_path = tmp_path / "cache.db"
    clock = iter([0.0, 1.0, 11.0])
    monkeypatch.setattr(cache.sqlite3, "connect", lambda *args, **kwargs: Connection())
    monkeypatch.setattr(cache, "time", SimpleNamespace(monotonic=lambda: next(clock),
                                                      sleep=lambda seconds: None))
    with pytest.raises(sqlite3.OperationalError), db._connect():
        pytest.fail("Eine gesperrte oder defekte Datenbank wird nicht verwendet")
    assert len(calls) == (1 if code == sqlite3.SQLITE_ERROR else 2)
    assert closed == [True]
