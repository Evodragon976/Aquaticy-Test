"""12.7.8 Luna: Die Größe der virtual machine bleibt gespeichert, und Normal hat 3 GB."""

from pathlib import Path

from aquaticy import web
from aquaticy.auth import Account


def ultra_session(tmp_path: Path, env: str = "", plan: str = "ultra") -> web.ChatSession:
    profile = tmp_path / f"konto-{plan}"
    profile.mkdir(exist_ok=True)
    (profile / ".env").write_text(env, encoding="utf-8")
    return web.ChatSession(Account("u1", "a@example.org", plan, 0), profile)


# 16.0.1 (Aquaticy-Test): 8 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


# 16.0.1 (Aquaticy-Test): 2 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.0 (Aquaticy-Test): test_the_settings_page_and_the_readme_say_three_gigabytes entfaellt.
# Grund: Die Einstellungen der virtual machine gibt es in Aquaticy-Test nicht mehr.


def test_every_saved_setting_is_read_back_for_accounts() -> None:
    """Das war der Fehler: ein Schlüssel, der gespeichert, aber nie wieder gelesen wurde."""
    read = (set(web._STRING_SETTINGS) | set(web._BOOL_SETTINGS) | set(web._INT_SETTINGS))
    # 16.0.1 (Aquaticy-Test): die Groesse der virtual machine gibt es nicht mehr.
    special = {"AQUATICY_LEGAL_GUARD"}  # eigener Zweig in _profile_settings
    assert set(web.SETTING_KEYS) - read == special
