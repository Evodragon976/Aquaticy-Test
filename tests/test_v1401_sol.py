"""Dateipruefungen, geschuetzte Einstellungen und Router-Auswahl bleiben korrekt."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aquaticy import private_json, voice
from tests.test_v1401 import owner  # noqa: F401

# 16.0.1 (Aquaticy-Test): 7 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_voice_model_access_failure_does_not_break_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(voice.shutil, "which", lambda name: "/bin/tool")
    monkeypatch.setattr(voice.importlib.util, "find_spec", lambda name: object())

    def denied():
        raise PermissionError("model cache unavailable")

    model = SimpleNamespace(is_file=lambda: True, stat=denied)
    monkeypatch.setattr(Path, "rglob", lambda *a: iter([model]))
    assert voice.ready(tmp_path) is False


def test_failed_settings_replace_preserves_previous_private_file(tmp_path, monkeypatch):
    target = tmp_path / "voice.json"
    private_json.write(target, {"enabled": True})

    def interrupted(*args):
        assert json.loads(target.read_text()) == {"enabled": True}
        raise OSError("disk unavailable")

    monkeypatch.setattr(private_json.os, "replace", interrupted)
    with pytest.raises(OSError):
        private_json.write(target, {"enabled": False})
    assert json.loads(target.read_text()) == {"enabled": True}
    assert list(tmp_path.iterdir()) == [target]


def test_private_settings_do_not_follow_links_or_keep_public_permissions(tmp_path):
    target, outside = tmp_path / "voice.json", tmp_path / "outside.json"
    outside.write_text("private external data")
    target.symlink_to(outside)
    with pytest.raises(OSError):
        private_json.write(target, {"enabled": False})
    assert outside.read_text() == "private external data"
    target.unlink()
    target.write_text('{"enabled":true}')
    target.chmod(0o644)
    private_json.write(target, {"enabled": False})
    assert json.loads(target.read_text()) == {"enabled": False}
    if private_json.os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o600


