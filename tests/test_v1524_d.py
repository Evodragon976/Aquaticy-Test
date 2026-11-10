"""15.2.4: nachgestellte Fehler F061 bis F080."""

import base64
import io
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from aquaticy import auth, botguard, cli, google, local_model
from aquaticy.agent import Agent


def test_f061_nonascii_bot_proofs_are_rejected_without_crashing():
    assert botguard.check({'token': 'ä.invalid', 'nonce': '1'}, ('visit',)) is False


def test_f062_a_full_replay_cache_never_evicts_a_still_valid_proof(monkeypatch):
    monkeypatch.setattr(botguard.time, 'time', lambda: 100)
    used = botguard._Used(max_entries=2)
    assert used.take('first', 1000) and used.take('second', 1000)
    used.take('third', 1000)
    assert not used.take('first', 1000)


def test_f063_an_existing_local_ollama_api_needs_no_host_binary(monkeypatch):
    monkeypatch.setattr(local_model, 'ollama_binary', lambda: None)
    monkeypatch.setattr(local_model, 'server_running', lambda *a, **kw: True)
    assert local_model.start_server() is True


def test_f064_cancelling_an_ollama_pull_stops_and_reaps_its_process(monkeypatch):
    class Process:
        stdout = io.StringIO('Downloading\nStill downloading\n')
        stopped = False
        waited = False
        def poll(self):
            return 0 if self.stopped else None
        def terminate(self):
            self.stopped = True
        def kill(self):
            self.stopped = True
        def wait(self, *a, **kw):
            self.waited = True
            return 0
    process = Process()
    monkeypatch.setattr(local_model.subprocess, 'Popen', lambda *a, **kw: process)
    progress = local_model.pull_model('qwen:7b', binary='/fake/ollama')
    assert next(progress) == 'Downloading'
    progress.close()
    assert process.stopped and process.waited and process.stdout.closed


def _mail_part(text, mime='text/plain'):
    return {'mimeType': mime, 'body': {'data': base64.urlsafe_b64encode(text.encode()).decode()}}


def test_f065_inline_multipart_mail_bodies_keep_all_their_text_parts():
    payload = {'mimeType': 'multipart/mixed', 'parts': [
        _mail_part('First paragraph.'), _mail_part('Second paragraph.'),
        {**_mail_part('Attachment must stay out.'), 'filename': 'private.txt'}]}
    text = google._body_text(payload)
    assert 'First paragraph.' in text and 'Second paragraph.' in text
    assert 'Attachment must stay out.' not in text


def test_f066_mail_mime_types_are_case_insensitive():
    assert google._body_text(_mail_part('Important message', 'TEXT/PLAIN')) == 'Important message'


@pytest.mark.parametrize('value,expected', [('1,2345 EUR', '1,2345'), (0.000001, '0.000001')])
def test_f067_price_parsing_keeps_the_full_decimal_precision(value, expected):
    from aquaticy.extract import parse_price
    assert parse_price(value)[0] == expected


def _tcp_frame(*, seq=123, vlan=False):
    import socket
    tcp = struct.pack('!HHIIBBHHH', 40000, 22, seq, 0, 0x50, 0x02, 0, 0, 0)
    ip = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 40, 0, 0, 64, 6, 0,
                     socket.inet_aton('192.168.1.20'), socket.inet_aton('192.168.1.21'))
    header = b'\0' * 12 + struct.pack('!H', 0x88A8 if vlan else 0x0800)
    tags = struct.pack('!HHHH', 1, 0x8100, 2, 0x0800) if vlan else b''
    return header + tags + ip + tcp


# 16.0.1 (Aquaticy-Test): 9 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f071_login_rate_limits_do_not_grow_without_bound_under_new_client_keys(monkeypatch):
    limiter = auth.RateLimiter(attempts=2)
    limiter.SWEEP_AT = 2
    monkeypatch.setattr(auth.time, 'monotonic', lambda: 100)
    assert limiter.allow('one') and limiter.allow('two')
    assert not limiter.allow('three') and len(limiter) == 2
    assert limiter.allow('one') and not limiter.allow('one')


def test_f072_local_model_setup_uses_the_configured_ollama_endpoint(settings, monkeypatch):
    monkeypatch.setenv('OLLAMA_API_BASE', 'http://127.0.0.1:12555')
    monkeypatch.setattr(cli, 'get_settings', lambda: settings)
    monkeypatch.setattr(local_model, 'ollama_binary', lambda: '/fake/ollama')
    monkeypatch.setattr(local_model, 'server_running', lambda *a, **kw: False)
    calls = []
    monkeypatch.setattr(local_model, 'start_server', lambda *a, **kw: calls.append((a, kw)) or True)
    assert cli._ensure_ollama(assume_yes=True)
    assert any('http://127.0.0.1:12555' in (*args, *kw.values()) for args, kw in calls)


def test_f073_image_descriptions_mark_their_content_as_untrusted(settings, monkeypatch, tmp_path):
    image = tmp_path / 'sample.png'
    image.write_bytes(local_model.solid_png())
    settings.vision_model = 'ollama_chat/vision:latest'
    agent = object.__new__(Agent)
    agent.settings = settings
    agent.toolbox = SimpleNamespace(untrusted_seen=False)
    agent._emit = lambda *a, **kw: None
    from aquaticy import metering
    monkeypatch.setattr(metering, 'completion', lambda *a, **kw: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='A red image.'))]))
    assert agent.describe_image(image) == 'A red image.'
    assert agent.toolbox.untrusted_seen


@pytest.mark.parametrize('answer', ['It is blue, not red.', 'The prototype is blue.', 'Nicht rot.'])
def test_f075_vision_probes_do_not_accept_substrings_or_negated_colour_names(monkeypatch, answer):
    import litellm
    monkeypatch.setattr(litellm, 'completion', lambda **kw: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=answer))]))
    assert local_model.verify_vision('ollama_chat/vision:latest')[0] is False


def _fake_command(directory: Path, name: str, body: str):
    file = directory / name
    file.write_text('#!/bin/sh\n' + body + '\n')
    file.chmod(0o755)


