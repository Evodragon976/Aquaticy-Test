"""Konten, Sitzungen und Kontingente."""

from __future__ import annotations

import pytest

from aquaticy.auth import (
    AuthStore,
    RateLimiter,
    new_pro_code,
    pro_code_for,
)

TERMS = {"terms_accepted": True, "terms_version": "test"}


@pytest.fixture
def store(tmp_path):
    return AuthStore(tmp_path, "PRO123456")


def test_normal_account_and_login(store: AuthStore) -> None:
    account = store.register(
        "Mensch@Example.org", "eine sehr lange Passphrase", "normal", **TERMS
    )
    assert account.email == "mensch@example.org"
    assert account.plan == "normal"
    assert store.authenticate(account.email, "eine sehr lange Passphrase") == account
    assert store.authenticate(account.email, "falsch und trotzdem lang genug") is None


def test_registration_keeps_the_chosen_username_and_needs_twelve_characters(
    store: AuthStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seit 9.5.15 mindestens 12 Zeichen -- aeltere, kuerzere bleiben gueltig."""
    import aquaticy.auth as auth_modul

    with pytest.raises(ValueError, match="12 Zeichen"):
        store.register("kurz@example.org", "12345678901", "normal", username="Kurz", **TERMS)
    account = store.register(
        "jonas@example.org", "123456789012", "normal", username="Jonas", **TERMS
    )
    assert account.username == "Jonas"
    assert store.authenticate(account.email, "123456789012") == account

    monkeypatch.setattr(auth_modul, "MIN_PASSWORD", 7)
    alt = store.register("alt@example.org", "1234567", "normal", username="Alt", **TERMS)
    monkeypatch.setattr(auth_modul, "MIN_PASSWORD", 12)
    assert store.authenticate(alt.email, "1234567") == alt


def test_free_accounts_get_a_session_and_a_weekly_budget() -> None:
    """Seit 9.5.23: 300.000 je 5-Stunden-Sitzung, 2 Mio. je Woche (aquaticy/quota.py)."""
    from aquaticy.quota import SESSION_TOKENS, WEEK_TOKENS

    assert (SESSION_TOKENS, WEEK_TOKENS) == (300_000, 2_000_000)


def test_each_plan_has_its_own_budget(tmp_path) -> None:
    """Pro: je ein Drittel mehr als vorher -- 533.333 und 4 Mio. (9.5.23)."""
    from aquaticy.auth import AuthStore

    store = AuthStore(tmp_path, "PRO123456")
    normal = store.register("n@example.org", "eine sehr lange Passphrase", "normal", **TERMS)
    pro = store.register("p@example.org", "eine sehr lange Passphrase", "pro", "PRO123456",
                         **TERMS)
    q_normal, q_pro = store.quota(normal), store.quota(pro)
    assert (q_normal.session_tokens, q_normal.week_tokens) == (300_000, 2_000_000)
    assert (q_pro.session_tokens, q_pro.week_tokens) == (533_333, 4_000_000)


def test_registration_requires_and_records_explicit_terms(store: AuthStore) -> None:
    with pytest.raises(ValueError, match="ausdrücklich"):
        store.register("nein@example.org", "eine sehr lange Passphrase", "normal")
    account = store.register(
        "ja@example.org", "eine sehr lange Passphrase", "normal", **TERMS
    )
    with store._connect() as conn:
        row = conn.execute(
            "SELECT terms_version, terms_accepted_at FROM users WHERE id=?", (account.id,)
        ).fetchone()
    assert row["terms_version"] == "test"
    assert row["terms_accepted_at"] > 0


def test_pro_needs_the_secret_code(store: AuthStore) -> None:
    with pytest.raises(ValueError, match="Pro-Code"):
        store.register(
            "a@example.org", "eine sehr lange Passphrase", "pro", "FALSCH123", **TERMS
        )
    account = store.register(
        "a@example.org", "eine sehr lange Passphrase", "pro", "pro123456", **TERMS
    )
    assert account.pro


def test_pro_accepts_the_terminal_label_when_copied(store: AuthStore) -> None:
    account = store.register(
        "copy@example.org",
        "eine sehr lange Passphrase",
        "pro",
        f"Pro-Code: {store.pro_code} (9 Zeichen, geheim halten)",
        **TERMS,
    )
    assert account.pro


def test_duplicate_email_and_short_password_are_rejected(store: AuthStore) -> None:
    with pytest.raises(ValueError, match="12 Zeichen"):
        store.register("a@example.org", "kurz", "normal", **TERMS)
    store.register("a@example.org", "eine sehr lange Passphrase", "normal", **TERMS)
    with pytest.raises(ValueError, match="kein neues Konto"):
        store.register("A@example.org", "noch eine lange Passphrase", "normal", **TERMS)


def test_session_is_random_device_bound_and_revocable(store: AuthStore) -> None:
    account = store.register(
        "a@example.org", "eine sehr lange Passphrase", "normal", **TERMS
    )
    token = store.create_session(account, "Firefox|de", "192.168.1.4")
    assert token != store.create_session(account, "Firefox|de", "192.168.1.4")
    assert store.session_account(token, "Firefox|de") == account
    assert store.session_account(token, "anderes Geraet") is None
    store.logout(token)
    assert store.session_account(token, "Firefox|de") is None


def test_pro_code_is_nine_characters_and_persists(tmp_path) -> None:
    generated = pro_code_for(tmp_path)
    assert len(generated) == 9 and generated.isalnum()
    assert pro_code_for(tmp_path) == generated
    assert len(new_pro_code()) == 9


def test_rate_limiter_opens_again_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [10.0]
    monkeypatch.setattr("aquaticy.auth.time.monotonic", lambda: now[0])
    limiter = RateLimiter(attempts=2, window_seconds=10)
    assert limiter.allow("client")
    assert limiter.allow("client")
    assert not limiter.allow("client")
    now[0] = 21.0
    assert limiter.allow("client")


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


def test_an_old_single_account_logs_in_by_username_in_the_account_system(tmp_path) -> None:
    """16.0.1 (Aquaticy-Test): Ein Einzelkonto hat nur eine interne Adresse -- der Name reicht."""
    ultra = "Ab3-defghijklm"
    alt = AuthStore(tmp_path, "PRO123456", ultra_code=ultra, single=True)
    konto = alt.register("", "eine sehr lange Passphrase", "ultra", ultra, username="Louis")
    neu = AuthStore(tmp_path, "PRO123456", ultra_code=ultra, single=False)
    assert neu.login("louis", "eine sehr lange Passphrase") == konto
    assert neu.login(" Louis ", "eine sehr lange Passphrase") == konto
    assert neu.login("Louis", "falsch und trotzdem lang genug") is None
    assert neu.login("niemand", "eine sehr lange Passphrase") is None
    assert neu.login(konto.email, "eine sehr lange Passphrase") == konto
    assert neu.login_key("LOUIS") == neu.login_key(konto.email.upper()) == konto.email
