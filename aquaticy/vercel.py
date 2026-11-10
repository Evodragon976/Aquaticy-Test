"""Aquaticy auf Vercel: die ganze Oberflaeche als WSGI-Funktion (Vercel-Modus, Aquaticy-Test).

Vercel startet Python als kurzlebige Funktion: kein dauerhafter Prozess, nur /tmp ist
beschreibbar. Dieser Einstieg reicht jede Anfrage an denselben ``web.Handler`` weiter, den
``aquaticy web`` benutzt -- dieselbe Anmeldung, dieselben Regeln (netguard, injection,
aiguard, guardrails). Nichts davon wird hier abgeschwaecht.

Anders als am eigenen Rechner:

* **Anmeldung:** Kontensystem ohne Code. Das erste Konto bekommt Ultra (der Besitzer), jedes
  weitere Pro -- ohne Token-Grenze. Was in der App an Ultra haengt, weil es Sicherheit
  betrifft (Rechts-Leitplanken abschalten, eigene Adressen fuer Modell oder Suche, nie vom
  Missbrauchsschutz gesperrt werden), bleibt beim Besitzer.
* **Daten:** liegen in /tmp und werden nach jeder Aenderung verschluesselt im privaten
  Blob-Speicher gesichert (``vercel_blob.py``). Ohne ``AQUATICY_VERCEL_SECRET`` und einen
  verbundenen Speicher gibt es keine Sicherung: Beim naechsten Kaltstart ist dann alles weg.
* **Aus:** virtual machine, WhatsApp/Signal, Secure Pro, Coworker-Zeitplan, Werkstatt,
  Plugins, Heimnetz-Dienste, Server-Verbund, lokale Modelle und deren Upgrades. Das braucht
  einen Rechner, der dauerhaft laeuft.
* **Modelle:** Voreingestellt ist Aquaticy Standard (aquaticy/standard.py): antwortet ohne
  Sprachmodell und ohne Schluessel. Mit eigenem Schluessel waehlt jedes Konto Mistral oder
  NVIDIA NIM (zum Beispiel Gemma 4) in der Modellauswahl.
* **Schluessel nur im eigenen Konto (16.0.0):** Jedes Konto traegt seine API-Schluessel selbst
  ein; sie liegen verschluesselt nur in diesem Konto. Schluessel aus der Umgebung von Vercel oder
  aus der gemeinsamen .env nimmt Aquaticy beim Start heraus -- sonst naehme LiteLLM sie fuer jedes
  Konto als Rueckfall.
* **Adresse des Besuchers:** aus ``x-real-ip``, das Vercel am Rand selbst setzt. Niemand gilt
  hier als Heimnetz oder als 127.0.0.1.
"""

from __future__ import annotations

import contextlib
import ipaddress
import os
import socket
import tempfile
import threading
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("AQUATICY_VERCEL_HOME") or tempfile.gettempdir()) / "aquaticy-home"
PRESET_MODEL = "aquaticy/standard"
MAX_BODY = 64 * 1024 * 1024
#: Diese Teile gibt es in Aquaticy-Test nicht mehr (16.0.1). Die Sperre bleibt als zweite
#: Wand -- falls ein alter Browser-Tab sie noch aufruft, kommt eine klare Meldung.
BLOCKED = ("/api/cluster", "/api/messenger/", "/api/addons/qr", "/api/werkstatt", "/api/vm",
           "/api/coworkers", "/api/upgrades", "/api/ha", "/api/storage", "/api/system",
           "/cluster/")
#: /api/features: nur "Secure-Pro-Chat oeffnen" -- Netz, Pruefung und Abwehr gibt es nicht.
FEATURES_ALLOWED = frozenset({"open"})
BLOCKED_TEXT = "Das gibt es auf Vercel nicht. Dafür brauchst du Aquaticy auf deinem Rechner."
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade",
              "proxy-connection", "expect"}
#: Nur fuer den Blob-Speicher -- geht nicht an web.Handler weiter.
PRIVATE_HEADERS = {"x-vercel-oidc-token"}

_STATE: dict[str, Any] = {"error": "", "web": None, "handler": None, "stand": None}
_START_LOCK = threading.Lock()
_SAVE_LOCK = threading.Lock()


