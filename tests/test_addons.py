"""Add-ons: installieren, schalten, anmelden -- und was das Modell davon sieht.

Keiner dieser Tests spricht mit GitHub, Open-Meteo oder einem Feed im Netz:
die Antworten kommen aus einem httpx.MockTransport, der gleichzeitig
mitschreibt, WAS gefragt wurde (nur GET? welcher Server?). Die virtual machine ist
gestellt; der echte Behaelter kommt in test_addons_live.py dran.
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import httpx
import pytest

from aquaticy import addons
from aquaticy.config import Settings


@pytest.fixture
def konto(tmp_path: Path) -> Settings:
    ordner = tmp_path / "konto"
    ordner.mkdir()
    return Settings(data_dir=ordner, env_path=ordner / ".env")


def _pro(settings: Settings, user_mode: bool = True) -> Settings:
    settings.vm_user_mode = user_mode
    return settings


def _mock(antworten: dict[str, Any], gefragt: list[httpx.Request]) -> httpx.Client:
    def handler(anfrage: httpx.Request) -> httpx.Response:
        gefragt.append(anfrage)
        for anfang, antwort in antworten.items():
            if str(anfrage.url).startswith(anfang):
                if isinstance(antwort, httpx.Response):
                    return antwort
                return httpx.Response(200, json=antwort)
        return httpx.Response(404, json={"message": "Not Found"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_the_catalogue_has_what_was_asked_for_plus_suggestions() -> None:
    assert "github" in addons.CATALOG
    # 16.0.1 (Aquaticy-Test): WhatsApp, Signal und Blender brauchten die virtual machine.
    for weg in ("whatsapp", "signal", "blender"):
        assert weg not in addons.CATALOG and weg in addons.RETIRED
    vorschlaege = [a for a in addons.CATALOG.values() if a.vorschlag]
    assert len(vorschlaege) >= 2
    for addon in addons.CATALOG.values():
        assert addon.login in {"token", "keine", "feeds", "apikey"}, addon.id
        assert addon.summary and addon.anmelden, addon.id


# 16.0.1 (Aquaticy-Test): 3 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


def test_every_addon_has_install_even_without_download(konto: Settings) -> None:
    addons.install(konto, "github", pro=False)
    eintrag = addons.load_state(konto)["github"]
    assert eintrag["installed"] and eintrag["enabled"]
    assert "github" in addons.active_ids(konto, pro=False)


# 16.0.0 (Aquaticy-Test): test_normal_accounts_get_no_workshop_addons entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


# 16.0.1 (Aquaticy-Test): 10 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.0 (Aquaticy-Test): test_workshop_addons_only_count_with_the_user_mode entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


# 16.0.0 (Aquaticy-Test): test_switching_off_takes_the_volume_out_of_the_workshop entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


def test_switching_needs_an_install(konto: Settings) -> None:
    with pytest.raises(addons.AddOnError, match="nicht installiert"):
        addons.set_enabled(konto, "wetter", True, pro=True)


def test_the_browser_view_carries_no_secret(konto: Settings) -> None:
    addons.install(konto, "github", pro=True)
    geheim = "ghp_" + "S" * 36
    addons._write_secret(konto, addons.GITHUB_TOKEN_KEY, geheim)
    ansicht = addons.public_view(konto, pro=True)
    assert geheim not in json.dumps(ansicht)
    github = next(a for a in ansicht["addons"] if a["id"] == "github")
    assert github["login"]["token_set"] is True


def test_the_state_file_ignores_what_it_does_not_know(konto: Settings) -> None:
    (konto.data_dir / addons.STATE_FILE).write_text(json.dumps(
        {"addons": {"boese": {"installed": True}, "github": "kaputt",
                    "wetter": {"installed": True, "enabled": True}}}))
    assert set(addons.load_state(konto)) == {"wetter"}
    (konto.data_dir / addons.STATE_FILE).write_text("{kein json")
    assert addons.load_state(konto) == {}


class FakeBox:
    """Nimmt die Aufrufe des Installers entgegen und antwortet wie aquaticy-addons."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.aufrufe: list[tuple[str, ...]] = []
        self.gestoppt = False
        self.runtime = None
        FakeBox.letzte = self

    antworten: ClassVar[dict[str, dict[str, Any]]] = {}
    letzte: ClassVar[FakeBox | None] = None

    def ensure(self) -> str:
        return "box"

    def addon_helper(self, *args: str, timeout: int = 0) -> subprocess.CompletedProcess[str]:
        self.aufrufe.append(args)
        antwort = FakeBox.antworten.get(args[0] + ":" + (args[1] if len(args) > 1 else ""),
                                        FakeBox.antworten.get(args[0], {"ok": True}))
        return subprocess.CompletedProcess(args, 0, "Fortschritt\n" + json.dumps(antwort), "")

    def stop(self, reason: str = "") -> None:
        self.gestoppt = True


