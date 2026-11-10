"""Lokale Sprache, Freigaben und defensive Secure-Pro-Meldungen."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from aquaticy import voice


@pytest.fixture
def speech(tmp_path, monkeypatch):
    monkeypatch.setattr(voice, "root", lambda: tmp_path)
    (tmp_path / "voice.json").write_text('{"enabled":true}')
    return tmp_path


@pytest.mark.parametrize("data", [b"", b"a" * (voice.MAX_BYTES + 1)])
def test_audio_limits_reject_before_running_any_decoder(speech, monkeypatch, data):
    monkeypatch.setattr(voice.subprocess, "run", lambda *a, **k: pytest.fail("decoder"))
    with pytest.raises(ValueError):
        voice.transcribe(data)


def test_transcriber_is_offline_bounded_and_deletes_its_input(speech, monkeypatch):
    inputs = []

    def run(args, **kwargs):
        source = Path(args[3])
        inputs.append(source)
        assert source.read_bytes() == b"audio"
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert kwargs["timeout"] == 180
        return SimpleNamespace(stdout="Öffne meine Mails")

    monkeypatch.setattr(voice.subprocess, "run", run)
    assert voice.transcribe(b"audio") == "Öffne meine Mails"
    assert all(not path.exists() for path in inputs)


# 16.0.1 (Aquaticy-Test): 16 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


