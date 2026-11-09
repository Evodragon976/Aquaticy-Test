"""Vercel-Modus (Aquaticy-Test): ganze App als WSGI, verschluesselte Sicherung im Blob-Speicher."""

from __future__ import annotations

import io
import json
import tarfile
import tomllib
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "vercel_blob_rw_AbCdEf123_geheimerTeil"
SECRET = "x" * 40


@pytest.fixture(autouse=True)
def _no_vercel_credentials(monkeypatch):
    """Keine Zugangsdaten aus der Umgebung des Rechners, auf dem die Tests laufen."""
    from aquaticy import vercel_blob

    for name in ("AQUATICY_BLOB_TOKEN", "BLOB_READ_WRITE_TOKEN", "BLOB_STORE_ID",
                 "VERCEL_OIDC_TOKEN", "AQUATICY_VERCEL_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(vercel_blob, "OIDC_TOKEN", "")


@pytest.fixture
def blob_env(monkeypatch):
    monkeypatch.setenv("AQUATICY_BLOB_TOKEN", TOKEN)
    monkeypatch.setenv("AQUATICY_VERCEL_SECRET", SECRET)


class FakeBlob:
    """Ein privater Blob-Speicher im Speicher -- prueft die Kopfzeilen wie das SDK."""

    def __init__(self) -> None:
        self.data: bytes | None = None
        self.puts: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            self.puts.append(request)
            self.data = request.content
            return httpx.Response(200, json={"pathname": request.url.params["pathname"]})
        if self.data is None:
            return httpx.Response(404)
        return httpx.Response(200, content=self.data)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def names(archiv: bytes) -> list[str]:
    with tarfile.open(fileobj=io.BytesIO(archiv), mode="r:gz") as tar:
        return tar.getnames()


def test_pyproject_points_vercel_to_the_full_app():
    daten = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert daten["tool"]["vercel"]["entrypoint"] == "aquaticy.vercel:app"


def test_store_id_from_token():
    from aquaticy import vercel_blob

    assert vercel_blob.store_id(TOKEN) == "AbCdEf123"
    with pytest.raises(vercel_blob.BlobError):
        vercel_blob.store_id("kaputt")
    with pytest.raises(vercel_blob.BlobError):
        vercel_blob.store_id("vercel_blob_rw_../x_y")


def test_credentials_follow_the_sdk_order(monkeypatch):
    from aquaticy import vercel_blob

    assert vercel_blob.credentials() is None
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", TOKEN)
    assert vercel_blob.credentials() == (TOKEN, "AbCdEf123")
    monkeypatch.setenv("BLOB_STORE_ID", "store_4FlvBGIR3Zq")
    assert vercel_blob.credentials() == (TOKEN, "AbCdEf123")
    monkeypatch.setattr(vercel_blob, "OIDC_TOKEN", "oidc-jwt")
    assert vercel_blob.credentials() == ("oidc-jwt", "4FlvBGIR3Zq")
    monkeypatch.setenv("AQUATICY_BLOB_TOKEN", "vercel_blob_rw_Eigen1_x")
    assert vercel_blob.credentials() == ("vercel_blob_rw_Eigen1_x", "Eigen1")
    monkeypatch.delenv("AQUATICY_BLOB_TOKEN")
    monkeypatch.setenv("BLOB_STORE_ID", "store_../böse")
    with pytest.raises(vercel_blob.BlobError):
        vercel_blob.credentials()


def test_save_and_restore_with_oidc(monkeypatch, tmp_path):
    from aquaticy import vercel_blob

    monkeypatch.setenv("AQUATICY_VERCEL_SECRET", SECRET)
    monkeypatch.setenv("BLOB_STORE_ID", "store_4FlvBGIR3Zq")
    monkeypatch.setattr(vercel_blob, "OIDC_TOKEN", "oidc-jwt")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.txt").write_text("1", encoding="utf-8")
    blob = FakeBlob()
    gelesen: list[httpx.Request] = []

    def mitlesen(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            gelesen.append(request)
        return blob(request)

    client = httpx.Client(transport=httpx.MockTransport(mitlesen))
    assert vercel_blob.save(tmp_path / "a", client=client)
    assert blob.puts[0].headers["authorization"] == "Bearer oidc-jwt"
    assert blob.puts[0].headers["x-vercel-blob-store-id"] == "4FlvBGIR3Zq"
    assert vercel_blob.restore(tmp_path / "b", client=client) == 1
    assert gelesen[0].url.host == "4flvbgir3zq.private.blob.vercel-storage.com"
    assert gelesen[0].headers["authorization"] == "Bearer oidc-jwt"


def test_no_backup_without_long_secret(monkeypatch, tmp_path):
    from aquaticy import vercel_blob

    monkeypatch.setenv("AQUATICY_BLOB_TOKEN", TOKEN)
    monkeypatch.setenv("AQUATICY_VERCEL_SECRET", "zu-kurz")
    assert not vercel_blob.enabled()
    assert vercel_blob.save(tmp_path) is False
    assert vercel_blob.restore(tmp_path) == 0


def test_pack_skips_links_and_caches(tmp_path):
    from aquaticy import vercel_blob

    quelle = tmp_path / "home"
    (quelle / ".aquaticy" / "cache").mkdir(parents=True)
    (quelle / ".aquaticy" / "konten.json").write_text("{}", encoding="utf-8")
    (quelle / ".aquaticy" / "cache" / "gross.bin").write_bytes(b"x")
    (quelle / "link").symlink_to("/etc/passwd")
    namen = names(vercel_blob.pack(quelle))
    assert namen == [".aquaticy/konten.json"]


def test_unpack_refuses_paths_outside_and_links(tmp_path):
    from aquaticy import vercel_blob

    puffer = io.BytesIO()
    with tarfile.open(fileobj=puffer, mode="w:gz") as archiv:
        for name in ("../draussen.txt", "/abs.txt", "ok/datei.txt"):
            info = tarfile.TarInfo(name)
            info.size = 2
            archiv.addfile(info, io.BytesIO(b"hi"))
        link = tarfile.TarInfo("ok/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archiv.addfile(link)
    ziel = tmp_path / "ziel"
    assert vercel_blob.unpack(puffer.getvalue(), ziel) == 1
    assert (ziel / "ok" / "datei.txt").read_bytes() == b"hi"
    assert not (tmp_path / "draussen.txt").exists()
    assert not (ziel / "ok" / "link").exists()


def test_save_is_encrypted_private_and_restores(blob_env, tmp_path):
    from aquaticy import vercel_blob

    quelle = tmp_path / "a"
    (quelle / ".aquaticy").mkdir(parents=True)
    (quelle / ".aquaticy" / "notiz.txt").write_text("streng geheim", encoding="utf-8")
    blob = FakeBlob()
    assert vercel_blob.save(quelle, client=blob.client())
    anfrage = blob.puts[0]
    assert anfrage.url.host == "vercel.com"
    assert anfrage.headers["x-vercel-blob-access"] == "private"
    assert anfrage.headers["x-vercel-blob-store-id"] == "AbCdEf123"
    assert anfrage.headers["x-allow-overwrite"] == "1"
    assert anfrage.headers["authorization"] == f"Bearer {TOKEN}"
    assert b"streng geheim" not in (blob.data or b"")
    ziel = tmp_path / "b"
    assert vercel_blob.restore(ziel, client=blob.client()) == 1
    assert (ziel / ".aquaticy" / "notiz.txt").read_text(encoding="utf-8") == "streng geheim"


def test_restore_without_backup_and_with_wrong_secret(blob_env, monkeypatch, tmp_path):
    from aquaticy import vercel_blob

    blob = FakeBlob()
    assert vercel_blob.restore(tmp_path, client=blob.client()) == 0
    (tmp_path / "x.txt").write_text("1", encoding="utf-8")
    vercel_blob.save(tmp_path, client=blob.client())
    monkeypatch.setenv("AQUATICY_VERCEL_SECRET", "y" * 40)
    with pytest.raises(vercel_blob.BlobError):
        vercel_blob.restore(tmp_path / "neu", client=blob.client())


@pytest.fixture
def vercel_app(monkeypatch, tmp_path):
    """Der Vercel-Einstieg mit /tmp unter tmp_path -- und die globalen Werte danach zurueck."""
    from aquaticy import config, vercel, web

    home = tmp_path / "home"
    monkeypatch.setattr(vercel, "HOME", home)
    for name in ("HOME", "AQUATICY_DATA_DIR", "AQUATICY_VERCEL", "AQUATICY_ENABLE_PLAYWRIGHT",
                 "AQUATICY_ACCOUNTS", "AQUATICY_MODEL", "AQUATICY_ULTRA_CODE",
                 "AQUATICY_PRO_CODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AQUATICY_BLOB_TOKEN", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(vercel, "_STATE", {"error": "", "web": None, "handler": None,
                                           "stand": None})
    for name in ("AUTH", "AIGUARD", "TOKEN", "account_quota", "_profile_settings"):
        monkeypatch.setattr(web, name, getattr(web, name))
    config.reset_settings_cache()
    yield vercel
    config.reset_settings_cache()


def call(app, path: str, method: str = "GET", ip: str = "198.51.100.7",
         body: bytes = b"", headers: dict[str, str] | None = None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "",
               "HTTP_HOST": "aquaticy.vercel.app", "HTTP_X_REAL_IP": ip,
               "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}
    for name, wert in (headers or {}).items():
        environ["HTTP_" + name.upper().replace("-", "_")] = wert
    antwort: dict[str, object] = {}

    def start_response(status, kopf):
        antwort["status"] = status
        antwort["headers"] = dict(kopf)

    inhalt = b"".join(app(environ, start_response))
    return str(antwort["status"]), antwort["headers"], inhalt


def test_starts_without_any_code_as_account_system(vercel_app):
    from aquaticy import web

    status, kopf, inhalt = call(vercel_app.app, "/")
    assert status.startswith("200")
    assert "text/html" in kopf["Content-Type"]
    assert b"Aquaticy" in inhalt
    assert "Connection" not in kopf
    assert web.AUTH is not None and not web.AUTH.single
    status, _, inhalt = call(vercel_app.app, "/api/auth/status")
    assert status.startswith("200")
    daten = json.loads(inhalt)
    assert daten["authenticated"] is False and daten["single"] is False


def test_first_account_ultra_then_pro_without_code(vercel_app):
    from aquaticy import web

    _, _, inhalt = call(vercel_app.app, "/api/auth/status")
    assert json.loads(inhalt)["auto_plan"] is True
    eins = web.AUTH.register("ana@example.org", "ein-langes-Passwort-42", "normal",
                             terms_accepted=True, terms_version="1", ip="198.51.100.7")
    zwei = web.AUTH.register("bo@example.org", "ein-langes-Passwort-42", "ultra", "egal",
                             terms_accepted=True, terms_version="1", ip="198.51.100.8")
    assert (eins.plan, zwei.plan) == ("ultra", "pro")
    # Pro bleibt sperrbar und darf nichts abschalten, was an Ultra haengt (Sicherheit).
    assert eins.ultra and not zwei.ultra
    assert web.AUTH.owner().id == eins.id


def test_pro_accounts_have_no_token_limit(vercel_app, tmp_path):
    from aquaticy import web

    call(vercel_app.app, "/")
    assert web.account_quota(tmp_path, None) is None


def test_wrong_codes_at_vercel_do_not_stop_the_page(vercel_app, monkeypatch):
    from aquaticy import web

    monkeypatch.setenv("AQUATICY_ULTRA_CODE", "Ab3-defghijklm")
    monkeypatch.setenv("AQUATICY_PRO_CODE", "zu-lang-und-falsch")
    assert call(vercel_app.app, "/")[0].startswith("200")
    assert web.AUTH.ultra_code == "Ab3-defghijklm"
    assert len(web.AUTH.pro_code) == 9 and web.AUTH.pro_code != "ZU-LANG-UND-FALSCH"


def test_server_only_features_are_off(vercel_app, monkeypatch):
    for pfad in ("/api/vm", "/api/messenger/native", "/api/cluster", "/api/werkstatt"):
        status, _, inhalt = call(vercel_app.app, pfad)
        assert status.startswith("404"), pfad
        assert "Vercel" in json.loads(inhalt)["error"]


def test_oidc_header_reaches_the_blob_code_but_not_the_app(vercel_app, monkeypatch):
    from aquaticy import vercel_blob

    status, _, _ = call(vercel_app.app, "/", headers={"x-vercel-oidc-token": "jwt-1"})
    assert status.startswith("200")
    assert vercel_blob.OIDC_TOKEN == "jwt-1"
    roh = vercel_app._raw_request({"REQUEST_METHOD": "GET", "PATH_INFO": "/",
                                   "HTTP_X_VERCEL_OIDC_TOKEN": "jwt-1"}, b"")
    assert b"jwt-1" not in roh


def test_loopback_and_unknown_addresses_are_refused(vercel_app, monkeypatch):
    assert call(vercel_app.app, "/", ip="127.0.0.1")[0].startswith("400")
    assert call(vercel_app.app, "/", ip="kein-ip")[0].startswith("400")
    assert vercel_app.visitor_ip({"HTTP_X_REAL_IP": "2001:db8::1"}) == "2001:db8::1"


def test_preset_model_is_aquaticy_standard_without_choice(vercel_app, monkeypatch):
    """16.0.0: ohne eigene Wahl antwortet Aquaticy Standard -- ohne Schluessel."""
    assert vercel_app.preset_model() == "aquaticy/standard"
    monkeypatch.setenv("AQUATICY_MODEL", "mistral/mistral-small-latest")
    assert vercel_app.preset_model() == ""
    monkeypatch.delenv("AQUATICY_MODEL")
    datei = vercel_app._env_file()
    datei.parent.mkdir(parents=True)
    datei.write_text("AQUATICY_MODEL=mistral/mistral-small-latest\n", encoding="utf-8")
    assert vercel_app.preset_model() == ""


def test_readme_explains_vercel_mode():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for wort in ("Kontensystem", "AQUATICY_VERCEL_SECRET", "BLOB_READ_WRITE_TOKEN",
                 "Gemma 4"):
        assert wort in text


def test_sqlite_in_wal_mode_is_packed_consistently(tmp_path):
    import sqlite3

    from aquaticy import vercel_blob

    quelle = tmp_path / "home"
    quelle.mkdir()
    db = sqlite3.connect(quelle / "aquaticy.sqlite3")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE t (x TEXT)")
    db.execute("INSERT INTO t VALUES ('noch im WAL')")
    db.commit()
    archiv = vercel_blob.pack(quelle)
    db.close()
    namen = names(archiv)
    assert namen == ["aquaticy.sqlite3"]
    ziel = tmp_path / "ziel"
    vercel_blob.unpack(archiv, ziel)
    neu = sqlite3.connect(ziel / "aquaticy.sqlite3")
    assert neu.execute("SELECT x FROM t").fetchall() == [("noch im WAL",)]
    neu.close()


def test_backup_only_after_changes(vercel_app, monkeypatch):
    from aquaticy import vercel_blob

    gesichert: list[Path] = []
    monkeypatch.setattr(vercel_blob, "save", lambda home: gesichert.append(home) or True)
    vercel_app.HOME.mkdir(parents=True)
    (vercel_app.HOME / "a.txt").write_text("1", encoding="utf-8")
    vercel_app.save_if_changed()
    vercel_app.save_if_changed()
    assert gesichert == [vercel_app.HOME]


def test_shared_keys_are_taken_out_at_start(vercel_app, monkeypatch):
    import os

    monkeypatch.setenv("MISTRAL_API_KEY", "m" * 32)
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-geheim")
    assert call(vercel_app.app, "/")[0].startswith("200")
    assert "MISTRAL_API_KEY" not in os.environ and "NVIDIA_NIM_API_KEY" not in os.environ
    assert {"MISTRAL_API_KEY", "NVIDIA_NIM_API_KEY"} <= vercel_app.shared_key_names()


def test_each_account_sees_only_its_own_keys(vercel_app):
    from types import SimpleNamespace

    fremd = SimpleNamespace(api_keys={"MISTRAL_API_KEY": "server", "NVIDIA_NIM_API_KEY": "eigen"},
                            search_keys={"BRAVE_API_KEY": "server"},
                            own_key_names=frozenset({"NVIDIA_NIM_API_KEY"}))
    gefiltert = vercel_app._only_own_keys(lambda *a, **k: fremd)("profil", "pro")
    assert gefiltert.api_keys == {"NVIDIA_NIM_API_KEY": "eigen"}
    assert gefiltert.search_keys == {}


def test_secure_pro_only_opens_its_chat(vercel_app):
    def post(body: dict) -> str:
        daten = json.dumps(body).encode()
        return call(vercel_app.app, "/api/features", "POST", body=daten,
                    headers={"Content-Type": "application/json"})[0]

    assert post({"action": "configure", "enabled": True}).startswith("404")
    assert post({"action": "detect"}).startswith("404")
    assert call(vercel_app.app, "/api/features")[0].startswith("404")
    assert call(vercel_app.app, "/api/system")[0].startswith("404")
    # "open" geht durch bis zur Anmeldung (ohne Konto: 401), nicht an der Sperre vorbei
    assert not post({"action": "open"}).startswith("404")
