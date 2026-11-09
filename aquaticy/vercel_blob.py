"""Datenordner verschluesselt im privaten Vercel-Blob-Speicher sichern (Vercel-Modus).

Eine Vercel-Funktion hat keine bleibende Platte: Nur /tmp ist beschreibbar, und das ist beim
naechsten Kaltstart leer. Deshalb packt Aquaticy seinen Datenordner nach jeder Aenderung in
ein Archiv, verschluesselt es und legt es im PRIVATEN Blob-Speicher ab. Beim Kaltstart holt
es das Archiv zurueck.

Sicherheit:
* Verschluesselt mit einem Schluessel aus ``AQUATICY_VERCEL_SECRET`` (mindestens 32 Zeichen,
  nur als Umgebungsvariable bei Vercel). Ohne ihn wird nichts gespeichert -- im Blob-Speicher
  laege sonst auch der Schluessel fuer die Notizen.
* Nur der private Speicher (``x-vercel-blob-access: private``); Lesen geht nur mit Token.
* Entpacken nur von normalen Dateien und Ordnern innerhalb des Datenordners (keine Links,
  keine absoluten Pfade, kein "..").

Protokoll wie im offiziellen SDK ``@vercel/blob`` 2.8.2: Hochladen per PUT an
``https://vercel.com/api/blob/?pathname=...``, Lesen per GET an
``https://<store>.private.blob.vercel-storage.com/<pathname>``, jeweils mit dem Token.

Anmeldung in derselben Reihenfolge wie das SDK: ``AQUATICY_BLOB_TOKEN``, sonst OIDC (das Token
schickt Vercel bei jeder Anfrage im Kopf ``x-vercel-oidc-token``, dazu ``BLOB_STORE_ID`` vom
Verbinden des Speichers), sonst ``BLOB_READ_WRITE_TOKEN``.

Grenze: Laufen gleichzeitig mehrere Instanzen, gewinnt die zuletzt gespeicherte. Fuer ein
Einzelkonto reicht das; fuer viele gleichzeitige Nutzer braeuchte es eine Datenbank.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import tarfile
import threading
from pathlib import Path
from typing import Any

API_URL = "https://vercel.com/api/blob"
API_VERSION = "13"
PATHNAME = "aquaticy/daten.tar.gz.enc"
MAX_ARCHIVE = 200 * 1024 * 1024
MAX_FILE = 50 * 1024 * 1024
SKIP_DIRS = {"cache", "voice-models", "vm", "workshop", "__pycache__"}
_LOCK = threading.Lock()


class BlobError(RuntimeError):
    """Der Blob-Speicher antwortet nicht wie erwartet."""


#: Das OIDC-Token der laufenden Anfrage -- setzt vercel.py aus ``x-vercel-oidc-token``.
OIDC_TOKEN = ""


def store_id(wert: str) -> str:
    """Aus ``vercel_blob_rw_<store>_<geheim>`` die Kennung des Speichers."""
    teile = wert.split("_")
    return _checked_store(teile[3] if len(teile) > 4 else "")


def _checked_store(kennung: str) -> str:
    kennung = kennung.strip().removeprefix("store_")
    if not kennung.isalnum() or len(kennung) > 64:
        raise BlobError("Die Kennung des Blob-Speichers hat ein unbekanntes Format.")
    return kennung


def credentials() -> tuple[str, str] | None:
    """(Bearer-Token, Speicher-Kennung) wie im SDK -- oder None (nichts eingerichtet)."""
    eigenes = os.environ.get("AQUATICY_BLOB_TOKEN", "").strip()
    if eigenes:
        return eigenes, store_id(eigenes)
    oidc = (OIDC_TOKEN or os.environ.get("VERCEL_OIDC_TOKEN", "")).strip()
    speicher = os.environ.get("BLOB_STORE_ID", "").strip()
    if oidc and speicher:
        return oidc, _checked_store(speicher)
    lese_schreib = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    if lese_schreib:
        return lese_schreib, store_id(lese_schreib)
    return None


def secret_key() -> bytes | None:
    """Fernet-Schluessel aus AQUATICY_VERCEL_SECRET -- oder None (dann keine Sicherung)."""
    geheim = os.environ.get("AQUATICY_VERCEL_SECRET", "")
    if len(geheim) < 32:
        return None
    roh = hashlib.scrypt(geheim.encode("utf-8"), salt=b"aquaticy-vercel-blob-v1",
                         n=2**14, r=8, p=1, dklen=32)
    return base64.urlsafe_b64encode(roh)


def enabled() -> bool:
    return bool(secret_key() and credentials())


def _sqlite_copy(datei: Path, ziel: Path) -> bool:
    """Eine stimmige Kopie einer SQLite-Datenbank (WAL eingerechnet). False: keine Datenbank."""
    import sqlite3

    with datei.open("rb") as quelle:
        if quelle.read(16) != b"SQLite format 3\x00":
            return False
    alt = sqlite3.connect(f"file:{datei}?mode=ro", uri=True)
    neu = sqlite3.connect(ziel)
    try:
        alt.backup(neu)
    finally:
        neu.close()
        alt.close()
    return True


def pack(data_dir: Path) -> bytes:
    """Der Datenordner als tar.gz -- ohne Caches, uebergrosse Dateien und Links.

    SQLite-Datenbanken gehen als stimmige Kopie mit (Backup-API), ihre -wal/-shm-Dateien nicht.
    """
    import tempfile

    puffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp, \
            tarfile.open(fileobj=puffer, mode="w:gz", compresslevel=6) as archiv:
        for datei in sorted(Path(data_dir).rglob("*")):
            relativ = datei.relative_to(data_dir)
            if (datei.is_symlink() or not datei.is_file()
                    or any(teil in SKIP_DIRS for teil in relativ.parts)
                    or datei.suffix in (".lock", ".tmp")
                    or datei.name.endswith(("-wal", "-shm", "-journal"))
                    or datei.stat().st_size > MAX_FILE):
                continue
            kopie = Path(tmp) / "db"
            kopie.unlink(missing_ok=True)
            quelle = kopie if _sqlite_copy(datei, kopie) else datei
            archiv.add(quelle, arcname=relativ.as_posix(), recursive=False)
            if puffer.tell() > MAX_ARCHIVE:
                raise BlobError("Die Daten sind zu groß für die Sicherung (200 MB).")
    return puffer.getvalue()


def unpack(daten: bytes, data_dir: Path) -> int:
    """Entpackt nur normale Dateien innerhalb von *data_dir*. Returns: Zahl der Dateien."""
    ziel = Path(data_dir).resolve()
    ziel.mkdir(parents=True, exist_ok=True)
    anzahl = 0
    with tarfile.open(fileobj=io.BytesIO(daten), mode="r:gz") as archiv:
        for eintrag in archiv.getmembers():
            pfad = (ziel / eintrag.name).resolve()
            if (not eintrag.isfile() or eintrag.name.startswith("/") or ".." in Path(
                    eintrag.name).parts or not pfad.is_relative_to(ziel)
                    or eintrag.size > MAX_FILE):
                continue
            quelle = archiv.extractfile(eintrag)
            if quelle is None:
                continue
            pfad.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(pfad, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as aus:
                aus.write(quelle.read(MAX_FILE + 1)[:MAX_FILE])
            anzahl += 1
    return anzahl


def _headers(wert: str, speicher: str) -> dict[str, str]:
    return {"authorization": f"Bearer {wert}", "x-api-version": API_VERSION,
            "x-vercel-blob-store-id": speicher}


def restore(data_dir: Path, client: Any = None) -> int:
    """Holt die letzte Sicherung zurueck. Returns: Zahl der Dateien (0: keine Sicherung)."""
    from cryptography.fernet import Fernet, InvalidToken

    schluessel, zugang = secret_key(), credentials()
    if not schluessel or not zugang:
        return 0
    import httpx

    wert, speicher = zugang
    eigener = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False)
    try:
        antwort = client.get(
            f"https://{speicher}.private.blob.vercel-storage.com/{PATHNAME}",
            params={"cache": "0"}, headers={"authorization": f"Bearer {wert}"})
    finally:
        if eigener:
            client.close()
    if antwort.status_code == 404:
        return 0
    if antwort.status_code != 200:
        raise BlobError(f"Die Sicherung ließ sich nicht laden (HTTP {antwort.status_code}).")
    try:
        roh = Fernet(schluessel).decrypt(antwort.content)
    except InvalidToken as exc:
        raise BlobError("Die Sicherung passt nicht zu AQUATICY_VERCEL_SECRET.") from exc
    return unpack(roh, data_dir)


def save(data_dir: Path, client: Any = None) -> bool:
    """Sichert den Datenordner verschluesselt. False: nicht eingerichtet."""
    from cryptography.fernet import Fernet

    schluessel, zugang = secret_key(), credentials()
    if not schluessel or not zugang:
        return False
    import httpx

    wert, speicher = zugang
    with _LOCK:
        daten = Fernet(schluessel).encrypt(pack(data_dir))
        eigener = client is None
        client = client or httpx.Client(timeout=60, follow_redirects=False)
        try:
            antwort = client.put(
                f"{API_URL}/", params={"pathname": PATHNAME}, content=daten,
                headers={**_headers(wert, speicher), "x-vercel-blob-access": "private",
                         "x-add-random-suffix": "0", "x-allow-overwrite": "1",
                         "x-content-type": "application/octet-stream"})
        finally:
            if eigener:
                client.close()
    if antwort.status_code not in (200, 201):
        raise BlobError(f"Die Sicherung ließ sich nicht speichern (HTTP {antwort.status_code}).")
    return True
