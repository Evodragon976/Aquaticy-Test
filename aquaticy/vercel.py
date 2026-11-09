"""Aquaticy auf Vercel: die ganze Oberflaeche als WSGI-Funktion (Vercel-Modus, Aquaticy-Test).

Vercel startet Python als kurzlebige Funktion: kein dauerhafter Prozess, nur /tmp ist
beschreibbar. Dieser Einstieg reicht jede Anfrage an denselben ``web.Handler`` weiter, den
``aquaticy web`` benutzt -- dieselbe Anmeldung, dieselben Regeln (netguard, injection,
aiguard, guardrails). Nichts davon wird hier abgeschwaecht.

Anders als am eigenen Rechner:

* **Anmeldung:** Einzelkonto. Den Einrichtungscode liest niemand im Terminal -- er kommt aus
  ``AQUATICY_ULTRA_CODE`` (Umgebungsvariable bei Vercel, 14 Zeichen). Ohne ihn startet nichts.
* **Daten:** liegen in /tmp und werden nach jeder Aenderung verschluesselt im privaten
  Blob-Speicher gesichert (``vercel_blob.py``). Ohne ``AQUATICY_VERCEL_SECRET`` und Blob-Token
  gibt es keine Sicherung: Beim naechsten Kaltstart ist dann alles weg.
* **Aus:** virtual machine, WhatsApp/Signal, Secure Pro, Coworker-Zeitplan, Werkstatt,
  Plugins, Heimnetz-Dienste, Server-Verbund, lokale Modelle und deren Upgrades. Das braucht
  einen Rechner, der dauerhaft laeuft.
* **Modelle:** Wie in der App unter Einstellungen frei waehlbar (Mistral, NVIDIA NIM). Ist
  noch keins gewaehlt und nur ein NVIDIA-Schluessel da, gilt Gemma 4 (``PRESET_MODEL``).
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
PRESET_MODEL = "nvidia_nim/google/gemma-4-31b-it"
MAX_BODY = 64 * 1024 * 1024
BLOCKED = ("/api/cluster", "/api/messenger/", "/api/addons/qr", "/api/werkstatt", "/api/vm",
           "/api/features", "/api/coworkers", "/api/upgrades", "/api/plugins", "/api/ha",
           "/api/storage", "/cluster/")
BLOCKED_TEXT = "Das gibt es auf Vercel nicht. Dafür brauchst du Aquaticy auf deinem Rechner."
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade",
              "proxy-connection", "expect"}

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
    os.environ.setdefault("AQUATICY_ACCOUNTS", "0")


def _env_file() -> Path:
    return HOME / ".config" / "aquaticy" / ".env"


def preset_model() -> str:
    """Das Modell fuer den ersten Start -- "" heisst: Aquaticy-Standard (Mistral)."""
    if os.environ.get("AQUATICY_MODEL", "").strip():
        return ""
    datei = _env_file()
    if datei.is_file() and any(zeile.strip().startswith("AQUATICY_MODEL=")
                               for zeile in datei.read_text(encoding="utf-8").splitlines()):
        return ""
    if os.environ.get("NVIDIA_NIM_API_KEY") and not os.environ.get("MISTRAL_API_KEY"):
        return PRESET_MODEL
    return ""


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
        from aquaticy.auth import valid_ultra_code

        code = os.environ.get("AQUATICY_ULTRA_CODE", "").strip()
        if not valid_ultra_code(code):
            _STATE["error"] = ("AQUATICY_ULTRA_CODE fehlt oder passt nicht (14 Zeichen, mit "
                               "Buchstabe, Ziffer und Sonderzeichen). Trag ihn bei Vercel unter "
                               "Settings → Environment Variables ein.")
            return str(_STATE["error"])
        try:
            vercel_blob.restore(HOME)
        except Exception as exc:
            # Nie mit leeren Daten weitermachen: die naechste Sicherung loeschte sonst alles.
            _STATE["error"] = f"Die Sicherung ließ sich nicht laden: {exc}"
            return str(_STATE["error"])
        modell = preset_model()
        if modell:
            from aquaticy.config import write_env_file

            write_env_file({"AQUATICY_MODEL": modell}, _env_file())
        from aquaticy import web
        from aquaticy.aiguard import guard_for
        from aquaticy.auth import AuthStore, pro_code_for
        from aquaticy.config import get_settings

        data_dir = get_settings().data_dir
        web.AUTH = AuthStore(data_dir, pro_code_for(data_dir), code, single=True)
        web.AIGUARD = guard_for(data_dir)
        web.TOKEN = ""
        _STATE["web"] = web
        _STATE["handler"] = _handler_class(web)
        _STATE["stand"] = _fingerprint()
        return ""


def _handler_class(web: Any) -> type:
    class VercelHandler(web.PublicHandler):
        """Wie der Eingang fuer den Tunnel -- nur ohne das, was Vercel nicht kann."""

        def _client_ip(self) -> str:
            return str(self.client_address[0])

        def _blocked(self) -> bool:
            if not self._route().startswith(BLOCKED):
                return False
            self.responded = False
            self._json({"ok": False, "error": BLOCKED_TEXT}, 404)
            return True

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
        if name.lower() in HOP_BY_HOP or name.lower() == "content-length":
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