def _prepare_env() -> None:
    """Pfade nach /tmp, bevor ein Modul von Aquaticy sie liest."""
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.environ["HOME"] = str(HOME)
    os.environ["AQUATICY_DATA_DIR"] = str(HOME / ".aquaticy")
    os.environ["AQUATICY_VERCEL"] = "1"
    os.environ.setdefault("AQUATICY_ENABLE_PLAYWRIGHT", "0")
    os.environ["AQUATICY_ACCOUNTS"] = "1"


def _env_file() -> Path:
    return HOME / ".config" / "aquaticy" / ".env"


def preset_model() -> str:
    """Das Modell fuer den ersten Start: Aquaticy Standard -- "" heisst, schon gewaehlt."""
    if os.environ.get("AQUATICY_MODEL", "").strip():
        return ""
    datei = _env_file()
    if datei.is_file() and any(zeile.strip().startswith("AQUATICY_MODEL=")
                               for zeile in datei.read_text(encoding="utf-8").splitlines()):
        return ""
    return PRESET_MODEL


def _fingerprint() -> tuple[tuple[str, int, int], ...]:
    """Was gerade in /tmp liegt -- ohne Aenderung keine neue Sicherung."""
    stand = []
    for datei in sorted(HOME.rglob("*")):
        with contextlib.suppress(OSError):
            if datei.is_file() and not datei.is_symlink():
                info = datei.stat()
                stand.append((str(datei), info.st_mtime_ns, info.st_size))
    return tuple(stand)


def start() -> str:
    """Einmal je Kaltstart: Sicherung holen, Konten laden. Returns: "" oder der Fehler."""
    with _START_LOCK:
        if _STATE["handler"] is not None or _STATE["error"]:
            return str(_STATE["error"])
        _prepare_env()
        from aquaticy import vercel_blob

        try:
            vercel_blob.restore(HOME)
        except Exception as exc:
            # Nie mit leeren Daten weitermachen: die naechste Sicherung loeschte sonst alles.
            _STATE["error"] = f"Die Sicherung ließ sich nicht laden: {exc}"
            return str(_STATE["error"])
        modell = preset_model()
        from aquaticy.config import write_env_file

        if modell:
            write_env_file({"AQUATICY_MODEL": modell}, _env_file())
        namen = shared_key_names()
        for name in namen:
            os.environ.pop(name, None)
        if _env_file().is_file():
            write_env_file({}, _env_file(), remove=set(namen))
        from aquaticy import web
        from aquaticy.aiguard import guard_for
        from aquaticy.auth import AuthStore, pro_code_for, ultra_code_for
        from aquaticy.config import get_settings

        data_dir = get_settings().data_dir
        web.AUTH = _auth_class(AuthStore)(
            data_dir, upgrade_code(pro_code_for, "AQUATICY_PRO_CODE", data_dir),
            upgrade_code(ultra_code_for, "AQUATICY_ULTRA_CODE", data_dir), single=False)
        # Pro ohne Token-Grenze: ohne Kontingent rechnet die App wie bei Ultra.
        web.account_quota = lambda profile, account=None: None
        web._profile_settings = _only_own_keys(web._profile_settings)
        web.AIGUARD = guard_for(data_dir)
        web.TOKEN = ""
        _STATE["web"] = web
        _STATE["handler"] = _handler_class(web)
        _STATE["stand"] = _fingerprint()
        return ""


def shared_key_names() -> set[str]:
    """Alle Namen, unter denen ein Schluessel fuer Modell oder Suche fuer alle gelten koennte."""
    from aquaticy.config import GENERIC_KEY_NAME, PROVIDER_KEYS, SEARCH_BACKEND_KEYS
    from aquaticy.keyvault import SLOTS

    namen = {*PROVIDER_KEYS.values(), *SEARCH_BACKEND_KEYS.values(), GENERIC_KEY_NAME}
    namen |= {slot.name for slot in SLOTS}
    return {name for name in namen if name}


def _only_own_keys(original: Callable[..., Any]) -> Callable[..., Any]:
    """Ein Konto sieht nur die Schluessel aus seinem eigenen Schluesselbund."""

    def einstellungen(*args: Any, **kwargs: Any) -> Any:
        settings = original(*args, **kwargs)
        eigene = set(getattr(settings, "own_key_names", ()) or ())
        settings.api_keys = {k: v for k, v in settings.api_keys.items() if k in eigene}
        settings.search_keys = {k: v for k, v in settings.search_keys.items() if k in eigene}
        return settings

    return einstellungen


