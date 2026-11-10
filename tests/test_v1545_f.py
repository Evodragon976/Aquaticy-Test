"""15.4.5: Profiluebertragung und Konfigurationsdateien bleiben vollstaendig."""

import contextlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aquaticy import budget, config, web
from aquaticy.memory import Memory

# 16.0.1 (Aquaticy-Test): 8 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f049_local_speech_model_weights_do_not_exhaust_the_personal_storage_budget(settings):
    model = settings.data_dir / 'voice-models' / 'model.bin'
    model.parent.mkdir(parents=True)
    with model.open('wb') as stream:
        stream.truncate(budget.MAX_BYTES + 1)
    memory = Memory(settings.db_path, settings.data_dir, settings.memory_key)
    memory.remember('A small personal note.')
    assert budget.used_bytes(settings.data_dir, fresh=True) < 1_000_000
    assert model.stat().st_size == budget.MAX_BYTES + 1


def test_f052_parallel_setting_updates_preserve_both_changes(tmp_path, monkeypatch):
    target = tmp_path / '.env'
    target.write_text('FIRST=before\nSECOND=before\n', encoding='utf-8')
    original = Path.read_text
    barrier = threading.Barrier(2)

    def synchronized_read(self, *args, **kwargs):
        text = original(self, *args, **kwargs)
        if self == target:
            with contextlib.suppress(threading.BrokenBarrierError):
                barrier.wait(0.3)
        return text

    monkeypatch.setattr(Path, 'read_text', synchronized_read)
    with ThreadPoolExecutor(2) as pool:
        tasks = [pool.submit(config.write_env_file, values, target)
                 for values in ({'FIRST': 'after'}, {'SECOND': 'after'})]
        for task in tasks:
            task.result(3)
    assert config.read_env_file(target) == {'FIRST': 'after', 'SECOND': 'after'}


def test_f053_failed_settings_replacement_preserves_the_previous_file(tmp_path, monkeypatch):
    target = tmp_path / '.env'
    original_text = 'AQUATICY_MODEL=previous\nMISTRAL_API_KEY=ExistingPrivateKey\n'
    target.write_text(original_text, encoding='utf-8')
    original = Path.write_text

    def partial_write(self, text, *args, **kwargs):
        original(self, text[:9], *args, **kwargs)
        raise OSError('disk full')

    monkeypatch.setattr(Path, 'write_text', partial_write)
    with pytest.raises(OSError):
        config.write_env_file({'AQUATICY_MODEL': 'next'}, target)
    assert target.read_text(encoding='utf-8') == original_text


def test_f054_key_migration_removes_valid_tab_separated_export_assignments(tmp_path):
    target = tmp_path / '.env'
    target.write_text('export\tMISTRAL_API_KEY=OldPlaintextSecret\nOTHER=keep\n', encoding='utf-8')
    web.remove_env_keys(target, {'MISTRAL_API_KEY'})
    assert 'OldPlaintextSecret' not in target.read_text(encoding='utf-8')
    assert config.read_env_file(target) == {'OTHER': 'keep'}


@pytest.mark.parametrize('action', ['update', 'remove'])
def test_f055_multiline_env_assignments_are_replaced_or_removed_as_one_value(tmp_path, action):
    target = tmp_path / '.env'
    target.write_text('MISTRAL_API_KEY="FirstSecretLine\nSecondSecretLine"\nOTHER=keep\n',
                      encoding='utf-8')
    if action == 'update':
        config.write_env_file({'MISTRAL_API_KEY': 'replacement'}, target)
    else:
        web.remove_env_keys(target, {'MISTRAL_API_KEY'})
    text = target.read_text(encoding='utf-8')
    assert 'FirstSecretLine' not in text and 'SecondSecretLine' not in text
    assert config.read_env_file(target).get('OTHER') == 'keep'


def test_utf8_bom_env_files_keep_the_first_setting(tmp_path, monkeypatch):
    target = tmp_path / '.env'
    target.write_bytes(b'\xef\xbb\xbfAQUATICY_LOCATION=Bremen\n')
    monkeypatch.delenv('AQUATICY_LOCATION', raising=False)
    assert config.read_env_file(target) == {'AQUATICY_LOCATION': 'Bremen'}
    config.load_env(target, override=True)
    assert os.environ.get('AQUATICY_LOCATION') == 'Bremen'


