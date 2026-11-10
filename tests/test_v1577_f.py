"""15.7.7: Datenschutz, Zustellung und gleichzeitige Cache-Zugriffe."""

import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from aquaticy import google, local_model
from aquaticy.cache import Cache

# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f051_naive_calendar_times_use_german_time_on_a_utc_server(monkeypatch):
    monkeypatch.setenv('TZ', 'UTC')
    time.tzset()
    try:
        actual = google._calendar_datetime('2026-11-08T14:00:00')
        expected = datetime(2026, 11, 8, 14, tzinfo=ZoneInfo('Europe/Berlin'))
        assert actual.timestamp() == expected.timestamp()
    finally:
        monkeypatch.undo()
        time.tzset()


def test_f052_attachment_dispositions_with_leading_space_stay_out_of_the_mail_body():
    part = {'mimeType': 'text/plain', 'headers': [
        {'name': 'Content-Disposition', 'value': ' attachment; filename="private.txt"'}],
        'body': {'data': base64.urlsafe_b64encode(b'Attachment private content').decode()}}
    assert google._body_text(part) == ''


@pytest.mark.parametrize('method', ['_get', '_write'])
def test_f053_google_api_responses_are_bounded_before_loading_the_body(
        tmp_path, method, monkeypatch):
    monkeypatch.setattr(google, 'MAX_RESPONSE_BYTES', 131072, raising=False)
    read = []

    class Body(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(150):
                read.append(1)
                yield b' ' * 65536

    with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=Body()))) as http:
        api = google.Google('id', 'secret', google.TokenStore(tmp_path), http)
        api._access = lambda: 'access'
        with pytest.raises(google.GoogleError):
            if method == '_get':
                api._get(google.GMAIL_API + '/messages', {})
            else:
                api._write('POST', google.GMAIL_API + '/drafts', {})
    assert len(read) < 150


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


def test_f057_parallel_ollama_metadata_misses_share_one_bounded_request(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    monkeypatch.setattr(local_model, '_SHOW', {})

    @contextmanager
    def stream(*args, **kwargs):
        calls.append(True)
        entered.set()
        release.wait(2)
        yield httpx.Response(200, json={'capabilities': ['tools']})

    monkeypatch.setattr(local_model.httpx, 'stream', stream)
    with ThreadPoolExecutor(2) as pool:
        one = pool.submit(local_model._show, 'example:7b')
        assert entered.wait(1)
        two = pool.submit(local_model._show, 'example:7b')
        try:
            time.sleep(0.05)
            assert len(calls) == 1
        finally:
            release.set()
        assert one.result() == two.result()


def test_f058_distinct_cache_objects_for_one_database_share_the_fill_lock(tmp_path):
    first = Cache(tmp_path / 'cache.sqlite3')
    second = Cache(tmp_path / 'cache.sqlite3')
    entered = threading.Event()

    def fill():
        with second.filling('same-key'):
            entered.set()

    with ThreadPoolExecutor(1) as pool:
        with first.filling('same-key'):
            worker = pool.submit(fill)
            assert not entered.wait(0.1)
        worker.result(1)


def test_bounded_google_responses_preserve_gzip_support(tmp_path, monkeypatch):
    import gzip

    payload = gzip.compress(b'{"email":"owner@example.org"}')
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, content=payload, headers={"content-encoding": "gzip"}))
    with httpx.Client(transport=transport) as client:
        connection = google.Google("client", "secret", google.TokenStore(tmp_path), client=client)
        monkeypatch.setattr(connection, "_access", lambda: "test-token")
        assert connection._get("https://www.googleapis.com/userinfo", {}) == {
            "email": "owner@example.org"}