_FIRST_ACCOUNT = threading.Lock()


def _auth_class(basis: type) -> type:
    class VercelAuthStore(basis):
        """Konten ohne Code: das erste Ultra, jedes weitere Pro."""

        auto_plan = True

        def register(self, email: str, password: str, plan: str, pro_code: str = "",
                     **kwargs: Any) -> Any:
            with _FIRST_ACCOUNT:
                erstes = not self.accounts()
                if erstes:
                    return super().register(email, password, "ultra", self.ultra_code,
                                            **kwargs)
            return super().register(email, password, "pro", self.pro_code, **kwargs)

    return VercelAuthStore


def upgrade_code(lesen: Callable[[Path], str], name: str, data_dir: Path) -> str:
    """Der interne Code fuer Pro oder Ultra: aus *name* -- passt der nicht, ein geheimer.

    Niemand muss ihn eingeben (register setzt ihn selbst). Ein falsch eingetragener Wert bei
    Vercel soll aber nicht die ganze Seite stoppen.
    """
    try:
        return lesen(data_dir)
    except ValueError:
        print(f"  [Vercel] {name} passt nicht -- ich nehme einen geheimen Code.")
        os.environ.pop(name, None)
        return lesen(data_dir)


def _handler_class(web: Any) -> type:
    class VercelHandler(web.PublicHandler):
        """Wie der Eingang fuer den Tunnel -- nur ohne das, was Vercel nicht kann."""

        def _client_ip(self) -> str:
            return str(self.client_address[0])

        def _blocked(self) -> bool:
            route = self._route()
            gesperrt = route.startswith(BLOCKED)
            if route == "/api/features":
                gesperrt = self.command != "POST" or self._feature_action() not in FEATURES_ALLOWED
            if not gesperrt:
                return False
            self.responded = False
            self._json({"ok": False, "error": BLOCKED_TEXT}, 404)
            return True

        def _feature_action(self) -> str:
            """Liest die Aktion aus dem Koerper -- und legt ihn fuer web.Handler zurueck."""
            import io
            import json

            try:
                laenge = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return ""
            roh = self.rfile.read(max(0, min(laenge, 65536)))
            setattr(self, "rfile", io.BytesIO(roh))  # noqa: B010 -- mypy kennt rfile hier nicht
            try:
                daten = json.loads(roh or b"{}")
            except ValueError:
                return ""
            return str(daten.get("action", "")) if isinstance(daten, dict) else ""

        def do_GET(self) -> None:
            if not self._blocked():
                super().do_GET()

        def do_POST(self) -> None:
            if not self._blocked():
                super().do_POST()

        def do_DELETE(self) -> None:
            if not self._blocked():
                super().do_DELETE()

    return VercelHandler


