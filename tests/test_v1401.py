"""Besitzerrechte, Secure-Pro-Chats und sichere Voice-Schalter."""

import json
import shutil
from types import SimpleNamespace

import pytest

from aquaticy import voice, web
from aquaticy.config import Settings
from tests.test_end_to_end import _req
from tests.test_v1300_luna import _anlegen, _zustimmung, server  # noqa: F401


@pytest.fixture
def owner(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path)
    account = SimpleNamespace(id="owner")
    session = SimpleNamespace(account=account, ultra=True, settings=lambda: settings,
                              chat_id=lambda: "secure-chat")
    auth = SimpleNamespace(single=True, ensure_owner_ultra=lambda: account)
    monkeypatch.setattr(web, "AUTH", auth)
    monkeypatch.setattr(web, "_native_paused", lambda account: False)
    monkeypatch.setattr(web, "get_settings", lambda: settings)
    monkeypatch.setattr(voice, "root", lambda: tmp_path)
    monkeypatch.setattr(web, "SECURE_WATCHER", None)
    return session, settings


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 3 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_feature_markup_and_english_translations_exist():
    html = web.UI_FILE.read_text()
    # 16.0.0 (Aquaticy-Test): Secure Pro nur noch als Chat; keine Sprachnachrichten (Messenger).
    assert 'id="secure-open"' in html and 'id="voice-setting"' not in html
    assert 'id="secure-panel"' in html and 'chat.secure_pro' in html
    assert 'Open Secure Pro chat' in html


def test_owner_can_open_marked_chat_with_model_and_command_gate(server):  # noqa: F811
    assert _req(server, "GET", "/api/features")[0] == 401
    consent = _zustimmung(server)
    status, headers, _ = _anlegen(server, consent)
    assert status == 200
    cookie = consent + "; " + headers["Set-Cookie"].split(";", 1)[0]
    status, _, raw = _req(server, "POST", "/api/features", {"action": "open"}, cookie)
    assert status == 200, raw
    chat_id = json.loads(raw)["session_id"]
    status, _, raw = _req(server, "POST", "/api/open", {"session_id": chat_id}, cookie)
    assert status == 200 and json.loads(raw)["secure_pro"] is True
    status, _, raw = _req(server, "GET", "/api/chats", cookie=cookie)
    assert any(c["session_id"] == chat_id and c["secure_pro"] for c in json.loads(raw)["chats"])
    status, _, raw = _req(server, "POST", "/api/chat",
                          {"message": "Erkläre meinen Secure-Pro-Status."}, cookie)
    assert status == 200 and b'"done"' in raw
    assert _req(server, "POST", "/api/command", {"line": "/max Angriff"}, cookie)[0] == 409
    # 16.0.1 (Aquaticy-Test): /api/features kennt nur noch "open" -- Fragen gehen in den Chat.
    assert _req(server, "POST", "/api/features",
                {"action": "message", "message": "Status"}, cookie)[0] == 400


@pytest.mark.parametrize("width", [1280, 390])
def test_settings_open_secure_chat_in_real_browser(server, monkeypatch, width):  # noqa: F811
    playwright = pytest.importorskip("playwright.sync_api")
    browser_path = shutil.which("chromium") or shutil.which("chromium-browser")
    if not browser_path:
        pytest.skip("Chromium fehlt")
    from tests.test_end_to_end import AGENT, SPRACHE

    consent = _zustimmung(server)
    status, headers, _ = _anlegen(server, consent)
    assert status == 200
    cookie = consent + "; " + headers["Set-Cookie"].split(";", 1)[0]
    monkeypatch.setattr(voice, "ready", lambda directory: True)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=browser_path, headless=True,
                                    args=["--no-sandbox"])
        context = browser.new_context(user_agent=AGENT, viewport={"width": width, "height": 900},
                                      extra_http_headers={"Cookie": cookie,
                                                          "Accept-Language": SPRACHE})
        page = context.new_page()
        page.goto(f"http://127.0.0.1:{server}")
        if width < 600:
            page.locator("#btn-side").click()
        page.locator("#btn-settings").click()
        page.locator("#voice-setting").wait_for(state="visible")
        page.locator("#voice-setting").check()
        playwright.expect(page.locator("#voice-setting")).to_be_enabled()
        assert json.loads(_req(server, "GET", "/api/features", cookie=cookie)[2])["voice"]
        page.locator("#voice-setting").uncheck()
        playwright.expect(page.locator("#voice-setting")).to_be_enabled()
        page.locator("#secure-setting").check()
        page.locator("#secure-subnet").fill("192.168.1.0/24")
        page.locator("#secure-consent").check()
        page.locator("#secure-apply").click()
        playwright.expect(page.locator("#secure-note")).to_contain_text("ist an")
        page.locator("#secure-open").click()
        page.locator("#secure-panel").wait_for(state="visible")
        assert page.locator("#thread").inner_text().count("Secure Pro") >= 1
        assert page.locator(".recent .art").filter(has_text="Secure Pro").count() >= 1
        page.locator("#secure-settings-open").click()
        page.locator("#secure-controls").wait_for(state="visible")
        page.locator("#secure-disable").click()
        playwright.expect(page.locator("#secure-note")).to_contain_text("ist aus")
        page.reload()
        if width < 600:
            page.locator("#btn-side").click()
        page.locator(".recent .name").filter(has_text="Secure Pro").first.click()
        page.locator("#secure-panel").wait_for(state="visible")
        browser.close()
