"""OAuth isolation, callback diagnostics and delayed cluster runtime changes."""

from __future__ import annotations

from dataclasses import replace

import pytest
from typer.testing import CliRunner

from aquaticy import cli, web
from tests.test_v965 import parallel_site as parallel_site


@pytest.mark.parametrize("label", ["token", "refresh_token", "refresh-token", "id_token",
                                   "code", "X-Aquaticy-Token", "access_token"])
def test_error_filter_masks_oauth_and_access_credentials(label):
    for message in (f"{label}=unknown-secret-fixture", f'"{label}": "unknown-secret-fixture"'):
        result = web.scrub_error(message, [])
        assert "unknown-secret-fixture" not in result
        assert "••••" in result
    assert web.scrub_error("Das Passwort braucht mindestens 12 Zeichen.", []) == (
        "Das Passwort braucht mindestens 12 Zeichen.")


@pytest.mark.parametrize("plan", ["normal", "pro", "ultra"])
def test_own_google_application_never_inherits_operator_secret(settings, tmp_path, monkeypatch,
                                                              plan):
    operator = replace(settings, google_client_id="operator.apps.googleusercontent.com",
                       google_client_secret="operator-secret-fixture")
    monkeypatch.setattr(web, "get_settings", lambda: operator)
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / ".env").write_text("GOOGLE_CLIENT_ID=own.apps.googleusercontent.com\n")
    loaded = web._profile_settings(profile, plan)
    assert loaded.google_client_id == "own.apps.googleusercontent.com"
    assert loaded.google_client_secret == ""
    assert not web.google_state(loaded)["has_secret"]


def test_shared_google_application_remains_available(settings, tmp_path, monkeypatch):
    operator = replace(settings, google_client_id="operator.apps.googleusercontent.com",
                       google_client_secret="operator-secret-fixture")
    monkeypatch.setattr(web, "get_settings", lambda: operator)
    loaded = web._profile_settings(tmp_path / "profile", "ultra")
    assert loaded.google_client_id == operator.google_client_id
    assert loaded.google_client_secret == operator.google_client_secret


def test_own_google_secret_is_migrated_and_kept(settings, tmp_path, monkeypatch):
    operator = replace(settings, google_client_id="operator.apps.googleusercontent.com",
                       google_client_secret="operator-secret-fixture")
    monkeypatch.setattr(web, "get_settings", lambda: operator)
    profile = tmp_path / "profile"
    profile.mkdir()
    env = profile / ".env"
    env.write_text("GOOGLE_CLIENT_ID=own.apps.googleusercontent.com\n"
                   "GOOGLE_CLIENT_SECRET=own-secret-fixture\n")
    assert web._profile_settings(profile, "ultra").google_client_secret == "own-secret-fixture"
    assert "own-secret-fixture" not in env.read_text()
    assert web._profile_settings(profile, "ultra").google_client_secret == "own-secret-fixture"
    assert web.account_vault(profile).secret("GOOGLE_CLIENT_SECRET") == "own-secret-fixture"


# 16.0.1 (Aquaticy-Test): 3 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 5 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_cli_does_not_advertise_port_zero(monkeypatch):
    monkeypatch.setattr(web, "serve", lambda **kwargs: None)
    result = CliRunner().invoke(cli.app, ["web", "--port", "0", "--no-open"])
    assert result.exit_code == 0 and "nach dem Start" in result.output
    assert "http://127.0.0.1:0/" not in result.output