@pytest.fixture
def fake_werkstatt(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from aquaticy import sandbox as werkstatt

    angelegt: list[str] = []
    monkeypatch.setattr(werkstatt, "find_runtime", lambda: SimpleNamespace(binary="docker"))
    monkeypatch.setattr(werkstatt, "ensure_addon_volume",
                        lambda runtime, volume, image: angelegt.append(volume))

    monkeypatch.setattr(werkstatt, "ensure_image", lambda runtime, image, **kw: None)
    monkeypatch.setattr(werkstatt, "Sandbox", FakeBox)
    FakeBox.antworten = {}
    return angelegt


# 16.0.0 (Aquaticy-Test): test_a_web_app_loads_firefox_first_then_its_profile entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


# 16.0.0 (Aquaticy-Test): test_a_failed_install_says_why_and_counts_as_not_installed entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


# 16.0.0 (Aquaticy-Test): test_no_runtime_means_no_install entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


def test_github_login_checks_the_token_and_stores_it(konto: Settings) -> None:
    addons.install(konto, "github", pro=False)
    gefragt: list[httpx.Request] = []
    client = _mock({"https://api.github.com/user": httpx.Response(
        200, json={"login": "jonas"}, headers={"x-oauth-scopes": "repo, read:user"})}, gefragt)
    ergebnis = addons.github_login(konto, "ghp_" + "x" * 36, client=client)
    assert ergebnis["who"] == "jonas" and "schreiben" in ergebnis["warning"]
    assert gefragt[0].headers["authorization"] == "Bearer ghp_" + "x" * 36
    assert "aquaticy/" in gefragt[0].headers["user-agent"]
    assert addons.github_token(konto) == "ghp_" + "x" * 36
    assert "AQUATICY_GITHUB_TOKEN=ghp_" in konto.env_path.read_text()
    assert addons.load_state(konto)["github"]["login"]["who"] == "jonas"


def test_github_login_refuses_bad_tokens(konto: Settings) -> None:
    addons.install(konto, "github", pro=False)
    with pytest.raises(addons.AddOnError, match="Token"):
        addons.github_login(konto, "nicht ein token; rm -rf")
    client = _mock({"https://api.github.com/user": httpx.Response(401)}, [])
    with pytest.raises(addons.AddOnError, match="kennt"):
        addons.github_login(konto, "ghp_" + "y" * 36, client=client)
    assert addons.github_token(konto) == ""


def test_github_login_needs_the_install(konto: Settings) -> None:
    with pytest.raises(addons.AddOnError, match="installieren"):
        addons.github_login(konto, "ghp_" + "z" * 36)


def test_github_only_ever_reads(konto: Settings) -> None:
    gefragt: list[httpx.Request] = []
    datei = base64.b64encode(b"print('hallo')\n").decode()
    client = _mock({
        "https://api.github.com/repos/jonas/app/issues/7/comments": [{"user": {"login": "a"},
                                                                      "body": "ok"}],
        "https://api.github.com/repos/jonas/app/issues/7": {"number": 7, "title": "Fehler",
                                                             "body": "kaputt"},
        "https://api.github.com/repos/jonas/app/issues": [
            {"number": 1, "title": "Issue"}, {"number": 2, "title": "PR", "pull_request": {}}],
        "https://api.github.com/repos/jonas/app/contents/src/main.py": {
            "encoding": "base64", "size": 15, "content": datei},
    }, gefragt)
    token = "ghp_" + "t" * 36
    issues = addons.github_call(token, "issues", repo="jonas/app", client=client)
    assert [i["nummer"] for i in issues["issues"]] == [1], "Pull Requests sind keine Issues"
    issue = addons.github_call(token, "issue", repo="jonas/app", number="7", client=client)
    assert issue["titel"] == "Fehler" and issue["kommentare"][0]["text"] == "ok"
    inhalt = addons.github_call(token, "datei", repo="jonas/app", path="src/main.py",
                                client=client)
    assert inhalt["text"] == "print('hallo')\n"
    assert {anfrage.method for anfrage in gefragt} == {"GET"}
    assert {anfrage.url.host for anfrage in gefragt} == {"api.github.com"}


@pytest.mark.parametrize(
    ("args", "fehler"),
    [
        ({"action": "loeschen"}, "Unbekannte Aktion"),
        ({"action": "repo", "repo": "nur ein teil"}, "besitzer/name"),
        ({"action": "repo", "repo": ".."}, "besitzer/name"),
        ({"action": "repo", "repo": "a/b/../c"}, "besitzer/name"),
        ({"action": "issue", "repo": "a/b", "number": "sieben"}, "ganze Zahl"),
        ({"action": "issue", "repo": "a/b", "number": -1}, "ganze Zahl"),
        ({"action": "datei", "repo": "a/b", "path": "../../etc/passwd"}, "Pfad"),
        ({"action": "datei", "repo": "a/b", "path": "x", "ref": "main;rm"}, "Branch"),
    ],
)
def test_github_arguments_are_checked_before_asking(args: dict[str, Any], fehler: str) -> None:
    gefragt: list[httpx.Request] = []
    aktion = args.pop("action")
    antwort = addons.github_call("ghp_" + "t" * 36, aktion, client=_mock({}, gefragt), **args)
    assert fehler in antwort["error"]
    assert gefragt == []


def test_github_without_token_asks_nothing() -> None:
    assert "nicht angemeldet" in addons.github_call("", "repos")["error"]


def test_weather_finds_the_place_and_translates_the_codes() -> None:
    gefragt: list[httpx.Request] = []
    client = _mock({
        addons.OPEN_METEO_GEO: {"results": [
            {"name": "Paris", "country": "Vereinigte Staaten", "admin1": "Texas",
             "latitude": 33.6, "longitude": -95.5},
            {"name": "Paris", "country": "Frankreich", "admin1": "Île-de-France",
             "latitude": 48.85, "longitude": 2.35}]},
        addons.OPEN_METEO: {
            "current": {"temperature_2m": 18.2, "weather_code": 61, "wind_speed_10m": 12},
            "daily": {"time": ["2026-09-23", "2026-09-24"], "weather_code": [3, 95],
                      "temperature_2m_max": [19, 21], "temperature_2m_min": [11, 12]}},
    }, gefragt)
    wetter = addons.weather("Paris, Frankreich", days=2, client=client)
    assert wetter["ort"].endswith("Frankreich")
    assert wetter["jetzt"]["wetter"] == "leichter Regen"
    assert [t["wetter"] for t in wetter["tage"]] == ["bedeckt", "Gewitter"]
    vorhersage = gefragt[-1]
    assert vorhersage.url.params["latitude"] == "48.85"
    assert vorhersage.url.params["forecast_days"] == "2"
    assert "Open-Meteo" in wetter["quelle"]


def test_weather_without_a_place_asks_nothing() -> None:
    gefragt: list[httpx.Request] = []
    assert "Ort" in addons.weather("  ", client=_mock({}, gefragt))["error"]
    assert gefragt == []


def test_weather_clamps_the_days() -> None:
    gefragt: list[httpx.Request] = []
    client = _mock({addons.OPEN_METEO_GEO: {"results": [
        {"name": "Bremen", "latitude": 53, "longitude": 8.8}]}, addons.OPEN_METEO: {}}, gefragt)
    addons.weather("Bremen", days=99, client=client)
    assert gefragt[-1].url.params["forecast_days"] == "7"


RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Alt</title><link>https://n.example/alt</link>
<pubDate>Mon, 21 Sep 2026 08:00:00 +0200</pubDate>
<description>&lt;p&gt;Wahl&lt;/p&gt;</description></item>
<item><title>Neu</title><link>/neu</link><pubDate>Tue, 22 Sep 2026 08:00:00 +0200</pubDate>
<description>Wetter</description></item></channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>A</title>
<entry><title>Atom-Eintrag</title><link href="https://a.example/1"/>
<updated>2026-09-23T06:00:00Z</updated><summary>Bahn</summary></entry></feed>"""


def test_feeds_are_parsed_newest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import fetch

    monkeypatch.setattr(fetch, "public_web_url", lambda url: True)
    gefragt: list[httpx.Request] = []
    client = _mock({
        "https://n.example/robots.txt": httpx.Response(404),
        "https://a.example/robots.txt": httpx.Response(404),
        "https://n.example/feed": httpx.Response(200, content=RSS),
        "https://a.example/atom": httpx.Response(200, content=ATOM),
    }, gefragt)
    ergebnis = addons.read_feeds(["https://n.example/feed", "https://a.example/atom"],
                                 client=client)
    assert [e["titel"] for e in ergebnis["eintraege"]] == ["Atom-Eintrag", "Neu", "Alt"]
    assert ergebnis["eintraege"][1]["link"] == "https://n.example/neu"
    assert ergebnis["eintraege"][2]["zusammenfassung"] == "Wahl", "ohne HTML"
    gefiltert = addons.read_feeds(["https://n.example/feed"], query="wetter", client=client)
    assert [e["titel"] for e in gefiltert["eintraege"]] == ["Neu"]


def test_feeds_respect_robots_txt(monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import fetch

    monkeypatch.setattr(fetch, "public_web_url", lambda url: True)
    gefragt: list[httpx.Request] = []
    client = _mock({
        "https://n.example/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /\n"),
        "https://n.example/feed": httpx.Response(200, content=RSS),
    }, gefragt)
    ergebnis = addons.read_feeds(["https://n.example/feed"], client=client)
    assert ergebnis["eintraege"] == [] and "robots" in ergebnis["probleme"][0]
    assert all(anfrage.url.path == "/robots.txt" for anfrage in gefragt)


def test_feeds_never_reach_into_the_home_network() -> None:
    gefragt: list[httpx.Request] = []
    ergebnis = addons.read_feeds(["http://192.168.1.10/feed", "http://localhost/x"],
                                 client=_mock({}, gefragt))
    assert len(ergebnis["probleme"]) == 2 and gefragt == []


def test_redirects_into_the_home_network_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import fetch

    monkeypatch.setattr(fetch, "public_web_url", lambda url: "192.168." not in url)
    gefragt: list[httpx.Request] = []
    client = _mock({
        "https://n.example/robots.txt": httpx.Response(404),
        "https://n.example/feed": httpx.Response(302, headers={"location":
                                                               "http://192.168.1.1/admin"}),
    }, gefragt)
    ergebnis = addons.read_feeds(["https://n.example/feed"], client=client)
    assert ergebnis["probleme"] and not any(a.url.host == "192.168.1.1" for a in gefragt)


def test_feeds_with_entities_are_not_read() -> None:
    bombe = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss>&a;</rss>'
    with pytest.raises(ValueError):
        addons.parse_feed(bombe, "https://x.example/")


def test_the_feed_list_is_checked(konto: Settings) -> None:
    addons.install(konto, "feeds", pro=False)
    assert addons.set_feeds(konto, "https://a.example/rss\n\nhttps://a.example/rss\n") == [
        "https://a.example/rss"]
    for boese in ("http://192.168.0.1/rss", "http://fritz.box/rss", "ftp://x.example/rss",
                  "http://10.1.2.3/"):
        with pytest.raises(addons.AddOnError):
            addons.set_feeds(konto, [boese])
    with pytest.raises(addons.AddOnError, match="Höchstens"):
        addons.set_feeds(konto, [f"https://f{i}.example/rss" for i in range(21)])


def test_tools_exist_only_for_switched_on_addons(konto: Settings) -> None:
    from aquaticy.tools import addon_schemas_for

    def namen() -> list[str]:
        return [s["function"]["name"] for s in addon_schemas_for(konto)]

    assert namen() == []
    addons.install(konto, "github", pro=False)
    assert namen() == [], "ohne Anmeldung kein GitHub-Werkzeug"
    konto.github_token = "ghp_" + "a" * 36
    # 16.0.1 (Aquaticy-Test): GitHub liest nur -- Aendern brauchte die virtual machine.
    assert namen() == ["github"]
    addons.set_rights(konto, "github", {"inhalte": "nein"})
    assert namen() == ["github"], "die Uebersicht bleibt"
    addons.install(konto, "wetter", pro=False)
    addons.install(konto, "feeds", pro=False)
    assert namen() == ["github", "weather"], "ohne eingetragene Feeds kein Feed-Werkzeug"
    addons.set_feeds(konto, ["https://a.example/rss"])
    assert namen() == ["github", "weather", "read_feeds"]
    addons.set_enabled(konto, "github", False, pro=False)
    assert "github" not in namen() and "github_write" not in namen()


# 16.0.0 (Aquaticy-Test): test_blender_in_the_user_mode_comes_from_the_addon entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


def test_the_prompt_names_only_active_addons(konto: Settings) -> None:
    assert addons.prompt_for(konto) == ""
    addons.install(konto, "wetter", pro=False)
    text = addons.prompt_for(konto)
    # 16.0.1 (Aquaticy-Test): keine Messenger mehr -- GitHub liest nur.
    assert "Wetter" in text and "Aendern geht nicht" in text
    assert "WhatsApp" not in text


def test_the_toolbox_refuses_switched_off_addons(konto: Settings) -> None:
    from aquaticy.tools import Toolbox

    box = Toolbox.__new__(Toolbox)
    box.settings = konto
    box.guard = None
    assert "nicht installiert" in box.call("weather", {"place": "Bremen"})["error"]
    assert "nicht installiert" in box.call("github", {"action": "repos"})["error"]


# 16.0.0 (Aquaticy-Test): test_the_desktop_opens_only_active_addon_apps entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


@pytest.mark.parametrize("name", ["whatsapp", "addons", "github", "blender", "login_apps",
                                  "add_ons"])
def test_the_chat_cannot_switch_addons(name: str) -> None:
    from aquaticy.preferences import refusal

    assert refusal(name), name


def _sitzung(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plan: str,
             user_mode: bool = True) -> Any:
    from aquaticy import web

    konto = SimpleNamespace(plan=plan, username="u")
    profil = tmp_path / f"konto-{plan}"
    profil.mkdir(exist_ok=True)
    sitzung = web.ChatSession(account=konto, profile=profil)
    if user_mode and plan in ("pro", "ultra"):
        (profil / ".env").write_text("AQUATICY_VM_USER_MODE=true\n", encoding="utf-8")
    monkeypatch.setattr(web, "SESSION", sitzung)
    return sitzung


def test_unknown_actions_and_addons_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aquaticy import web

    _sitzung(tmp_path, monkeypatch, "pro")
    assert web.addon_action({"action": "hack", "id": "wetter"})[1] == 400
    assert web.addon_action({"action": "install", "id": "../x"})[1] == 400


def test_the_token_goes_in_but_never_comes_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aquaticy import web

    sitzung = _sitzung(tmp_path, monkeypatch, "normal")
    geheim = "ghp_" + "G" * 36

    def pruefe(settings: Any, token: str, **kwargs: Any) -> dict[str, Any]:
        addons._write_secret(settings, addons.GITHUB_TOKEN_KEY, token)
        return {"who": "jonas", "warning": ""}

    monkeypatch.setattr(addons, "github_login", pruefe)
    web.addon_action({"action": "install", "id": "github"})
    antwort, status = web.addon_action({"action": "token", "id": "github", "token": geheim})
    assert status == 200 and "jonas" in antwort["message"]
    assert geheim not in json.dumps(antwort)
    assert sitzung.settings().github_token == geheim, "nach dem Neuaufbau aus der .env gelesen"
    assert geheim not in json.dumps(web.current_values())


# 16.0.0 (Aquaticy-Test): test_login_opens_the_app_for_the_human entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


# 16.0.0 (Aquaticy-Test): test_login_needs_the_user_mode entfaellt.
# Grund: Add-ons in der virtual machine (WhatsApp, Signal, Blender) sind geloescht


class FakeVm:
    alive = True
    user_mode = True

    def __init__(self) -> None:
        self.aufrufe: list[tuple] = []

    def desktop(self, *args: str, stdin: bytes | None = None, timeout: float = 0,
                start: bool = True) -> subprocess.CompletedProcess[bytes]:
        self.aufrufe.append((args, stdin, start))
        return subprocess.CompletedProcess(args, 0, b"{}", b"")


def test_the_ui_has_the_addon_window_and_login_apps() -> None:
    from aquaticy import web

    html = web.UI_FILE.read_text(encoding="utf-8")
    for teil in ('id="btn-addons"', 'id="addonbox"', "Installieren", "Deinstallieren",
                 "/api/addons"):
        assert teil in html, teil
    # 16.0.0 (Aquaticy-Test): ohne virtual machine kein "Selbst anmelden" mehr.
    for weg in ('id="btn-loginapps"', 'id="screenbox"', "/api/werkstatt/eingabe",
                'id="usermode"'):
        assert weg not in html, weg


def test_github_survives_unexpected_answers() -> None:
    """Gefunden beim Fuzzen: eine Liste, wo ein Objekt stehen sollte."""
    client = _mock({"https://api.github.com/": []}, [])
    for aktion in ("ich", "repo", "suche"):
        antwort = addons.github_call("ghp_" + "t" * 36, aktion, repo="a/b", query="x",
                                     client=client)
        assert "unerwartet" in antwort["error"], aktion
