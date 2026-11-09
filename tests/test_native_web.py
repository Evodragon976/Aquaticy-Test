"""Direkte Kopplung im Web (aquaticy/web.py): Aktion, Ansicht, Start und Stopp, Oberfläche."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aquaticy import bridge, web
from aquaticy import messenger_native as nat
from aquaticy.auth import Account
from aquaticy.messenger_native import NativeHub, NativeStore
from tests.test_messenger_native import StubTransport, stub_factory
from tests.test_v965 import parallel_site as parallel_site

WEB = Path(web.__file__).parent
ICH = "+4915100000000"
PAIRING = "2@AbCdEfGhIjKlMnOpQrStUv,WxYz0123456789AbCdEfGhIjKlMnOp=,QrStUvWxYz0123456789AbCdEf=,1"


REG: dict[str, web.ChatSession] = {}


def session_of(tmp_path: Path, plan: str = "ultra") -> web.ChatSession:
    profil = tmp_path / f"konto-{plan}"
    profil.mkdir(exist_ok=True)
    (profil / ".env").write_text("", encoding="utf-8")
    session = web.ChatSession(Account("u1", "a@example.org", plan, 0), profil)
    REG["u1"] = session
    return session


@pytest.fixture
def hub_of(monkeypatch: pytest.MonkeyPatch):
    """Ersetzt die echten Verbindungen durch gestellte -- der Rest ist echt."""
    monkeypatch.setattr(web, "USER_NATIVE", {})
    monkeypatch.setattr(web, "NATIVE_HUB", None)
    monkeypatch.setattr(web.SESSIONS, "get", lambda account: REG[account.id])
    hubs: list[NativeHub] = []

    def bauen(get_session: Any, account: Any, directory: Path) -> NativeHub:
        def gewollt(name: str) -> bool:
            return bool(bridge.load_config(get_session().settings())[name]["an"])

        hub = NativeHub(directory, lambda m, t: None, gewollt, factories={
            "whatsapp": stub_factory(), "signal": stub_factory(True, "signal")})
        hub.answerer = SimpleNamespace(close=lambda: None)  # type: ignore[attr-defined]
        hubs.append(hub)
        return hub

    monkeypatch.setattr(web, "_build_native_hub", bauen)
    yield hubs
    for hub in hubs:
        hub.stop()


# -- native_action -----------------------------------------------------------------------------
def test_only_ultra_may_link(tmp_path: Path, hub_of) -> None:
    antwort, status = web.native_action(session_of(tmp_path, "pro"),
                                        {"action": "link", "id": "whatsapp"})
    assert status == 403 and not antwort["ok"] and hub_of == []


@pytest.mark.parametrize("daten", [
    {}, {"action": "link"}, {"id": "whatsapp"}, {"action": "hack", "id": "whatsapp"},
    {"action": "link", "id": "telegram"}, {"action": "link", "id": "../x"},
    {"action": 5, "id": ["whatsapp"]},
])
def test_unknown_actions_and_messengers_are_refused(tmp_path: Path, hub_of, daten: Any) -> None:
    assert web.native_action(session_of(tmp_path), daten)[1] == 400


def test_the_whole_linking_way(tmp_path: Path, hub_of) -> None:
    session = session_of(tmp_path)
    antwort, status = web.native_action(session, {"action": "status", "id": "whatsapp"})
    assert status == 200 and antwort["state"] == "aus" and not antwort["linked"]
    assert antwort["available"] and antwort["image"] is None
    antwort, status = web.native_action(session, {"action": "link", "id": "whatsapp"})
    assert status == 200 and antwort["state"] == "verbunden" and antwort["who"] == ICH
    transport = hub_of[0].transport("whatsapp")
    assert transport.started == 1
    # Solange der QR-Code gebraucht wird, kommt er als Bild -- nie als Text.
    transport._set(nat.QR, qr=PAIRING)
    antwort, _ = web.native_action(session, {"action": "status", "id": "whatsapp"})
    assert antwort["state"] == "qr" and antwort["image"].startswith("data:image/png;base64,")
    assert PAIRING not in str(antwort), "der Kopplungscode selbst verlässt den Server nicht"


def test_a_text_that_is_no_pairing_code_is_never_drawn(tmp_path: Path, hub_of) -> None:
    session = session_of(tmp_path)
    web.native_action(session, {"action": "link", "id": "whatsapp"})
    hub_of[0].transport("whatsapp")._set(nat.QR, qr="https://evil.example/login?x=1")
    antwort, status = web.native_action(session, {"action": "status", "id": "whatsapp"})
    assert status == 200 and antwort["image"] is None


def test_linking_without_the_library_says_what_is_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hub_of) -> None:
    monkeypatch.setattr(web, "_build_native_hub", lambda g, a, d: _hub_ohne_bibliothek(d))
    antwort, status = web.native_action(session_of(tmp_path), {"action": "link", "id": "signal"})
    assert status == 400 and "signal-cli" in antwort["error"]


def _hub_ohne_bibliothek(directory: Path) -> NativeHub:
    class Fehlt(StubTransport):
        def available(self) -> tuple[bool, str]:
            return False, "signal-cli fehlt"

    hub = NativeHub(directory, lambda m, t: None, lambda n: False, factories={
        "whatsapp": lambda d, m, on_connected=None, clock=None: Fehlt(d, m, on_connected, ok=False),
        "signal": lambda d, m, on_connected=None, clock=None: Fehlt(
            d, m, on_connected, ok=False, name="signal")})
    hub.answerer = SimpleNamespace(close=lambda: None)  # type: ignore[attr-defined]
    return hub


def test_unlinking_switches_the_bridge_off_and_names_the_phone_step(
        tmp_path: Path, hub_of) -> None:
    session = session_of(tmp_path)
    settings = session.settings()
    NativeStore(nat.native_dir(settings)).set("whatsapp", ICH)
    bridge.set_config(settings, "whatsapp", {"an": True})
    antwort, status = web.native_action(session, {"action": "unlink", "id": "whatsapp"})
    assert status == 200 and "Verknüpfte Geräte" in antwort["message"]
    assert not antwort["linked"]
    assert bridge.load_config(settings)["whatsapp"]["an"] is False


def test_cancelling_removes_a_half_finished_link(tmp_path: Path, hub_of) -> None:
    session = session_of(tmp_path)
    web.native_action(session, {"action": "link", "id": "whatsapp"})
    sitzung = nat.native_dir(session.settings()) / "whatsapp"
    sitzung.mkdir(parents=True, exist_ok=True)
    (sitzung / "session.sqlite3").write_text("x", encoding="utf-8")
    NativeStore(nat.native_dir(session.settings())).clear("whatsapp")
    web.native_action(session, {"action": "cancel", "id": "whatsapp"})
    assert not sitzung.exists()


def test_an_unexpected_error_is_a_clean_500(tmp_path: Path, hub_of) -> None:
    session = session_of(tmp_path)
    web._native_hub(session).link = lambda m: (_ for _ in ()).throw(KeyError("geheim"))  # type: ignore[method-assign]
    antwort, status = web.native_action(session, {"action": "link", "id": "whatsapp"})
    assert status == 500 and not antwort["ok"]


# -- Ansicht -----------------------------------------------------------------------------------
# 16.0.0 (Aquaticy-Test): entfaellt:
# test_the_add_on_window_shows_the_direct_link_only_for_ultra_messengers
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


def test_the_add_on_window_opens_even_if_the_direct_link_breaks(
        tmp_path: Path, hub_of, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "native_view",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaputt")))
    ansicht = web.addons_view(session_of(tmp_path))
    assert ansicht["addons"] and not any("native" in a for a in ansicht["addons"])


# -- Die Brücke einschalten --------------------------------------------------------------------
def test_a_linked_messenger_needs_no_vm_to_switch_the_bridge_on(tmp_path: Path, hub_of) -> None:
    session = session_of(tmp_path)
    settings = session.settings()
    assert not settings.vm_user_mode
    with pytest.raises(Exception, match="User mode"):
        web._bridge_action(session, settings, "whatsapp", {"an": True})
    NativeStore(nat.native_dir(settings)).set("whatsapp", ICH)
    hinweis = web._bridge_action(session, settings, "whatsapp", {"an": True, "wer": "selbst"})
    assert "sofort" in hinweis
    assert bridge.load_config(settings)["whatsapp"]["an"] is True
    assert hub_of[0].transport("whatsapp").started == 1
    assert "aus" in web._bridge_action(session, settings, "whatsapp", {"an": False})
    assert web.USER_BRIDGES == {}, "kein Bildschirm-Lauf für eine direkte Kopplung"


def test_a_pro_account_still_cannot_switch_it_on(tmp_path: Path, hub_of) -> None:
    session = session_of(tmp_path, "pro")
    NativeStore(nat.native_dir(session.settings())).set("whatsapp", ICH)
    with pytest.raises(Exception, match="Ultra"):
        web._bridge_action(session, session.settings(), "whatsapp", {"an": True})


# -- Start und Stopp ---------------------------------------------------------------------------
class Auth:
    def __init__(self, ordner: Path) -> None:
        self.ordner = ordner

    def profile_dir(self, konto_id: str) -> Path:
        return self.ordner


def test_login_starts_a_hub_only_for_a_linked_and_switched_on_messenger(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hub_of) -> None:
    monkeypatch.setattr(web, "AUTH", Auth(tmp_path))
    monkeypatch.setattr(web, "USER_BRIDGES", {})
    konto = SimpleNamespace(id="u1")
    web.start_user_bridge(konto)
    assert hub_of == [] and web.USER_NATIVE == {}
    NativeStore(tmp_path / "messenger").set("whatsapp", ICH)
    settings = SimpleNamespace(data_dir=tmp_path)
    bridge.set_config(settings, "whatsapp", {"an": False})
    web.start_user_bridge(konto)
    assert hub_of == [], "gekoppelt, aber aus: nichts startet"
    bridge.set_config(settings, "whatsapp", {"an": True})
    monkeypatch.setattr(web.SESSIONS, "get", lambda account: SimpleNamespace(
        settings=lambda: SimpleNamespace(data_dir=tmp_path)))
    web.start_user_bridge(konto)
    assert len(hub_of) == 1 and hub_of[0].transport("whatsapp").started == 1
    assert web.USER_BRIDGES == {}, "alles direkt gekoppelt: kein Bildschirm-Lauf"


def test_login_starts_the_screen_runner_for_what_is_not_linked_directly(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hub_of) -> None:
    monkeypatch.setattr(web, "AUTH", Auth(tmp_path))
    monkeypatch.setattr(web, "USER_BRIDGES", {})
    gebaut: list[str] = []

    class Laeufer:
        def ensure_running(self) -> bool:
            gebaut.append("start")
            return True

    monkeypatch.setattr(web, "_build_bridge_runner", lambda g, a: Laeufer())
    NativeStore(tmp_path / "messenger").set("whatsapp", ICH)
    settings = SimpleNamespace(data_dir=tmp_path)
    bridge.set_config(settings, "whatsapp", {"an": True})
    bridge.set_config(settings, "signal", {"an": True})
    monkeypatch.setattr(web.SESSIONS, "get", lambda account: SimpleNamespace(
        settings=lambda: SimpleNamespace(data_dir=tmp_path)))
    web.start_user_bridge(SimpleNamespace(id="u1"))
    assert gebaut == ["start"] and len(hub_of) == 1


def test_a_server_that_is_not_home_never_opens_the_connection(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hub_of) -> None:
    """Zwei Verbindungen derselben Sitzung verdrängen sich: nur der Heimserver verbindet."""
    monkeypatch.setattr(web, "AUTH", Auth(tmp_path))
    monkeypatch.setattr(web, "USER_BRIDGES", {})
    monkeypatch.setattr(web, "CLUSTER", SimpleNamespace(is_home=lambda konto_id: False))
    NativeStore(tmp_path / "messenger").set("whatsapp", ICH)
    bridge.set_config(SimpleNamespace(data_dir=tmp_path), "whatsapp", {"an": True})
    web.start_user_bridge(SimpleNamespace(id="u1"))
    assert hub_of == [] and web.USER_NATIVE == {}


def test_stopping_everything_stops_the_hubs(monkeypatch: pytest.MonkeyPatch) -> None:
    gestoppt: list[str] = []

    class Hub:
        def __init__(self, name: str) -> None:
            self.name = name
            self.answerer = SimpleNamespace(close=lambda: gestoppt.append(name + "-close"))

        def stop(self) -> None:
            gestoppt.append(self.name)

    monkeypatch.setattr(web, "USER_NATIVE", {"a": Hub("a")})
    monkeypatch.setattr(web, "NATIVE_HUB", Hub("b"))
    web._stop_schedulers()
    assert sorted(gestoppt) == ["a", "a-close", "b", "b-close"]
    assert web.USER_NATIVE == {} and web.NATIVE_HUB is None


def test_forgetting_an_account_stops_its_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    gestoppt: list[str] = []

    class Hub:
        answerer = SimpleNamespace(close=lambda: None)

        def __init__(self, name: str) -> None:
            self.name = name

        def stop(self) -> None:
            gestoppt.append(self.name)

    monkeypatch.setattr(web, "USER_NATIVE", {"u1": Hub("meins"), "u2": Hub("fremdes")})
    monkeypatch.setattr(web, "USER_BRIDGES", {})
    monkeypatch.setattr(web, "AUTH", None)
    web.forget_account_runtime(SimpleNamespace(id="u1"))
    assert gestoppt == ["meins"] and list(web.USER_NATIVE) == ["u2"]


def test_the_direct_bridge_waits_for_a_downgrade_a_ban_and_another_home(
        monkeypatch: pytest.MonkeyPatch) -> None:
    konto = SimpleNamespace(id="u1")
    monkeypatch.setattr(web, "AIGUARD", None)
    monkeypatch.setattr(web, "CLUSTER", None)
    monkeypatch.setattr(web, "_plan_of", lambda konto_id, fallback: "ultra")
    assert web._native_paused(konto) is False
    assert web._native_paused(None) is False
    monkeypatch.setattr(web, "_plan_of", lambda konto_id, fallback: "pro")
    assert web._native_paused(konto) is True
    monkeypatch.setattr(web, "_plan_of", lambda konto_id, fallback: "ultra")
    monkeypatch.setattr(web, "AIGUARD", SimpleNamespace(is_banned=lambda user_id: "gesperrt"))
    assert web._native_paused(konto) is True
    monkeypatch.setattr(web, "AIGUARD", None)
    monkeypatch.setattr(web, "CLUSTER", SimpleNamespace(is_home=lambda konto_id: False))
    assert web._native_paused(konto) is True


def test_the_real_hub_builder_wires_answerer_and_rules(tmp_path: Path) -> None:
    """Der echte Bau (ohne gestellte Teile): Hub, Antwortgeber, Wunsch aus der Einstellung."""
    from aquaticy.config import Settings

    konto = Settings(data_dir=tmp_path, env_path=tmp_path / ".env")
    hub = web._build_native_hub(lambda: SimpleNamespace(settings=lambda: konto), None,
                                nat.native_dir(konto))
    try:
        assert isinstance(hub, NativeHub) and hub.directory == tmp_path / "messenger"
        assert hub._wanted("whatsapp") is False
        bridge.set_config(konto, "whatsapp", {"an": True})
        assert hub._wanted("whatsapp") is True
        assert hub.ensure_running() == [], "nichts gekoppelt: nichts startet"
    finally:
        hub.stop()
        hub.answerer.close()


# -- Oberfläche --------------------------------------------------------------------------------
def _ui() -> str:
    return (WEB / "webui.html").read_text(encoding="utf-8")


# 16.0.0 (Aquaticy-Test): test_the_page_has_the_native_section_dialog_and_route entfaellt.
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


def test_every_native_text_the_server_shows_has_english() -> None:
    import json

    html = _ui()
    en = json.loads(re.search(r"const EN = (\{.*?\n\});", html, re.S).group(1))
    quelle = (WEB / "messenger_native.py").read_text(encoding="utf-8")
    quelle = re.sub(r'"\s*\n\s*"', "", quelle)
    for satz in (nat.NEED_SIGNAL_CLI, nat.NEED_LIBMAGIC, nat.NEED_NEONIZE,
                 "WhatsApp hat die Kopplung beendet (am Handy abgemeldet).",
                 "Das Koppeln hat nicht geklappt. Versuch es erneut.",
                 "Der QR-Code ist abgelaufen. Verbinde noch einmal.",
                 "signal-cli wurde beendet.",
                 "Die gespeicherte Nummer ist ungültig. Verbinde noch einmal."):
        assert satz in en and satz in quelle, satz
    assert re.search(r"Prüfe die Internetverbindung", html), "Muster für 'nicht erreichbar'"


def _chromium() -> str | None:
    found = shutil.which("chromium")
    if found:
        return found
    return "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None


# 16.0.0 (Aquaticy-Test): test_the_dialog_shows_the_qr_then_closes_when_connected entfaellt.
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


def web_qr_data_url() -> str:
    from aquaticy.messenger_login import render_qr

    return render_qr(PAIRING)


def test_the_route_needs_a_login_the_same_origin_and_ultra(parallel_site) -> None:
    import httpx

    client, _, _, _, _, url = parallel_site
    with httpx.Client(base_url=url, trust_env=False) as fremd:
        assert fremd.post("/api/messenger/native", json={}).status_code == 401
    schlecht = client.post("/api/messenger/native", json={"action": "link", "id": "whatsapp"},
                           headers={"Origin": "https://evil.example"})
    assert schlecht.status_code == 403
    normal = client.post("/api/messenger/native", json={"action": "link", "id": "whatsapp"})
    assert normal.status_code == 403 and normal.headers["Cache-Control"] == "no-store"
    assert "Ultra" in normal.json()["error"]
