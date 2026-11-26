"""Bestaetigung in zwei Schritten per E-Mail (16.5.7, Aquaticy-Test).

Wie bei grossen Diensten: Nach dem richtigen Passwort schickt Aquaticy einen Code mit sechs
Ziffern an die E-Mail-Adresse des Kontos. Erst mit diesem Code entsteht die Sitzung. Ist der
Code falsch, geht eine Warnung an dieselbe Adresse.

Was dafuer gilt:

* **Nur Hashes.** Gespeichert wird ein HMAC des Codes mit dem Geheimnis des Servers, nie der
  Code selbst. Die Kennung der Anmeldung im Browser ist ebenfalls nur als HMAC abgelegt.
* **Gebunden.** Ein Code gilt nur im selben Browser (Geraete-Keks und Kennung des Browsers)
  und nur, solange das Passwort dasselbe ist. Er gilt 10 Minuten und nur einmal.
* **Hoechstens 5 Versuche je Code.** Gezaehlt wird atomar in der Datenbank -- auf Vercel in der
  Postgres-Datenbank der Konten, damit keine zweite Instanz mitzaehlt, ohne es zu wissen.
  Dazu hoechstens 5 Mails je Viertelstunde und 20 am Tag je Konto.
* **Einschalten nur mit Code** an die Adresse des Kontos (sie koennte sonst falsch sein),
  **Ausschalten nur mit Passwort** -- eine offene Sitzung allein reicht nicht.
* **Kein stilles Abschalten.** Faellt der Mail-Versand weg, wartet die Anmeldung, bis er wieder
  geht. Nur der Betreiber kann den zweiten Schritt mit ``AQUATICY_2FA_AUS=1`` fuer alle
  aussetzen (Notfall, steht in der README).
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import html
import os
import secrets
import sqlite3
import threading
import time
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from aquaticy import mailversand

STELLEN = 6
GUELTIG = 10 * 60
MAX_VERSUCHE = 5
NEU_SENDEN_NACH = 60
MAX_MAILS = 5
MAILS_FENSTER = 15 * 60
MAX_MAILS_TAG = 20
WARN_ABSTAND = 10 * 60
AUS_SCHALTER = "AQUATICY_2FA_AUS"
ANMELDEN = "anmelden"
EINSCHALTEN = "einschalten"
NAME = "Bestätigung in zwei Schritten"
#: Mail-Dienst oder Datenbank fehlen: 424 statt 503 -- der Server ersetzt jede Meldung mit
#: Status ab 500 durch einen allgemeinen Satz, und dieser Hinweis soll ankommen.
ABHAENGIG = 424


class ZweiFaktorFehler(ValueError):
    """Etwas, das der Nutzer sehen darf -- mit dem passenden HTTP-Status."""

    def __init__(self, text: str, status: int = 400, *, neu_anmelden: bool = False) -> None:
        super().__init__(text)
        self.status = status
        self.neu_anmelden = neu_anmelden


@dataclass(frozen=True, slots=True)
class Versuch:
    user_id: str
    zweck: str
    code_hash: str
    bindung: str
    versuche: int
    gesendet: float


class Ablage(Protocol):
    def ist_an(self, user_id: str) -> bool: ...
    def setzen(self, user_id: str, an: bool, jetzt: float) -> None: ...
    def mails_seit(self, user_id: str, seit: float) -> int: ...
    def mail_merken(self, user_id: str, jetzt: float) -> None: ...
    def anlegen(self, kennung: str, user_id: str, zweck: str, code_hash: str, bindung: str,
                jetzt: float) -> None: ...
    def neuer_code(self, kennung: str, code_hash: str, jetzt: float) -> bool: ...
    def zeile(self, kennung: str) -> Versuch | None: ...
    def versuch(self, kennung: str, jetzt: float) -> Versuch | None: ...
    def verbrauchen(self, kennung: str) -> bool: ...
    def warnen_erlaubt(self, user_id: str, jetzt: float) -> bool: ...
    def konto_weg(self, user_id: str) -> None: ...


# -- Ablage in SQLite (Rechner, Vercel ohne Postgres) ----------------------------------------

class SqliteAblage:
    """In der Konten-Datei selbst: ein Prozess, also atomar mit BEGIN IMMEDIATE."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._sperre = threading.RLock()
        with self._verbinden() as conn:
            conn.executescript(
                "CREATE TABLE IF NOT EXISTS zf_konten (user_id TEXT PRIMARY KEY, "
                "an INTEGER NOT NULL, seit REAL NOT NULL);"
                "CREATE TABLE IF NOT EXISTS zf_codes (kennung TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, zweck TEXT NOT NULL, code_hash TEXT NOT NULL, "
                "bindung TEXT NOT NULL, erstellt REAL NOT NULL, ablauf REAL NOT NULL, "
                "gesendet REAL NOT NULL, versuche INTEGER NOT NULL DEFAULT 0);"
                "CREATE TABLE IF NOT EXISTS zf_mails (user_id TEXT NOT NULL, zeit REAL NOT NULL);"
                "CREATE TABLE IF NOT EXISTS zf_warnungen (user_id TEXT PRIMARY KEY, "
                "zuletzt REAL NOT NULL);")

    @contextlib.contextmanager
    def _verbinden(self) -> Any:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        try:
            yield conn
        finally:
            conn.close()

    def _schreiben(self, arbeit: Callable[[sqlite3.Connection], Any]) -> Any:
        with self._sperre, self._verbinden() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                ergebnis = arbeit(conn)
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
            return ergebnis

    def ist_an(self, user_id: str) -> bool:
        with self._verbinden() as conn:
            zeile = conn.execute("SELECT an FROM zf_konten WHERE user_id=?",
                                 (user_id,)).fetchone()
        return bool(zeile and zeile[0])

    def setzen(self, user_id: str, an: bool, jetzt: float) -> None:
        self._schreiben(lambda c: c.execute(
            "INSERT INTO zf_konten (user_id, an, seit) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET an=excluded.an, seit=excluded.seit",
            (user_id, 1 if an else 0, jetzt)))

    def mails_seit(self, user_id: str, seit: float) -> int:
        with self._verbinden() as conn:
            return int(conn.execute("SELECT count(*) FROM zf_mails WHERE user_id=? AND zeit>?",
                                    (user_id, seit)).fetchone()[0])

    def mail_merken(self, user_id: str, jetzt: float) -> None:
        def arbeit(c: sqlite3.Connection) -> None:
            c.execute("DELETE FROM zf_mails WHERE zeit<?", (jetzt - 86400,))
            c.execute("DELETE FROM zf_codes WHERE ablauf<?", (jetzt - 3600,))
            c.execute("INSERT INTO zf_mails (user_id, zeit) VALUES (?, ?)", (user_id, jetzt))
        self._schreiben(arbeit)

    def anlegen(self, kennung: str, user_id: str, zweck: str, code_hash: str, bindung: str,
                jetzt: float) -> None:
        self._schreiben(lambda c: c.execute(
            "INSERT INTO zf_codes (kennung, user_id, zweck, code_hash, bindung, erstellt, "
            "ablauf, gesendet, versuche) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (kennung, user_id, zweck, code_hash, bindung, jetzt, jetzt + GUELTIG, jetzt)))

    def neuer_code(self, kennung: str, code_hash: str, jetzt: float) -> bool:
        return bool(self._schreiben(lambda c: c.execute(
            "UPDATE zf_codes SET code_hash=?, gesendet=?, ablauf=? WHERE kennung=? "
            "AND versuche<? AND ablauf>?",
            (code_hash, jetzt, jetzt + GUELTIG, kennung, MAX_VERSUCHE, jetzt)).rowcount))

    @staticmethod
    def _versuch(zeile: Any) -> Versuch | None:
        if zeile is None:
            return None
        return Versuch(str(zeile[0]), str(zeile[1]), str(zeile[2]), str(zeile[3]),
                       int(zeile[4]), float(zeile[5]))

    def zeile(self, kennung: str) -> Versuch | None:
        with self._verbinden() as conn:
            return self._versuch(conn.execute(
                "SELECT user_id, zweck, code_hash, bindung, versuche, gesendet FROM zf_codes "
                "WHERE kennung=?", (kennung,)).fetchone())

    def versuch(self, kennung: str, jetzt: float) -> Versuch | None:
        def arbeit(c: sqlite3.Connection) -> Versuch | None:
            gezaehlt = c.execute(
                "UPDATE zf_codes SET versuche=versuche+1 WHERE kennung=? AND versuche<? "
                "AND ablauf>?", (kennung, MAX_VERSUCHE, jetzt)).rowcount
            if not gezaehlt:
                return None
            return self._versuch(c.execute(
                "SELECT user_id, zweck, code_hash, bindung, versuche, gesendet FROM zf_codes "
                "WHERE kennung=?", (kennung,)).fetchone())
        return self._schreiben(arbeit)

    def verbrauchen(self, kennung: str) -> bool:
        return bool(self._schreiben(lambda c: c.execute(
            "DELETE FROM zf_codes WHERE kennung=?", (kennung,)).rowcount))

    def warnen_erlaubt(self, user_id: str, jetzt: float) -> bool:
        def arbeit(c: sqlite3.Connection) -> bool:
            zeile = c.execute("SELECT zuletzt FROM zf_warnungen WHERE user_id=?",
                              (user_id,)).fetchone()
            if zeile is not None and float(zeile[0]) > jetzt - WARN_ABSTAND:
                return False
            c.execute("INSERT INTO zf_warnungen (user_id, zuletzt) VALUES (?, ?) "
                      "ON CONFLICT(user_id) DO UPDATE SET zuletzt=excluded.zuletzt",
                      (user_id, jetzt))
            return True
        return bool(self._schreiben(arbeit))

    def konto_weg(self, user_id: str) -> None:
        def arbeit(c: sqlite3.Connection) -> None:
            for tabelle in ("zf_konten", "zf_codes", "zf_mails", "zf_warnungen"):
                c.execute(f"DELETE FROM {tabelle} WHERE user_id=?", (user_id,))  # nosec B608
        self._schreiben(arbeit)


# -- Ablage in Postgres (Vercel mit Speicher-Verbund) ----------------------------------------

_PG_TABELLEN = (
    "CREATE TABLE IF NOT EXISTS aquaticy.zf_konten (user_id TEXT PRIMARY KEY, "
    "an BOOLEAN NOT NULL, seit DOUBLE PRECISION NOT NULL)",
    "CREATE TABLE IF NOT EXISTS aquaticy.zf_codes (kennung TEXT PRIMARY KEY, "
    "user_id TEXT NOT NULL, zweck TEXT NOT NULL, code_hash TEXT NOT NULL, bindung TEXT NOT NULL, "
    "erstellt DOUBLE PRECISION NOT NULL, ablauf DOUBLE PRECISION NOT NULL, "
    "gesendet DOUBLE PRECISION NOT NULL, versuche INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS aquaticy.zf_mails (user_id TEXT NOT NULL, "
    "zeit DOUBLE PRECISION NOT NULL)",
    "CREATE TABLE IF NOT EXISTS aquaticy.zf_warnungen (user_id TEXT PRIMARY KEY, "
    "zuletzt DOUBLE PRECISION NOT NULL)",
)


class PostgresAblage:
    """In der Postgres-Datenbank der Konten: jede Zaehlung ist eine einzelne Anweisung.

    Der Teil ``kern`` des Speicher-Verbunds ist eine Einheit (die spaetere Instanz gewinnt).
    Fuer einen Versuchszaehler reicht das nicht -- darum liegen Codes und Versuche hier.
    """

    def __init__(self, datenbank: Any) -> None:
        self.db = datenbank
        self._bereit = False

    def _sql(self, anweisung: str, werte: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        if not self._bereit:
            fertig = True
            for tabelle in _PG_TABELLEN:
                # Zwei Instanzen legen gleichzeitig an: die zweite scheitert, die Tabelle steht.
                # Dann beim naechsten Mal noch einmal (IF NOT EXISTS) -- nie still "bereit".
                try:
                    self.db.ausfuehren(tabelle)
                except Exception:
                    fertig = False
            self._bereit = fertig
        return list(self.db.ausfuehren(anweisung, werte))

    def ist_an(self, user_id: str) -> bool:
        zeilen = self._sql("SELECT an FROM aquaticy.zf_konten WHERE user_id=%s", (user_id,))
        return bool(zeilen and zeilen[0][0])

    def setzen(self, user_id: str, an: bool, jetzt: float) -> None:
        self._sql("INSERT INTO aquaticy.zf_konten (user_id, an, seit) VALUES (%s, %s, %s) "
                  "ON CONFLICT (user_id) DO UPDATE SET an=EXCLUDED.an, seit=EXCLUDED.seit",
                  (user_id, bool(an), jetzt))

    def mails_seit(self, user_id: str, seit: float) -> int:
        zeilen = self._sql("SELECT count(*) FROM aquaticy.zf_mails WHERE user_id=%s AND zeit>%s",
                           (user_id, seit))
        return int(zeilen[0][0]) if zeilen else 0

    def mail_merken(self, user_id: str, jetzt: float) -> None:
        self._sql("DELETE FROM aquaticy.zf_mails WHERE zeit<%s", (jetzt - 86400,))
        self._sql("DELETE FROM aquaticy.zf_codes WHERE ablauf<%s", (jetzt - 3600,))
        self._sql("INSERT INTO aquaticy.zf_mails (user_id, zeit) VALUES (%s, %s)",
                  (user_id, jetzt))

    def anlegen(self, kennung: str, user_id: str, zweck: str, code_hash: str, bindung: str,
                jetzt: float) -> None:
        self._sql("INSERT INTO aquaticy.zf_codes (kennung, user_id, zweck, code_hash, bindung, "
                  "erstellt, ablauf, gesendet, versuche) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
                  "0)", (kennung, user_id, zweck, code_hash, bindung, jetzt, jetzt + GUELTIG,
                         jetzt))

    def neuer_code(self, kennung: str, code_hash: str, jetzt: float) -> bool:
        return bool(self._sql(
            "UPDATE aquaticy.zf_codes SET code_hash=%s, gesendet=%s, ablauf=%s WHERE kennung=%s "
            "AND versuche<%s AND ablauf>%s RETURNING kennung",
            (code_hash, jetzt, jetzt + GUELTIG, kennung, MAX_VERSUCHE, jetzt)))

    @staticmethod
    def _versuch(zeilen: list[tuple[Any, ...]]) -> Versuch | None:
        if not zeilen:
            return None
        z = zeilen[0]
        return Versuch(str(z[0]), str(z[1]), str(z[2]), str(z[3]), int(z[4]), float(z[5]))

    def zeile(self, kennung: str) -> Versuch | None:
        return self._versuch(self._sql(
            "SELECT user_id, zweck, code_hash, bindung, versuche, gesendet FROM "
            "aquaticy.zf_codes WHERE kennung=%s", (kennung,)))

    def versuch(self, kennung: str, jetzt: float) -> Versuch | None:
        return self._versuch(self._sql(
            "UPDATE aquaticy.zf_codes SET versuche=versuche+1 WHERE kennung=%s AND versuche<%s "
            "AND ablauf>%s RETURNING user_id, zweck, code_hash, bindung, versuche, gesendet",
            (kennung, MAX_VERSUCHE, jetzt)))

    def verbrauchen(self, kennung: str) -> bool:
        return bool(self._sql("DELETE FROM aquaticy.zf_codes WHERE kennung=%s RETURNING kennung",
                              (kennung,)))

    def warnen_erlaubt(self, user_id: str, jetzt: float) -> bool:
        return bool(self._sql(
            "INSERT INTO aquaticy.zf_warnungen (user_id, zuletzt) VALUES (%s, %s) "
            "ON CONFLICT (user_id) DO UPDATE SET zuletzt=EXCLUDED.zuletzt "
            "WHERE aquaticy.zf_warnungen.zuletzt<%s RETURNING user_id",
            (user_id, jetzt, jetzt - WARN_ABSTAND)))

    def konto_weg(self, user_id: str) -> None:
        for tabelle in ("zf_konten", "zf_codes", "zf_mails", "zf_warnungen"):
            self._sql(f"DELETE FROM aquaticy.{tabelle} WHERE user_id=%s",  # nosec B608
                      (user_id,))


# -- Texte der Mails -------------------------------------------------------------------------

def maskiert(email: str) -> str:
    """ "jonas@example.org" -> "jo•••@example.org" (fuer Anzeige und Antworten)."""
    lokal, _, domain = (email or "").partition("@")
    if not domain:
        return "•••"
    return (lokal[:2] if len(lokal) > 3 else lokal[:1]) + "•••@" + domain


def _zeitpunkt(jetzt: float, sprache: str) -> str:
    try:
        from zoneinfo import ZoneInfo

        zeit = datetime.fromtimestamp(jetzt, ZoneInfo("Europe/Berlin"))
    except Exception:
        zeit = datetime.fromtimestamp(jetzt).astimezone()
    zone = zeit.tzname() or ""
    if sprache == "en":
        return zeit.strftime("%d %b %Y, %H:%M") + (f" ({zone})" if zone else "")
    zone = {"CET": "MEZ", "CEST": "MESZ"}.get(zone, zone)
    return zeit.strftime("%d.%m.%Y, %H:%M Uhr") + (f" ({zone})" if zone else "")


_FUSS = {
    "de": "Diese E-Mail wurde automatisch verschickt. Antworten kommen nicht an.",
    "en": "This email was sent automatically. Replies are not received.",
}


def _html(titel: str, absaetze: list[str], code: str = "", website: str = "",
          sprache: str = "de") -> str:
    """Eine schlichte Mail mit Karte, wie man sie von grossen Diensten kennt. Alles escaped."""
    teile = [f'<p style="margin:0 0 16px">{html.escape(a).replace(chr(10), "<br>")}</p>'
             for a in absaetze]
    if code:
        teile.insert(1, '<p style="margin:8px 0 24px;font-size:32px;font-weight:700;'
                        'letter-spacing:6px;font-family:Consolas,monospace">'
                        f'{html.escape(code)}</p>')
    link = (f'<br><a href="https://{html.escape(website)}" style="color:#5f6368">'
            f'{html.escape(website)}</a>' if website else "")
    return (
        '<!doctype html><html><body style="margin:0;background:#f1f3f4;'
        'font-family:Arial,Helvetica,sans-serif;color:#202124">'
        '<div style="max-width:520px;margin:24px auto;background:#fff;border:1px solid #dadce0;'
        'border-radius:8px;padding:32px 40px">'
        '<div style="font-size:20px;color:#1a73e8;font-weight:700;margin-bottom:16px">'
        'Aquaticy</div>'
        f'<h1 style="font-size:22px;font-weight:400;margin:0 0 24px">{html.escape(titel)}</h1>'
        + "".join(teile)
        + '</div><p style="max-width:520px;margin:0 auto 24px;font-size:12px;color:#5f6368;'
        f'text-align:center">{html.escape(_FUSS.get(sprache, _FUSS["de"]))}{link}</p>'
        '</body></html>'
    )


def _text(titel: str, absaetze: list[str], code: str = "", website: str = "",
          sprache: str = "de") -> str:
    teile = [titel, "", absaetze[0], ""]
    if code:
        teile += [code, ""]
    for absatz in absaetze[1:]:
        teile += [absatz, ""]
    teile.append(_FUSS.get(sprache, _FUSS["de"]))
    if website:
        teile.append(f"Aquaticy · https://{website}")
    return "\n".join(teile) + "\n"


def mail_code(zweck: str, name: str, email: str, code: str, website: str,
              sprache: str = "de") -> tuple[str, str, str]:
    """(Betreff, Text, HTML) der Mail mit dem Code."""
    if sprache == "en":
        if zweck == EINSCHALTEN:
            betreff, titel = "Confirm your email address for Aquaticy", "Confirm your email"
            absaetze = [f"Hi {name},\nyou want to turn on two-step verification for your "
                        f"Aquaticy account {email}. Enter this code to confirm your address:",
                        "The code is valid for 10 minutes.",
                        "Wasn't you? Then you can ignore this email."]
        else:
            betreff, titel = "Your Aquaticy verification code", "Verification code"
            absaetze = [f"Hi {name},\nsomeone is signing in to your Aquaticy account {email}. "
                        "Use this code to confirm it's you:",
                        "The code is valid for 10 minutes. Don't share it with anyone.",
                        "Wasn't you? Then someone knows your password. Change it in Aquaticy "
                        "under Settings → Account."]
    elif zweck == EINSCHALTEN:
        betreff, titel = ("Bestätige deine E-Mail-Adresse für Aquaticy",
                          "Bestätige deine E-Mail-Adresse")
        absaetze = [f"Hallo {name},\ndu möchtest die {NAME} für dein Aquaticy-Konto {email} "
                    "einschalten. Gib dazu diesen Code ein:",
                    "Der Code gilt 10 Minuten.",
                    "Warst du das nicht? Dann kannst du diese E-Mail einfach ignorieren."]
    else:
        betreff, titel = "Dein Aquaticy-Bestätigungscode", "Bestätigungscode"
        absaetze = [f"Hallo {name},\njemand meldet sich gerade mit deinem Aquaticy-Konto "
                    f"{email} an. Mit diesem Code bestätigst du, dass du es bist:",
                    "Der Code gilt 10 Minuten. Gib ihn an niemanden weiter.",
                    "Warst du das nicht? Dann kennt jemand dein Passwort. Ändere es in Aquaticy "
                    "unter Einstellungen → Konto."]
    return (betreff, _text(titel, absaetze, code, website, sprache),
            _html(titel, absaetze, code, website, sprache))


def mail_warnung(name: str, email: str, jetzt: float, geraet: str, website: str,
                 sprache: str = "de") -> tuple[str, str, str]:
    """(Betreff, Text, HTML) der Warnung nach einem falschen Code."""
    zeit = _zeitpunkt(jetzt, sprache)
    if sprache == "en":
        betreff, titel = "Security alert for your Aquaticy account", "Someone tried to sign in"
        absaetze = [f"Hi {name},\na wrong verification code was just entered for your Aquaticy "
                    f"account {email}. The password was correct. The sign-in was blocked.",
                    f"Time: {zeit}\nDevice: {geraet or 'unknown'}",
                    "Was it you? Then you don't need to do anything.",
                    "Wasn't you? Then someone knows your password. Change it now in Aquaticy "
                    "under Settings → Account. All other devices will be signed out."]
    else:
        betreff, titel = ("Sicherheitswarnung für dein Aquaticy-Konto",
                          "Jemand hat versucht, sich anzumelden")
        absaetze = [f"Hallo {name},\nfür dein Aquaticy-Konto {email} wurde gerade ein falscher "
                    "Bestätigungscode eingegeben. Das Passwort war richtig. Die Anmeldung wurde "
                    "nicht zugelassen.",
                    f"Zeit: {zeit}\nGerät: {geraet or 'unbekannt'}",
                    "Warst du das? Dann musst du nichts tun.",
                    "Warst du das nicht? Dann kennt jemand dein Passwort. Ändere es jetzt in "
                    "Aquaticy unter Einstellungen → Konto. Danach sind alle anderen Geräte "
                    "abgemeldet."]
    return (betreff, _text(titel, absaetze, "", website, sprache),
            _html(titel, absaetze, "", website, sprache))


def mail_schalter(an: bool, name: str, email: str, website: str,
                  sprache: str = "de") -> tuple[str, str, str]:
    """(Betreff, Text, HTML) der Nachricht, wenn die Bestaetigung an- oder ausgeht."""
    if sprache == "en":
        if an:
            betreff = titel = "Two-step verification is now on"
            absaetze = [f"Hi {name},\ntwo-step verification is now on for your Aquaticy account "
                        f"{email}. From now on, we'll send a code to this address every time "
                        "you sign in.",
                        "Wasn't you? Then change your password right away."]
        else:
            betreff = titel = "Two-step verification is now off"
            absaetze = [f"Hi {name},\ntwo-step verification is now off for your Aquaticy "
                        f"account {email}. Your password is enough to sign in again.",
                        "Wasn't you? Then change your password right away and turn it back on."]
    elif an:
        betreff = titel = f"Die {NAME} ist jetzt an"
        absaetze = [f"Hallo {name},\nfür dein Aquaticy-Konto {email} ist die {NAME} jetzt "
                    "eingeschaltet. Bei jeder Anmeldung schicken wir dir ab jetzt einen Code an "
                    "diese Adresse.",
                    "Warst du das nicht? Dann ändere sofort dein Passwort."]
    else:
        betreff = titel = f"Die {NAME} ist jetzt aus"
        absaetze = [f"Hallo {name},\nfür dein Aquaticy-Konto {email} ist die {NAME} jetzt "
                    "ausgeschaltet. Zum Anmelden reicht wieder dein Passwort.",
                    "Warst du das nicht? Dann ändere sofort dein Passwort und schalte sie wieder "
                    "ein."]
    return (betreff, _text(titel, absaetze, "", website, sprache),
            _html(titel, absaetze, "", website, sprache))


# -- Ablauf ----------------------------------------------------------------------------------

def echte_adresse(email: str) -> bool:
    """Hat das Konto eine echte E-Mail-Adresse? (Alte Einzelkonten haben eine interne.)"""
    from aquaticy.auth import LOCAL_EMAIL_DOMAIN

    return "@" in (email or "") and not email.lower().endswith("@" + LOCAL_EMAIL_DOMAIN)


class ZweiFaktor:
    """Die Bestaetigung in zwei Schritten fuer ein AuthStore."""

    def __init__(self, auth: Any, ablage: Ablage, *, kopie: Ablage | None = None,
                 mail: mailversand.Einrichtung | None = None,
                 umgebung: Mapping[str, str] | None = None,
                 uhr: Callable[[], float] = time.time,
                 senden: Callable[..., None] = mailversand.senden) -> None:
        self.auth = auth
        self.ablage = ablage
        #: Auf Vercel: eine Kopie des Schalters im Teil "kern" -- falls Postgres kurz fehlt.
        self.kopie = kopie
        self.umgebung = os.environ if umgebung is None else umgebung
        self.mail = mail if mail is not None else mailversand.aus_umgebung(self.umgebung)
        self.uhr = uhr
        self._senden = senden

    # -- Hilfen ------------------------------------------------------------------------------

    def _hash(self, art: str, *teile: str) -> str:
        nachricht = ("aquaticy/2fa/" + art + "\0" + "\0".join(teile)).encode("utf-8")
        return hmac.new(self.auth._pepper, nachricht, hashlib.sha256).hexdigest()

    def _bindung(self, account: Any, geraet_text: str, geraet_kennung: str) -> str:
        return self._hash("bindung", account.id, geraet_text, geraet_kennung,
                          bytes(account._credential).hex())

    def _mail(self, an: str, inhalt: tuple[str, str, str]) -> None:
        if self.mail is None:
            raise ZweiFaktorFehler("Der E-Mail-Versand ist nicht eingerichtet.", ABHAENGIG)
        betreff, text, html_teil = inhalt
        try:
            self._senden(self.mail, an, betreff, text, html_teil)
        except mailversand.MailFehler as fehler:
            print(f"  [2FA] Mail nicht verschickt: {fehler}")
            raise ZweiFaktorFehler("Die E-Mail mit dem Code ließ sich gerade nicht verschicken. "
                                   "Versuch es gleich noch einmal.", ABHAENGIG) from None

    @property
    def website(self) -> str:
        return self.mail.website if self.mail is not None else mailversand.website_aus(
            self.umgebung)

    def abgeschaltet(self) -> bool:
        """Hat der Betreiber den zweiten Schritt fuer alle ausgesetzt (Notfall)?"""
        return str(self.umgebung.get(AUS_SCHALTER, "")).strip().lower() in {
            "1", "true", "ja", "an", "on"}

    def ist_an(self, user_id: str) -> bool:
        """Ist der zweite Schritt fuer dieses Konto an? Raises: ZweiFaktorFehler (424)."""
        try:
            return self.ablage.ist_an(user_id)
        except Exception:
            if self.kopie is None:
                raise ZweiFaktorFehler("Die Anmeldung geht gerade nicht. Versuch es gleich noch "
                                       "einmal.", ABHAENGIG) from None
        return self.kopie.ist_an(user_id)

    def noetig(self, account: Any) -> bool:
        """Braucht diese Anmeldung den zweiten Schritt?"""
        return not self.abgeschaltet() and self.ist_an(account.id)

    def zustand(self, account: Any) -> dict[str, Any]:
        try:
            an = self.ist_an(account.id)
        except ZweiFaktorFehler:
            an = False
        grund = ""
        if self.mail is None:
            grund = ("Dafür muss der Betreiber einen E-Mail-Versand einrichten (README, "
                     "„Bestätigung in zwei Schritten“).")
        elif not echte_adresse(account.email):
            grund = "Dein Konto hat keine E-Mail-Adresse. Dafür braucht es eine."
        return {"an": an, "moeglich": not grund or an, "grund": grund,
                "email": maskiert(account.email) if echte_adresse(account.email) else "",
                "abgeschaltet": self.abgeschaltet()}

    def _drosseln(self, user_id: str, jetzt: float) -> None:
        if (self.ablage.mails_seit(user_id, jetzt - MAILS_FENSTER) >= MAX_MAILS
                or self.ablage.mails_seit(user_id, jetzt - 86400) >= MAX_MAILS_TAG):
            raise ZweiFaktorFehler("Wir haben dir gerade schon mehrere Codes geschickt. Warte "
                                   "eine Viertelstunde und versuch es dann noch einmal.", 429)

    # -- Code schicken -----------------------------------------------------------------------

    def beginnen(self, account: Any, zweck: str, geraet_text: str, geraet_kennung: str,
                 sprache: str = "de") -> dict[str, Any]:
        """Neuer Code an die Adresse des Kontos. Returns: Kennung fuer den Browser."""
        if not echte_adresse(account.email):
            raise ZweiFaktorFehler("Dein Konto hat keine E-Mail-Adresse. Dafür braucht es eine.")
        if self.mail is None:
            raise ZweiFaktorFehler(
                "Der E-Mail-Versand ist nicht eingerichtet. Der Betreiber kann den zweiten "
                "Schritt mit AQUATICY_2FA_AUS=1 vorübergehend aussetzen.", ABHAENGIG)
        jetzt = self.uhr()
        self._drosseln(account.id, jetzt)
        token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(10 ** STELLEN):0{STELLEN}d}"
        kennung = self._hash("kennung", token)
        self.ablage.anlegen(kennung, account.id, zweck, self._hash("code", kennung, code),
                            self._bindung(account, geraet_text, geraet_kennung), jetzt)
        self.ablage.mail_merken(account.id, jetzt)
        try:
            self._mail(account.email, mail_code(zweck, account.username or "", account.email,
                                                code, self.website, sprache))
        except ZweiFaktorFehler:
            self.ablage.verbrauchen(kennung)
            raise
        return {"challenge": token, "an": maskiert(account.email), "gueltig": GUELTIG,
                "neu_nach": NEU_SENDEN_NACH}

    def neu_senden(self, token: str, geraet_text: str, geraet_kennung: str,
                   sprache: str = "de") -> dict[str, Any]:
        """Ein neuer Code fuer dieselbe Anmeldung. Die Versuche zaehlen weiter."""
        kennung = self._hash("kennung", str(token or ""))
        zeile = self.ablage.zeile(kennung)
        jetzt = self.uhr()
        account = self.auth.account(zeile.user_id) if zeile else None
        if (zeile is None or account is None or not hmac.compare_digest(
                zeile.bindung, self._bindung(account, geraet_text, geraet_kennung))):
            raise ZweiFaktorFehler("Diese Anmeldung ist abgelaufen. Melde dich neu an.", 401,
                                   neu_anmelden=True)
        if jetzt - zeile.gesendet < NEU_SENDEN_NACH:
            warte = int(NEU_SENDEN_NACH - (jetzt - zeile.gesendet)) + 1
            raise ZweiFaktorFehler(f"Warte noch {warte} Sekunden, dann kannst du einen neuen "
                                   "Code anfordern.", 429)
        self._drosseln(account.id, jetzt)
        code = f"{secrets.randbelow(10 ** STELLEN):0{STELLEN}d}"
        if not self.ablage.neuer_code(kennung, self._hash("code", kennung, code), jetzt):
            raise ZweiFaktorFehler("Diese Anmeldung ist abgelaufen. Melde dich neu an.", 401,
                                   neu_anmelden=True)
        self.ablage.mail_merken(account.id, jetzt)
        self._mail(account.email, mail_code(zeile.zweck, account.username or "", account.email,
                                            code, self.website, sprache))
        return {"ok": True, "an": maskiert(account.email), "neu_nach": NEU_SENDEN_NACH}

    # -- Code pruefen ------------------------------------------------------------------------

    def pruefen(self, token: str, code: str, zweck: str, geraet_text: str,
                geraet_kennung: str, *, sprache: str = "de", geraet: str = "") -> Any:
        """Prueft einen Code. Returns: das Konto. Raises: ZweiFaktorFehler."""
        abgelaufen = ZweiFaktorFehler("Der Code ist abgelaufen oder wurde zu oft falsch "
                                      "eingegeben. Melde dich neu an.", 401, neu_anmelden=True)
        # 17.1.1: Ziffern aus jeder Schrift ("۱۲۳", "١٢٣", "１２３") als 0 bis 9 -- vorher
        # galt der richtige Code von einer persischen Tastatur als falsch und kostete
        # Versuche.
        eingabe = "".join(str(unicodedata.decimal(z)) for z in str(code or "")
                          if z.isdecimal())
        kennung = self._hash("kennung", str(token or ""))
        jetzt = self.uhr()
        versuch = self.ablage.versuch(kennung, jetzt)
        if versuch is None or versuch.zweck != zweck:
            raise abgelaufen
        account = self.auth.account(versuch.user_id)
        if account is None or not hmac.compare_digest(
                versuch.bindung, self._bindung(account, geraet_text, geraet_kennung)):
            # Anderer Browser oder inzwischen ein neues Passwort: diese Anmeldung gilt nicht mehr.
            self.ablage.verbrauchen(kennung)
            raise abgelaufen
        richtig = len(eingabe) == STELLEN and hmac.compare_digest(
            versuch.code_hash, self._hash("code", kennung, eingabe))
        if richtig:
            # Nur eine Anfrage kann den Code verbrauchen -- eine zweite mit demselben Code nicht.
            if self.ablage.verbrauchen(kennung):
                return account
            raise abgelaufen
        rest = MAX_VERSUCHE - versuch.versuche
        if zweck == ANMELDEN and self.ablage.warnen_erlaubt(account.id, jetzt):
            with contextlib.suppress(ZweiFaktorFehler):
                self._mail(account.email, mail_warnung(account.username or "", account.email,
                                                       jetzt, geraet, self.website, sprache))
        if rest <= 0:
            self.ablage.verbrauchen(kennung)
            raise abgelaufen
        raise ZweiFaktorFehler("Der Code stimmt nicht. Du hast noch einen Versuch." if rest == 1
                               else f"Der Code stimmt nicht. Du hast noch {rest} Versuche.", 401)

    # -- Ein und aus -------------------------------------------------------------------------

    def _schalten(self, account: Any, an: bool, sprache: str) -> None:
        jetzt = self.uhr()
        self.ablage.setzen(account.id, an, jetzt)
        if self.kopie is not None:
            with contextlib.suppress(Exception):
                self.kopie.setzen(account.id, an, jetzt)
        with contextlib.suppress(ZweiFaktorFehler):
            self._mail(account.email, mail_schalter(an, account.username or "", account.email,
                                                    self.website, sprache))

    def einschalten(self, account: Any, token: str, code: str, geraet_text: str,
                    geraet_kennung: str, sprache: str = "de") -> None:
        bestaetigt = self.pruefen(token, code, EINSCHALTEN, geraet_text, geraet_kennung,
                                  sprache=sprache)
        if bestaetigt.id != account.id:
            raise ZweiFaktorFehler("Dieser Code gehört zu einem anderen Konto.", 403)
        self._schalten(account, True, sprache)

    def ausschalten(self, account: Any, passwort: str, sprache: str = "de") -> bool:
        """Nur mit dem Passwort. Returns: False, wenn das Passwort nicht stimmt."""
        geprueft = self.auth.authenticate(account.email, passwort)
        if geprueft is None or geprueft.id != account.id:
            return False
        self._schalten(account, False, sprache)
        return True

    def konto_weg(self, user_id: str) -> None:
        for ablage in (self.ablage, self.kopie):
            if ablage is not None:
                with contextlib.suppress(Exception):
                    ablage.konto_weg(user_id)
