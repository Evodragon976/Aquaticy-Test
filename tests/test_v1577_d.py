"""15.7.7: Laufende Aufgaben, Geheimnisse und Zeitumstellungen."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from aquaticy import web, zeit

# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


def test_f034_the_timezone_fallback_observes_fold_in_the_spring_gap():
    actual, fallback = ZoneInfo('Europe/Berlin'), zeit._EURegel()
    for fold in (0, 1):
        wall = datetime(2026, 3, 29, 2, 30, fold=fold)
        assert wall.replace(tzinfo=actual).utcoffset() == wall.replace(tzinfo=fallback).utcoffset()


# 16.0.1 (Aquaticy-Test): 3 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def _google_handler(settings, monkeypatch, host, https=False):
    handler = object.__new__(web.Handler)
    handler.headers = {'Host': host}
    handler._https = lambda: https
    handler._queue_header = lambda *args: None
    settings.google_client_id = 'client-id'
    settings.google_client_secret = 'client-secret'
    monkeypatch.setattr(web, 'SESSION', SimpleNamespace(settings=lambda: settings, account=None))
    return handler


def test_f037_google_login_on_home_https_uses_the_http_callback_port(settings, monkeypatch):
    monkeypatch.setattr(web, 'SERVER', SimpleNamespace(server_address=('0.0.0.0', 8765)))
    handler = _google_handler(settings, monkeypatch, 'aquaticy.local:8443', https=True)
    result = handler._google({'action': 'start'})
    assert result['redirect'] == 'http://localhost:8765/google'


def test_f039_google_code_exchange_keeps_the_original_redirect_after_an_address_change(
        settings, monkeypatch):
    from aquaticy import google

    captured = []
    handler = _google_handler(settings, monkeypatch, '127.0.0.1:8765')
    initial = handler._google({'action': 'start'})
    handler.headers = {'Host': 'localhost:8765'}
    monkeypatch.setattr(google, 'exchange_code', lambda cid, secret, code, redirect:
                        captured.append(redirect) or google.Tokens())
    monkeypatch.setattr(web, 'google_client', lambda settings: SimpleNamespace(
        remember=lambda tokens: None, close=lambda: None))
    monkeypatch.setattr(web, 'google_state', lambda settings: {})
    handler._google({'action': 'finish', 'code': 'code', 'state': initial['state']})
    assert captured == [initial['redirect']]
