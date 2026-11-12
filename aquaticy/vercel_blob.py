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
from collections.abc import Callable
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


def belongs(datei: Path, relativ: Path) -> bool:
    """Gehoert diese Datei in die Sicherung? Keine Caches, Links, Sperren, WAL-Dateien."""
    try:
        return not (datei.is_symlink() or not datei.is_file()
                    or any(teil in SKIP_DIRS for teil in relativ.parts)
                    or datei.suffix in (".lock", ".tmp")
                    or datei.name.endswith(("-wal", "-shm", "-journal"))
                    or datei.stat().st_size > MAX_FILE)
    except OSError:
        return False


def pack(data_dir: Path, only: Callable[[Path], bool] | None = None) -> bytes:
    """Der Datenordner als tar.gz -- ohne Caches, uebergrosse Dateien und Links.

    SQLite-Datenbanken gehen als stimmige Kopie mit (Backup-API), ihre -wal/-shm-Dateien nicht.

    Args:
        only: nimmt nur Dateien, fuer deren Pfad (relativ zu *data_dir*) das gilt -- der
            Speicher-Verbund (aquaticy/vercel_verbund.py) packt so einzelne Teile.
    """
    import gzip
    import tempfile

    puffer = io.BytesIO()
    # Ohne Zeitstempel und Besitzer: Gleicher Inhalt ergibt dasselbe Archiv. So erkennt der
    # Speicher-Verbund an der Pruefsumme, dass sich nichts geaendert hat (16.1.3).
    with tempfile.TemporaryDirectory() as tmp, \
            gzip.GzipFile(fileobj=puffer, mode="wb", compresslevel=6, mtime=0) as gz, \
            tarfile.open(fileobj=gz, mode="w") as archiv:
        for datei in sorted(Path(data_dir).rglob("*")):
            relativ = datei.relative_to(data_dir)
            if not belongs(datei, relativ) or (only is not None and not only(relativ)):
                continue
            kopie = Path(tmp) / "db"
            kopie.unlink(missing_ok=True)
            quelle = kopie if _sqlite_copy(datei, kopie) else datei
            eintrag = archiv.gettarinfo(str(quelle), arcname=relativ.as_posix())
            eintrag.mtime, eintrag.uid, eintrag.gid = 0, 0, 0
            eintrag.uname = eintrag.gname = ""
            eintrag.mode = 0o600
            with quelle.open("rb") as inhalt:
                archiv.addfile(eintrag, inhalt)
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
            # Erst daneben schreiben, dann ersetzen: Wer die alte Datei gerade offen hat, liest
            # sie zu Ende. Alte WAL-Dateien gehoeren zur alten Datenbank und muessen weg.
            neu = pfad.with_name(pfad.name + ".tmp")
            fd = os.open(neu, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as aus:
                aus.write(quelle.read(MAX_FILE + 1)[:MAX_FILE])
            os.replace(neu, pfad)
            for anhang in ("-wal", "-shm", "-journal"):
                pfad.with_name(pfad.name + anhang).unlink(missing_ok=True)
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


TEIL_KOPF = b"AQV1 "


class BlobTeile:
    """Einzelne Teile des Datenordners im privaten Blob-Speicher (16.1.4).

    Der Speicher-Verbund (aquaticy/vercel_verbund.py) legt hier den Inhalt ab -- der
    Blob-Speicher ist der groesste und damit der Hauptspeicher. Jeder Teil ist eine Datei
    ``aquaticy/teile/<name>.enc``: eine Kopfzeile mit der Fassungsnummer, dann der schon
    verschluesselte Inhalt. Ein leerer Inhalt heisst: geloescht.
    """

    def __init__(self, client: Any = None) -> None:
        self._client = client

    @staticmethod
    def pfad(teil: str) -> str:
        return "aquaticy/teile/" + teil.replace("/", "-") + ".enc"

    def _zugang(self) -> tuple[str, str]:
        zugang = credentials()
        if not zugang:
            raise BlobError("Der Blob-Speicher ist nicht verbunden.")
        return zugang

    def _mit_client(self, tun: Callable[[Any], Any], sekunden: int) -> Any:
        import httpx

        if self._client is not None:
            return tun(self._client)
        with httpx.Client(timeout=sekunden, follow_redirects=False) as client:
            return tun(client)

    def holen(self, teil: str) -> tuple[int, bytes] | None:
        """Fassung und Inhalt eines Teils -- None, wenn es ihn hier nicht gibt."""
        wert, speicher = self._zugang()
        antwort = self._mit_client(lambda client: client.get(
            f"https://{speicher}.private.blob.vercel-storage.com/{self.pfad(teil)}",
            params={"cache": "0"}, headers={"authorization": f"Bearer {wert}"}), 30)
        if antwort.status_code == 404:
            return None
        if antwort.status_code != 200:
            raise BlobError(f"Der Blob-Speicher antwortet mit HTTP {antwort.status_code}.")
        kopf, trenner, inhalt = bytes(antwort.content).partition(b"\n")
        if not trenner or not kopf.startswith(TEIL_KOPF) or not kopf[len(TEIL_KOPF):].isdigit():
            raise BlobError("Ein Teil im Blob-Speicher ist beschädigt.")
        return int(kopf[len(TEIL_KOPF):]), inhalt

    def schreiben(self, teil: str, fassung: int, daten: bytes) -> None:
        wert, speicher = self._zugang()
        inhalt = TEIL_KOPF + str(int(fassung)).encode("ascii") + b"\n" + bytes(daten)
        antwort = self._mit_client(lambda client: client.put(
            f"{API_URL}/", params={"pathname": self.pfad(teil)}, content=inhalt,
            headers={**_headers(wert, speicher), "x-vercel-blob-access": "private",
                     "x-add-random-suffix": "0", "x-allow-overwrite": "1",
                     "x-content-type": "application/octet-stream"}), 60)
        if antwort.status_code not in (200, 201):
            raise BlobError(f"Der Blob-Speicher nimmt nicht an (HTTP {antwort.status_code}).")
