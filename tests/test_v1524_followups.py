"""Erfolgswege, Abbruch und parallele Nutzung der Korrekturen aus 15.2.4."""

import io
import json
from types import SimpleNamespace

import httpx
import pytest
from rich.console import Console

from aquaticy import addons, cli, export, local_model, memory


def test_clearing_uploads_cannot_remove_files_outside_the_profile(tmp_path):
    profile = tmp_path / 'profile'
    profile.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    valuable = outside / 'keep.txt'
    valuable.write_text('Keep this', encoding='utf-8')
    (profile / 'uploads').symlink_to(outside, target_is_directory=True)
    store = memory.Memory(profile / 'memory.db')
    assert store.clear_uploads() == (0, 0)
    assert valuable.read_text(encoding='utf-8') == 'Keep this'


def test_feed_base_paths_have_a_size_limit():
    feed = b'<feed xml:base="https://example.org/' + b'a' * 8192 + b'"/>'
    with pytest.raises(ValueError, match='Basisadresse'):
        addons.parse_feed(feed, 'https://example.org/feed')


def test_currency_semicolons_keep_the_same_euro_permissions(settings, monkeypatch):
    from aquaticy.tools import Toolbox
    box = object.__new__(Toolbox)
    box.settings = settings
    box.stats = SimpleNamespace(addon_calls=0)
    monkeypatch.setattr(addons, "active", lambda *args: True)
    monkeypatch.setattr(addons, "rights_of", lambda *args: {"waehrungen": "euro"})
    monkeypatch.setattr(addons, "currency", lambda *args: {"ok": True})
    assert box._addon_call('currency', {'base': 'USD', 'to': 'EUR; EUR'}) == {'ok': True}
    assert box._addon_call('currency', {'base': 'USD', 'to': 'EUR; CHF'}).get('error')


def test_failed_default_export_does_not_leave_an_empty_document(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError('Disk unavailable')
    monkeypatch.setattr(export, 'to_markdown', fail)
    with pytest.raises(OSError):
        export.export([export.Turn('Question', 'Answer')], 'md', directory=tmp_path)
    assert not list(tmp_path.glob('*.md'))


# 16.0.1 (Aquaticy-Test): 5 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


@pytest.mark.parametrize('body,success', [
    (b'{"status":"downloading"}\n{"status":"success"}\n', True),
    (b'{"status":"success"}', True),
    (b'{"status":"downloading"}\n', False),
    (b'{"error":"disk full"}\n', False),
    (b'[]\n', False),
])
def test_ollama_server_can_download_without_a_local_cli(body, success, monkeypatch):
    monkeypatch.setattr(local_model, 'ollama_binary', lambda: None)
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, content=body)
    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        def stream(method, url, **kwargs):
            assert kwargs.pop('trust_env') is False
            assert kwargs['follow_redirects'] is False
            return http.stream(method, url, **kwargs)
        monkeypatch.setattr(local_model.httpx, 'stream', stream)
        if success:
            assert list(local_model.pull_model('qwen3:8b', base_url='http://ollama:11434'))[-1] \
                == 'success'
        else:
            with pytest.raises(local_model.LocalModelError):
                list(local_model.pull_model('qwen3:8b', base_url='http://ollama:11434'))
    assert requests[0].url == 'http://ollama:11434/api/pull'
    assert json.loads(requests[0].content)['model'] == 'qwen3:8b'


def test_image_descriptions_are_displayed_as_plain_text(tmp_path, monkeypatch):
    image = tmp_path / '[image].png'
    image.write_bytes(b'png')
    output = io.StringIO()
    monkeypatch.setattr(cli, 'console', Console(file=output, width=150, color_system=None))
    description = 'Text [/invalid] [bold] als Text'
    agent = SimpleNamespace(describe_image=lambda *args: description)
    assert description in cli._describe_image(agent, image)
    assert description in output.getvalue()


