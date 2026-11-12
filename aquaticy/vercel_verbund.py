"""Speicher-Verbund: mehrere Postgres-Datenbanken teilen sich die Arbeit (16.1.3, Vercel-Modus).

Bis 16.0.3 lag der ganze Datenordner als EIN Archiv im Blob-Speicher: Jede Aenderung lud alles
neu hoch, und liefen zwei Instanzen, gewann die zuletzt gespeicherte. Der Verbund teilt den
Ordner in Teile und verteilt sie auf die verbundenen Datenbanken (Neon, Supabase -- alles
Postgres):

* **Konten** (Datenbank 1): der Teil ``kern`` -- Konten, Anmeldungen, Schluessel, Einstellungen.
* **Profile** (Datenbank 2 und alle ab der 4.): je Konto ein Teil ``konto/<kennung>`` -- Chats,
  Gedaechtnis, Dateien. Welche Datenbank ein Konto bekommt, entscheidet seine Kennung. Jeder
  Teil liegt zusaetzlich als Spiegel auf einer zweiten Datenbank.
* **Cache** (Datenbank 3): kurzlebige Abrufe mit Ablaufzeit -- Bilder, Wetter, Wikipedia.

Was das bringt:

* Gespeichert wird nur der Teil, der sich geaendert hat -- nicht mehr alles.
* Ein Profil wird erst geladen, wenn sein Konto eine Anfrage stellt. Jede Instanz haelt nur,
  was sie braucht.
* Vor jeder Anfrage fragt die Instanz die Fassungsnummern ab und holt, was eine andere
  Instanz geaendert hat.
* Faellt eine Datenbank aus, liest der Verbund vom Spiegel.

Sicherheit: Jeder Teil und jeder Cache-Eintrag ist mit dem Schluessel aus
``AQUATICY_VERCEL_SECRET`` verschluesselt (wie die Sicherung im Blob-Speicher). Die Tabellen
liegen im eigenen Schema ``aquaticy`` -- die Daten-API von Supabase zeigt nur ``public``.
Zugangsdaten stehen nur in den Umgebungsvariablen und nie in einer Meldung.

Grenze: Der Teil ``kern`` ist weiter eine Einheit. Schreiben zwei Instanzen ihn in derselben
Sekunde, gewinnt die spaetere. Dafuer muessten die Konten selbst in Postgres liegen.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA = "aquaticy"
KERN = "kern"
KONTO = "konto/"
DATEN = ".aquaticy"
MAX_TEIL = 64 * 1024 * 1024
MAX_CACHE = 2 * 1024 * 1024
#: So oft (Sekunden) fragt eine Instanz hoechstens nach den Fassungen der anderen.
PRUEF_ABSTAND = 3.0
#: Nach einem Fehler laesst der Cache die Datenbank so lange in Ruhe.
CACHE_PAUSE = 60.0
#: So lange wartet der Verbund hoechstens auf eine Verbindung -- und so lange fragt er eine
#: Datenbank nach einem Ausfall nicht wieder.
VERBINDEN_SEKUNDEN = 6
AUSFALL_PAUSE = 30.0
URL_NAME = re.compile(r"^((?:[A-Z][A-Z0-9]*_)?)(POSTGRES_URL|DATABASE_URL)$")
#: Nur diese Angaben einer Adresse gehen an den Treiber. Supabase haengt eigene an
#: (``supa=base-pooler.x``), an denen libpq sonst scheitert.
URL_PARAMETER = frozenset({"sslmode", "channel_binding", "connect_timeout"})
KENNUNG = re.compile(r"[0-9a-f]{32}")

TABELLEN = (
    f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}",
    f"CREATE TABLE IF NOT EXISTS {SCHEMA}.teile (name TEXT PRIMARY KEY, "
    "version BIGINT NOT NULL, daten BYTEA NOT NULL, "
    "geaendert TIMESTAMPTZ NOT NULL DEFAULT now())",
    f"CREATE TABLE IF NOT EXISTS {SCHEMA}.cache (schluessel TEXT PRIMARY KEY, "
    "art TEXT NOT NULL DEFAULT '', daten BYTEA NOT NULL, ablauf TIMESTAMPTZ NOT NULL)",
    f"CREATE INDEX IF NOT EXISTS cache_ablauf ON {SCHEMA}.cache (ablauf)",
)


class VerbundFehler(RuntimeError):
    """Eine Datenbank des Verbunds antwortet nicht oder lehnt ab."""


def melde(text: str) -> None:
    print(f"  [Verbund] {text}", flush=True)


def saubere_adresse(adresse: str) -> str:
    """Die Adresse fuer den Treiber: nur postgres(ql)://, nur bekannte Angaben, mit TLS.

    Returns:
        Die bereinigte Adresse, oder "" wenn sie keine Postgres-Adresse ist.
    """
    teile = urlsplit(str(adresse or "").strip())
    if teile.scheme not in ("postgres", "postgresql") or not teile.hostname:
        return ""
    angaben = [(k, v) for k, v in parse_qsl(teile.query) if k in URL_PARAMETER]
    lokal = teile.hostname in ("127.0.0.1", "localhost", "::1")
    if not lokal and not any(k == "sslmode" for k, _ in angaben):
        angaben.append(("sslmode", "require"))
    return urlunsplit(("postgresql", teile.netloc, teile.path, urlencode(angaben), ""))


def adressen(umgebung: Mapping[str, str] | None = None) -> list[tuple[str, str]]:
    """Die verbundenen Datenbanken in fester Reihenfolge: (Name, Adresse).

    Vercel legt je Datenbank ``<PRAEFIX>POSTGRES_URL`` an (Neon zusaetzlich
    ``<PRAEFIX>DATABASE_URL``). Ohne Praefix kommt zuerst, dann STORAGE_, STORAGE2_, ...
    """
    umgebung = os.environ if umgebung is None else umgebung
    gefunden: dict[str, str] = {}
    for name in sorted(umgebung):
        treffer = URL_NAME.match(name)
        if not treffer:
            continue
        adresse = saubere_adresse(umgebung[name])
        vorsatz = treffer.group(1)
        # POSTGRES_URL (ueber den Verbindungs-Pool) geht vor DATABASE_URL.
        if adresse and (vorsatz not in gefunden or treffer.group(2) == "POSTGRES_URL"):
            gefunden[vorsatz] = adresse

    def ordnung(vorsatz: str) -> tuple[str, int]:
        teil = re.match(r"^([A-Z_]*?)(\d*)_?$", vorsatz)
        return (teil.group(1), int(teil.group(2) or 0)) if teil else (vorsatz, 0)

    return [(vorsatz.rstrip("_") or "HAUPT", gefunden[vorsatz])
            for vorsatz in sorted(gefunden, key=ordnung)]


class Datenbank:
    """Eine Postgres-Datenbank des Verbunds -- eine Verbindung, bei Bedarf neu aufgebaut."""

    def __init__(self, name: str, adresse: str) -> None:
        self.name = name
        self._adresse = adresse
        self._verbindung: Any = None
        self._bereit = False
        self._pause_bis = 0.0
        self._sperre = threading.RLock()

    def __repr__(self) -> str:
        return f"Datenbank({self.name})"

    def _verbinden(self) -> Any:
        import psycopg

        # prepare_threshold=None: keine vorbereiteten Anweisungen -- die Pools von Neon und
        # Supabase reichen Verbindungen je Transaktion weiter.
        return psycopg.connect(self._adresse, autocommit=True, prepare_threshold=None,
                               connect_timeout=VERBINDEN_SEKUNDEN)

    def ausfuehren(self, sql: str, werte: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        """Fuehrt eine Anweisung aus. Returns: die Zeilen (leer ohne Ergebnis).

        Raises:
            VerbundFehler: nach dem zweiten Versuch -- ohne Adresse und Zugangsdaten.
        """
        import psycopg

        with self._sperre:
            if time.monotonic() < self._pause_bis:
                # Eben erst nicht erreichbar: nicht jede Anfrage wieder Sekunden warten lassen.
                raise VerbundFehler(f"{self.name} antwortet nicht (Pause nach einem Fehler).")
            for versuch in (1, 2):
                frisch = self._verbindung is None or self._verbindung.closed
                try:
                    if frisch:
                        self._verbindung = self._verbinden()
                    if not self._bereit:
                        for anweisung in TABELLEN:
                            # Zwei Instanzen legen gleichzeitig an: die zweite sieht "gibt es".
                            with contextlib.suppress(psycopg.errors.UniqueViolation,
                                                     psycopg.errors.DuplicateTable,
                                                     psycopg.errors.DuplicateSchema):
                                self._verbindung.execute(anweisung)
                        self._bereit = True
                    zeiger = self._verbindung.execute(sql, werte or None)
                    return list(zeiger.fetchall()) if zeiger.description else []
                except (psycopg.OperationalError, psycopg.InterfaceError) as fehler:
                    self.schliessen()
                    # Eine alte Verbindung kann eingeschlafen sein: einmal neu verbinden. Scheitert
                    # schon das Verbinden, hilft ein zweiter Versuch jetzt nicht.
                    if frisch or versuch == 2:
                        self._pause_bis = time.monotonic() + AUSFALL_PAUSE
                        raise VerbundFehler(
                            f"{self.name} antwortet nicht ({type(fehler).__name__}).") from None
                except psycopg.Error as fehler:
                    self.schliessen()
                    raise VerbundFehler(
                        f"{self.name} lehnt ab ({type(fehler).__name__}, "
                        f"{getattr(fehler, 'sqlstate', '') or 'ohne Code'}).") from None
        return []

    def schliessen(self) -> None:
        with self._sperre:
            verbindung, self._verbindung = self._verbindung, None
            if verbindung is not None:
                with contextlib.suppress(Exception):
                    verbindung.close()


def teil_von(relativ: Path) -> str:
    """Zu welchem Teil eine Datei gehoert: ``konto/<kennung>`` oder ``kern``."""
    stuecke = relativ.parts
    if (len(stuecke) >= 4 and stuecke[0] == DATEN and stuecke[1] == "users"
            and KENNUNG.fullmatch(stuecke[2])):
        return KONTO + stuecke[2]
    return KERN


class Verbund:
    """Teilt den Ordner *home* auf die Datenbanken auf und haelt ihn aktuell."""

    def __init__(self, datenbanken: list[Datenbank], schluessel: bytes, home: Path) -> None:
        if not datenbanken:
            raise ValueError("Der Verbund braucht mindestens eine Datenbank.")
        self.home = Path(home)
        self.datenbanken = list(datenbanken)
        self._schluessel = schluessel
        self.konten = datenbanken[0]
        self.cache = datenbanken[2] if len(datenbanken) >= 3 else datenbanken[-1]
        self.profile = ([db for i, db in enumerate(datenbanken) if i not in (0, 2)]
                        or [datenbanken[0]])
        #: Teil -> (Fassung, Fingerabdruck, Pruefsumme) beim letzten Gleichstand mit der
        #: Datenbank. Der Fingerabdruck ist billig (Zeit und Groesse); die Pruefsumme des
        #: Inhalts entscheidet, ob wirklich etwas hochgeladen werden muss.
        self.stand: dict[str, tuple[int, tuple[Any, ...], str]] = {}
        #: Teile, die diese Instanz kennt (geladen oder sicher neu).
        self.bekannt: set[str] = set()
        #: Teile, deren letzte Speicherung scheiterte -- sie gehen vor fremden Fassungen.
        self.offen: set[str] = set()
        self._fundort: dict[str, Datenbank] = {}
        self._aufgeraeumt: set[str] = set()
        self._sperre = threading.RLock()
        self._geprueft = 0.0
        self._cache_pause = 0.0
        self.letzter_fehler = ""

    # -- Wer haelt was ----------------------------------------------------------------------

    def orte(self, teil: str) -> list[Datenbank]:
        """Wo ein Teil liegt: zuerst die Hauptdatenbank, dann der Spiegel."""
        if teil == KERN:
            spiegel = self.profile[-1]
            return [self.konten] + ([spiegel] if spiegel is not self.konten else [])
        nummer = int(hashlib.sha256(teil.encode("utf-8")).hexdigest()[:8], 16)
        n = len(self.profile)
        haupt = self.profile[nummer % n]
        spiegel = self.profile[(nummer + 1) % n] if n > 1 else self.konten
        return [haupt] + ([spiegel] if spiegel is not haupt else [])

    def _fernet(self) -> Any:
        from cryptography.fernet import Fernet

        return Fernet(self._schluessel)

    # -- Dateien ----------------------------------------------------------------------------

    def fingerabdruecke(self) -> dict[str, tuple[Any, ...]]:
        """Je Teil: was gerade auf der Platte liegt (Pfad, Zeit, Groesse) -- auch WAL-Dateien,

        denn SQLite schreibt zuerst dorthin.
        """
        gruppen: dict[str, list[tuple[str, int, int]]] = {}
        if not self.home.is_dir():
            return {}
        for datei in sorted(self.home.rglob("*")):
            with contextlib.suppress(OSError):
                if datei.is_file() and not datei.is_symlink():
                    relativ = datei.relative_to(self.home)
                    info = datei.stat()
                    # -shm aendert sich schon beim Lesen, eine leere -wal traegt nichts.
                    if datei.name.endswith("-shm") or (
                            datei.name.endswith("-wal") and info.st_size == 0):
                        continue
                    gruppen.setdefault(teil_von(relativ), []).append(
                        (relativ.as_posix(), info.st_mtime_ns, info.st_size))
        return {teil: tuple(eintraege) for teil, eintraege in gruppen.items()}

    def _ordner(self, teil: str) -> Path:
        return self.home / DATEN / "users" / teil[len(KONTO):]

    def _packen(self, teil: str) -> tuple[bytes, str]:
        """Das Archiv eines Teils und seine Pruefsumme (noch unverschluesselt)."""
        from aquaticy import vercel_blob

        roh = vercel_blob.pack(self.home, only=lambda relativ: teil_von(relativ) == teil)
        if len(roh) > MAX_TEIL:
            raise VerbundFehler(f"Der Teil {teil.split('/')[0]} ist zu groß für den Verbund.")
        return roh, hashlib.sha256(roh).hexdigest()

    def _entpacken(self, teil: str, daten: bytes) -> str:
        """Entpackt einen Teil. Returns: die Pruefsumme seines Archivs."""
        from cryptography.fernet import InvalidToken

        from aquaticy import vercel_blob

        try:
            roh = self._fernet().decrypt(bytes(daten))
        except InvalidToken as fehler:
            raise VerbundFehler(
                "Ein Teil passt nicht zu AQUATICY_VERCEL_SECRET.") from fehler
        if teil != KERN:
            # Ein Profil ist ein genaues Abbild: was es dort nicht mehr gibt, soll hier weg.
            shutil.rmtree(self._ordner(teil), ignore_errors=True)
        vercel_blob.unpack(roh, self.home)
        return hashlib.sha256(roh).hexdigest()

    def _gleichstand(self, teil: str, fassung: int, pruefsumme: str) -> None:
        self.stand[teil] = (fassung, self.fingerabdruecke().get(teil, ()), pruefsumme)

    # -- Lesen und Schreiben in den Datenbanken ---------------------------------------------

    def _holen(self, teil: str) -> tuple[int, bytes] | None:
        """Die Fassung und der Inhalt eines Teils -- vom Hauptort, sonst vom Spiegel.

        Raises:
            VerbundFehler: wenn keine Datenbank antwortet. "Gibt es nicht" ist None -- und
                gilt nur, wenn mindestens eine Datenbank das auch gesagt hat.
        """
        orte = self.orte(teil) + self._andere(teil)
        geantwortet = False
        fehler: VerbundFehler | None = None
        for db in orte:
            try:
                zeilen = db.ausfuehren(
                    f"SELECT version, daten FROM {SCHEMA}.teile WHERE name = %s", (teil,))
            except VerbundFehler as exc:
                fehler = exc
                melde(f"{exc} Ich versuche es beim Spiegel.")
                continue
            geantwortet = True
            if zeilen:
                if db not in self.orte(teil):
                    self._fundort[teil] = db
                return int(zeilen[0][0]), bytes(zeilen[0][1])
        if not geantwortet and fehler is not None:
            raise fehler
        return None

    def _schreiben(self, teil: str, daten: bytes) -> int:
        """Legt die neue Fassung ab. Returns: ihre Nummer."""
        orte = self.orte(teil)
        zeilen = orte[0].ausfuehren(
            f"INSERT INTO {SCHEMA}.teile (name, version, daten) VALUES (%s, 1, %s) "
            f"ON CONFLICT (name) DO UPDATE SET version = {SCHEMA}.teile.version + 1, "
            "daten = EXCLUDED.daten, geaendert = now() RETURNING version", (teil, daten))
        fassung = int(zeilen[0][0])
        for spiegel in orte[1:]:
            try:
                spiegel.ausfuehren(
                    f"INSERT INTO {SCHEMA}.teile (name, version, daten) VALUES (%s, %s, %s) "
                    "ON CONFLICT (name) DO UPDATE SET version = EXCLUDED.version, "
                    "daten = EXCLUDED.daten, geaendert = now()", (teil, fassung, daten))
            except VerbundFehler as exc:
                melde(f"Spiegel nicht geschrieben: {exc}")
        self._fundort.pop(teil, None)
        if teil not in self._aufgeraeumt:
            # Einmal je Instanz: Reste an frueheren Orten wegnehmen (nach einer neuen Datenbank
            # liegt ein Konto woanders).
            self._aufgeraeumt.add(teil)
            for alt in self._andere(teil):
                with contextlib.suppress(VerbundFehler):
                    alt.ausfuehren(f"DELETE FROM {SCHEMA}.teile WHERE name = %s", (teil,))
        return fassung

    def _andere(self, teil: str) -> list[Datenbank]:
        """Wo ein Profil frueher gelegen haben kann -- alle ausser seinen heutigen Orten."""
        if teil == KERN:
            return []
        orte = self.orte(teil)
        return [db for db in [*self.profile, self.konten] if db not in orte]

    def _loeschen(self, teil: str) -> None:
        self._fundort.pop(teil, None)
        for db in self.orte(teil) + self._andere(teil):
            db.ausfuehren(f"DELETE FROM {SCHEMA}.teile WHERE name = %s", (teil,))

    # -- Ablauf -----------------------------------------------------------------------------

    def start_laden(self) -> bool:
        """Beim Kaltstart: holt den Teil ``kern``. Returns: False, wenn der Verbund leer ist."""
        with self._sperre:
            zeile = self._holen(KERN)
            if zeile is None:
                return False
            self._gleichstand(KERN, zeile[0], self._entpacken(KERN, zeile[1]))
            self.bekannt.add(KERN)
            return True

    def alles_bekannt(self) -> None:
        """Nach der Uebernahme aus dem Blob-Speicher: alles liegt hier und muss noch hoch."""
        with self._sperre:
            self.bekannt.add(KERN)
            self.bekannt.update(teil for teil in self.fingerabdruecke())

    def konto_laden(self, kennung: str) -> None:
        """Holt das Profil eines Kontos, sobald es gebraucht wird (einmal je Instanz)."""
        teil = KONTO + kennung
        if teil in self.bekannt or not KENNUNG.fullmatch(kennung):
            return
        with self._sperre:
            if teil in self.bekannt:
                return
            zeile = self._holen(teil)
            if zeile is not None:
                self._gleichstand(teil, zeile[0], self._entpacken(teil, zeile[1]))
            else:
                # Neu hier: Was schon auf der Platte liegt, muss noch hoch.
                self.stand[teil] = (0, (), "")
            self.bekannt.add(teil)

    def sichern(self) -> int:
        """Speichert jeden Teil, der sich geaendert hat. Returns: Zahl der gespeicherten."""
        gespeichert = 0
        with self._sperre:
            for teil in list(self.fingerabdruecke()):
                if teil not in self.bekannt and teil != KERN:
                    # Erst holen, was es schon gibt -- nie ein leeres Profil drueberschreiben.
                    self.konto_laden(teil[len(KONTO):])
            abdruecke = self.fingerabdruecke()
            for teil, abdruck in abdruecke.items():
                alt = self.stand.get(teil, (0, None, ""))
                if alt[1] == abdruck and teil not in self.offen:
                    continue
                try:
                    roh, pruefsumme = self._packen(teil)
                    if pruefsumme == alt[2] and alt[0] > 0 and teil not in self.offen:
                        # Nur Zeitstempel sind neu (etwa nach einem SQLite-Checkpoint).
                        self.stand[teil] = (alt[0], abdruck, pruefsumme)
                        continue
                    fassung = self._schreiben(teil, bytes(self._fernet().encrypt(roh)))
                except VerbundFehler as fehler:
                    self.offen.add(teil)
                    self.letzter_fehler = str(fehler)
                    melde(f"Nicht gespeichert: {fehler}")
                    continue
                # Das Packen selbst kann Zeitstempel bewegen: danach neu nachsehen.
                self._gleichstand(teil, fassung, pruefsumme)
                self.bekannt.add(teil)
                self.offen.discard(teil)
                gespeichert += 1
            for teil in [t for t in self.stand if t != KERN and t not in abdruecke]:
                if self.stand[teil][0] > 0:
                    try:
                        self._loeschen(teil)
                    except VerbundFehler as fehler:
                        self.letzter_fehler = str(fehler)
                        melde(f"Nicht gelöscht: {fehler}")
                        continue
                    gespeichert += 1
                self.stand[teil] = (0, (), "")
                self.offen.discard(teil)
        return gespeichert

    def auffrischen(self, jetzt: float | None = None) -> int:
        """Holt, was eine andere Instanz geaendert hat. Returns: Zahl der neu geladenen Teile.

        Eigene Aenderungen, die noch nicht gespeichert werden konnten (``offen``), gehen vor.
        Sonst gilt die neuere Fassung der Datenbank: Was hier seit dem letzten Speichern nur
        nebenbei anfiel (etwa "zuletzt gesehen"), wiegt weniger als ein fremder Schreibvorgang.
        """
        jetzt = time.monotonic() if jetzt is None else jetzt
        if jetzt - self._geprueft < PRUEF_ABSTAND:
            return 0
        geladen = 0
        with self._sperre:
            self._geprueft = jetzt
            gruppen: dict[int, tuple[Datenbank, list[str]]] = {}
            for teil in self.bekannt:
                db = self._fundort.get(teil) or self.orte(teil)[0]
                gruppen.setdefault(id(db), (db, []))[1].append(teil)
            for db, teile in gruppen.values():
                try:
                    zeilen = db.ausfuehren(
                        f"SELECT name, version FROM {SCHEMA}.teile WHERE name = ANY(%s)",
                        (teile,))
                except VerbundFehler:
                    continue
                dort = {str(name): int(fassung) for name, fassung in zeilen}
                for teil in teile:
                    hier = self.stand.get(teil, (0, (), ""))[0]
                    if teil in self.offen:
                        continue
                    if teil in dort and dort[teil] > hier:
                        try:
                            zeile = self._holen(teil)
                            if zeile is None:
                                continue
                            self._gleichstand(teil, zeile[0], self._entpacken(teil, zeile[1]))
                        except VerbundFehler as fehler:
                            self.letzter_fehler = str(fehler)
                            continue
                        geladen += 1
                    elif teil not in dort and hier > 0 and teil != KERN:
                        # Anderswo geloescht (Konto oder alle Daten): hier auch.
                        shutil.rmtree(self._ordner(teil), ignore_errors=True)
                        self.stand[teil] = (0, (), "")
                        geladen += 1
        return geladen

    # -- Cache ------------------------------------------------------------------------------

    @staticmethod
    def cache_name(art: str, was: str) -> str:
        return hashlib.sha256(f"{art}\x00{was}".encode()).hexdigest()

    def cache_holen(self, art: str, was: str) -> bytes | None:
        """Ein Eintrag aus dem Cache -- None bei Fehlen, Ablauf oder jedem Fehler."""
        if time.monotonic() < self._cache_pause:
            return None
        try:
            zeilen = self.cache.ausfuehren(
                f"SELECT daten FROM {SCHEMA}.cache WHERE schluessel = %s AND ablauf > now()",
                (self.cache_name(art, was),))
            return bytes(self._fernet().decrypt(bytes(zeilen[0][0]))) if zeilen else None
        except Exception:
            self._cache_pause = time.monotonic() + CACHE_PAUSE
            return None

    def cache_setzen(self, art: str, was: str, daten: bytes, sekunden: int) -> bool:
        """Legt einen Eintrag ab (hoechstens 2 MB). Fehler sind egal -- es ist nur ein Cache."""
        if (time.monotonic() < self._cache_pause or not daten or len(daten) > MAX_CACHE
                or sekunden <= 0):
            return False
        try:
            name = self.cache_name(art, was)
            self.cache.ausfuehren(
                f"INSERT INTO {SCHEMA}.cache (schluessel, art, daten, ablauf) VALUES "
                "(%s, %s, %s, now() + make_interval(secs => %s)) ON CONFLICT (schluessel) "
                "DO UPDATE SET art = EXCLUDED.art, daten = EXCLUDED.daten, "
                "ablauf = EXCLUDED.ablauf",
                (name, art[:40], bytes(self._fernet().encrypt(daten)), int(sekunden)))
            if int(name[:2], 16) < 6:
                # Etwa jeder vierzigste Eintrag raeumt Abgelaufenes weg.
                self.cache.ausfuehren(f"DELETE FROM {SCHEMA}.cache WHERE ablauf <= now()")
            return True
        except Exception:
            self._cache_pause = time.monotonic() + CACHE_PAUSE
            return False

    def gemerkt(self, art: str, sekunden: Callable[[str], int],
                holen: Callable[[str], bytes | None]) -> Callable[[str], bytes | None]:
        """Stellt den Cache vor einen Abruf: erst nachsehen, sonst holen und ablegen."""

        def mit_cache(was: str) -> bytes | None:
            vorhanden = self.cache_holen(art, was)
            if vorhanden is not None:
                return vorhanden
            frisch = holen(was)
            dauer = sekunden(was)
            if frisch is not None and dauer > 0:
                self.cache_setzen(art, was, frisch, dauer)
            return frisch

        return mit_cache

    # -- Auskunft ---------------------------------------------------------------------------

    def auskunft(self) -> dict[str, Any]:
        """Was der Verbund gerade tut -- ohne Adressen und Zugangsdaten."""
        return {
            "datenbanken": len(self.datenbanken),
            "konten": self.konten.name,
            "profile": [db.name for db in self.profile],
            "cache": self.cache.name,
            "geladen": len([t for t in self.bekannt if t != KERN]),
            "kern": self.stand.get(KERN, (0, (), ""))[0],
            "offen": len(self.offen),
            "fehler": self.letzter_fehler,
        }


def aus_umgebung(home: Path, umgebung: Mapping[str, str] | None = None) -> Verbund | None:
    """Der Verbund aus den Umgebungsvariablen -- None, wenn er nicht eingerichtet ist.

    Braucht ``AQUATICY_VERCEL_SECRET`` (ohne Schluessel wird nichts gespeichert) und mindestens
    eine Postgres-Adresse. ``AQUATICY_VERBUND=0`` schaltet ihn ab.
    """
    from aquaticy import vercel_blob

    umgebung = os.environ if umgebung is None else umgebung
    if str(umgebung.get("AQUATICY_VERBUND", "")).strip().lower() in ("0", "false", "aus", "off"):
        return None
    schluessel = vercel_blob.secret_key()
    gefunden = adressen(umgebung)
    if not schluessel or not gefunden:
        return None
    return Verbund([Datenbank(name, adresse) for name, adresse in gefunden], schluessel, home)
