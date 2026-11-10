"""Key preservation, malformed input and private diagnostics for 9.6.8 Luna."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import secrets
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from aquaticy import auth, keyvault, memory, privacy
from aquaticy.auth import AuthStore
from aquaticy.calc import CalcError, calculate
from aquaticy.extract import extract_product
from aquaticy.jsonutil import MAX_DEPTH, JsonDepthError, loads
from tests.test_v965 import parallel_site as parallel_site


@pytest.mark.parametrize("filename,loader", [
    ("data.key", lambda p: privacy.master_key(p.parent)),
    ("auth.key", lambda p: AuthStore(p.parent, "TESTCODE")),
    ("vault.key", keyvault.load_secret),
    ("memory.key", memory._key_from_file),
    ("memory.salt", lambda p: memory._salt_for(p.parent)),
])
@pytest.mark.parametrize("content", [b"", b"broken"])
def test_corrupt_keys_fail_without_destroying_the_original(tmp_path, filename, loader, content):
    path = tmp_path / filename
    path.write_bytes(content)
    with pytest.raises(memory.CipherError, match="beschädigt"):
        loader(path)
    assert path.read_bytes() == content
    assert not list(tmp_path.glob(".aquaticy-key-*"))


def test_failed_master_load_is_not_cached_and_backup_restores_access(tmp_path):
    path = tmp_path / "data.key"
    path.write_bytes(b"")
    with pytest.raises(memory.CipherError):
        privacy.master_key(tmp_path)
    restored = secrets.token_bytes(32)
    path.write_bytes(restored)
    assert privacy.master_key(tmp_path) == restored


@pytest.mark.parametrize("hardlinks", [True, False])
def test_simultaneous_key_creators_publish_one_complete_private_key(tmp_path, monkeypatch,
                                                                  hardlinks):
    if not hardlinks:
        def unsupported(*args):
            raise OSError(errno.ENOTSUP, "hard links unavailable")
        monkeypatch.setattr(memory.os, "link", unsupported)
    path = tmp_path / "secret.key"
    barrier = threading.Barrier(8)

    def create():
        def candidate():
            barrier.wait(timeout=10)
            return secrets.token_bytes(32)
        return memory.load_secret_file(path, candidate, 32)

    with ThreadPoolExecutor(max_workers=8) as pool:
        keys = list(pool.map(lambda _: create(), range(8)))
    assert len(set(keys)) == 1
    assert keys[0] == path.read_bytes() and len(keys[0]) == 32
    assert not list(tmp_path.glob(".aquaticy-key-*"))
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("hardlinks", [True, False])
def test_independent_processes_create_and_reopen_the_same_key(tmp_path, hardlinks):
    path = tmp_path / "secret.key"
    script = (
        "import errno,hashlib,os,secrets,sys; from pathlib import Path; "
        "from aquaticy.memory import load_secret_file; "
        "original_link=os.link; "
        "os.link=lambda *a: original_link(*a) if sys.argv[2]=='yes' else "
        "(_ for _ in ()).throw(OSError(errno.ENOTSUP,'unavailable')); "
        "key=load_secret_file(Path(sys.argv[1]),lambda:secrets.token_bytes(32),32); "
        "print(hashlib.sha256(key).hexdigest())"
    )

    def run(_):
        return subprocess.run([sys.executable, "-c", script, str(path),
                               "yes" if hardlinks else "no"], check=True,
                              capture_output=True, text=True, timeout=20).stdout.strip()

    with ThreadPoolExecutor(max_workers=6) as pool:
        fingerprints = list(pool.map(run, range(6)))
    assert set(fingerprints) == {hashlib.sha256(path.read_bytes()).hexdigest()}
    assert not list(tmp_path.glob(".aquaticy-key-*"))


def test_failed_secret_creation_cleans_up_without_publishing(tmp_path):
    path = tmp_path / "secret.key"
    with pytest.raises(memory.CipherError):
        memory.load_secret_file(path, lambda: b"short", 32)
    assert not path.exists()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-32"])
def test_depth_limit_preserves_encodings_quotes_escapes_and_string_brackets(encoding):
    value = {"text": 'Wärme \\ " ' + "[{}]" * 100, "items": [True, None, 1]}
    assert loads(json.dumps(value, ensure_ascii=False).encode(encoding)) == value
    boundary = "[" * MAX_DEPTH + "0" + "]" * MAX_DEPTH
    assert loads(boundary.encode(encoding)) == json.loads(boundary)
    with pytest.raises(JsonDepthError):
        loads(("[" + boundary + "]").encode(encoding))


def test_existing_long_secret_is_preserved_without_rotation(tmp_path):
    path = tmp_path / "legacy.key"
    original = secrets.token_bytes(64)
    path.write_bytes(original)
    assert memory.load_secret_file(path, lambda: pytest.fail("must not rotate"), 32) == original
    assert path.read_bytes() == original


def test_encrypted_notes_and_passwords_survive_reopening(tmp_path):
    cipher = memory.Cipher(tmp_path / "memory.key")
    token = cipher.encrypt("Vertrauliche Erinnerung mit Umlauten: Größe und Wärme.")
    assert memory.Cipher(tmp_path / "memory.key").decrypt(token) == cipher.decrypt(token)
    store = AuthStore(tmp_path, "TESTCODE")
    account = store.register("unicode@example.org", "pässwort-sicher-123", "normal",
                             terms_accepted=True, terms_version="1")
    reopened = AuthStore(tmp_path, "TESTCODE")
    assert reopened.authenticate(account.email, "pässwort-sicher-123").id == account.id


def test_unicode_password_change_still_revokes_other_sessions(tmp_path):
    store = AuthStore(tmp_path, "TESTCODE")
    old, new = "pässwort-sicher-123", "äußerst-sicher-neu-456"
    account = store.register("unicode@example.org", old, "normal",
                             terms_accepted=True, terms_version="1")
    keep = store.create_session(account, "one", "127.0.0.1")
    other = store.create_session(account, "two", "127.0.0.1")
    with pytest.raises(ValueError, match="unterscheiden"):
        store.change_password(account, old, old, keep)
    store.change_password(account, old, new, keep)
    assert store.authenticate(account.email, old) is None
    assert store.authenticate(account.email, new).id == account.id
    assert store.session_account(keep, "one").id == account.id
    assert store.session_account(other, "two") is None


def test_invalid_unicode_password_is_rejected_and_login_keeps_dummy_hash(tmp_path, monkeypatch):
    invalid = "sicheres-passwort-\ud800"
    with pytest.raises(ValueError, match="ungültige Zeichen"):
        auth.validate_password(invalid)
    store = AuthStore(tmp_path, "TESTCODE")
    hashed = []
    monkeypatch.setattr(auth, "_argon_hash", lambda password, *args: hashed.append(password))
    assert store.authenticate("unknown@example.org", invalid) is None
    assert hashed == [""]


@pytest.mark.parametrize("expression", ["0**-1", "(-0.0)**-2", "0**(-1/2)"])
def test_zero_to_negative_power_is_a_controlled_calculation_error(expression):
    with pytest.raises(CalcError, match="Division durch null"):
        calculate(expression)
    assert calculate("2**-3") == 0.125


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


@pytest.mark.parametrize("nested", ["[" * 1500 + "{}" + "]" * 1500,
                                    '{"@graph":' * 1500 + "{}" + "}" * 1500])
def test_bad_nested_source_json_does_not_discard_valid_product_data(nested):
    html = ('<script type="application/ld+json">' + nested + '</script>'
            '<script type="application/ld+json">'
            '{"@type":"Product","name":"Gültiges Produkt",'
            '"offers":{"price":"10","priceCurrency":"EUR"}}</script>')
    product = extract_product(html, "https://example.org/product")
    assert product and product.name == "Gültiges Produkt" and product.price == "10"


# 16.0.2 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (Gemeinsames Lernen, Recherchecache, Webcams und Satellitenbilder,
# Einstellungen unter Helfer & Grenzen).