def visitor_ip(environ: dict[str, Any]) -> str:
    """Die Adresse des Besuchers: von Vercel gesetzt, nie 127.0.0.1. "" heisst: ablehnen."""
    roh = str(environ.get("HTTP_X_REAL_IP") or "").strip()
    if not roh:
        roh = str(environ.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    if not roh and not os.environ.get("VERCEL"):
        roh = str(environ.get("REMOTE_ADDR") or "")
    try:
        adresse = ipaddress.ip_address(roh.split("%", 1)[0])
    except ValueError:
        return ""
    if adresse.is_loopback or adresse.is_unspecified:
        return ""
    return str(adresse)


def _raw_request(environ: dict[str, Any], body: bytes) -> bytes:
    """Die Anfrage so, wie sie ueber eine Verbindung kaeme -- fuer web.Handler."""
    pfad = str(environ.get("PATH_INFO") or "/")
    abfrage = str(environ.get("QUERY_STRING") or "")
    ziel = pfad + (f"?{abfrage}" if abfrage else "")
    methode = str(environ.get("REQUEST_METHOD") or "GET").upper()
    zeilen = [f"{methode} {ziel} HTTP/1.1"]
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            name = key[5:].replace("_", "-").title()
        elif key == "CONTENT_TYPE" and value:
            name = "Content-Type"
        else:
            continue
        wert = str(value)
        if name.lower() in HOP_BY_HOP | PRIVATE_HEADERS or name.lower() == "content-length":
            continue
        if "\r" in wert or "\n" in wert:
            continue
        zeilen.append(f"{name}: {wert}")
    zeilen += [f"Content-Length: {len(body)}", "Connection: close"]
    return ("\r\n".join(zeilen) + "\r\n\r\n").encode("latin-1", "replace") + body


def _plain(start_response: Callable[..., Any], status: str, text: str) -> list[bytes]:
    daten = text.encode("utf-8")
    start_response(status, [("Content-Type", "text/plain; charset=utf-8"),
                            ("Content-Length", str(len(daten))),
                            ("Cache-Control", "no-store"),
                            ("X-Content-Type-Options", "nosniff")])
    return [daten]


def save_if_changed() -> None:
    """Nach einer Aenderung: neue Sicherung, aber nur wenn sich in /tmp etwas getan hat."""
    from aquaticy import vercel_blob

    with _SAVE_LOCK:
        stand = _fingerprint()
        if stand == _STATE["stand"]:
            return
        try:
            if vercel_blob.save(HOME):
                _STATE["stand"] = stand
        except Exception as exc:
            print(f"  [Vercel] Sicherung fehlgeschlagen: {type(exc).__name__}: {exc}")


def app(environ: dict[str, Any],
        start_response: Callable[[str, list[tuple[str, str]]], Any]) -> Iterable[bytes]:
    """WSGI-Einstieg fuer Vercel (pyproject: ``[tool.vercel] entrypoint``)."""
    from aquaticy import vercel_blob

    oidc = str(environ.get("HTTP_X_VERCEL_OIDC_TOKEN") or "").strip()
    if oidc:
        vercel_blob.OIDC_TOKEN = oidc
    fehler = start()
    if fehler:
        return _plain(start_response, "503 Service Unavailable", fehler)
    ip = visitor_ip(environ)
    if not ip:
        return _plain(start_response, "400 Bad Request", "Unbekannte Adresse.")
    try:
        laenge = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        laenge = -1
    if laenge < 0 or laenge > MAX_BODY:
        return _plain(start_response, "413 Content Too Large", "Die Anfrage ist zu groß.")
    body = environ["wsgi.input"].read(laenge) if laenge else b""
    methode = str(environ.get("REQUEST_METHOD") or "GET").upper()
    return _relay(_raw_request(environ, body), ip, methode, start_response)


def _relay(roh: bytes, ip: str, methode: str,
           start_response: Callable[..., Any]) -> Iterator[bytes]:
    """Laesst web.Handler die Anfrage ueber ein Socket-Paar beantworten."""
    handler = _STATE["handler"]
    innen, aussen = socket.socketpair()

    def bedienen() -> None:
        try:
            handler(innen, (ip, 0), _FakeServer())
        except Exception as exc:  # pragma: no cover - Fehler landen im Log
            print(f"  [Vercel] Anfrage: {type(exc).__name__}")
        finally:
            with contextlib.suppress(OSError):
                innen.shutdown(socket.SHUT_RDWR)
            innen.close()

    def schreiben() -> None:
        with contextlib.suppress(OSError):
            aussen.sendall(roh)

    faden = threading.Thread(target=bedienen, daemon=True)
    faden.start()
    threading.Thread(target=schreiben, daemon=True).start()
    datei = aussen.makefile("rb")
    status_zeile = datei.readline(65537).decode("latin-1").strip()
    teile = status_zeile.split(" ", 2)
    if len(teile) < 2 or not teile[1].isdigit():
        aussen.close()
        yield from _plain(start_response, "502 Bad Gateway", "Keine Antwort von Aquaticy.")
        return
    status = f"{teile[1]} {teile[2] if len(teile) > 2 else ''}".strip()
    kopf: list[tuple[str, str]] = []
    while True:
        zeile = datei.readline(65537).decode("latin-1")
        if zeile in ("\r\n", "\n", ""):
            break
        name, _, wert = zeile.partition(":")
        if name.strip().lower() not in HOP_BY_HOP:
            kopf.append((name.strip(), wert.strip()))
    start_response(status, kopf)
    try:
        while True:
            stueck = datei.read1(65536) if hasattr(datei, "read1") else datei.read(65536)
            if not stueck:
                break
            yield stueck
    finally:
        datei.close()
        aussen.close()
        faden.join(timeout=5)
        if methode in ("POST", "DELETE") and int(teile[1]) < 500:
            save_if_changed()


class _FakeServer:
    """web.Handler fragt den Server nichts -- BaseRequestHandler will trotzdem einen."""

    server_address = ("vercel", 443)
