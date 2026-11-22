"""16.5.7: Bestaetigung in zwei Schritten per E-Mail (Aquaticy-Test).

Mailversand gegen einen SMTP-Nachbau auf 127.0.0.1 (echtes smtplib, echtes TLS), der Ablauf mit
einer gestellten Uhr, die Anmeldung ueber den echten Server und -- mit
``AQUATICY_TEST_POSTGRES`` -- die Zaehlung in Postgres ueber zwei Verbindungen.
"""

from __future__ import annotations

import base64
import contextlib
import datetime
import json
import os
import re
import socket
import sqlite3
import ssl
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from aquaticy import mailversand, standard, web
from aquaticy.auth import AuthStore
from aquaticy.zweifaktor import (
    ANMELDEN,
    EINSCHALTEN,
    MAX_VERSUCHE,
    SqliteAblage,
    ZweiFaktor,
    ZweiFaktorFehler,
    mail_code,
    mail_warnung,
    maskiert,
)
from tests.anmeldung import AGENT, FETCH, SPRACHE, wie_die_app

PASSWORT = "ein langes Passwort"
GERAET = AGENT + "\x1f" + SPRACHE
KEKS = "geraet-eins"
POSTFACH_ADRESSE = "aquaticy@example.org"


class Uhr:
    def __init__(self) -> None:
        self.t = 1_800_000_000.0

    def __call__(self) -> float:
        return self.t


class Postfach:
    def __init__(self) -> None:
        self.mails: list[dict[str, str]] = []
        self.kaputt = False

    def __call__(self, einrichtung: Any, an: str, betreff: str, text: str, html: str = "",
                 **_: Any) -> None:
        if self.kaputt:
            raise mailversand.MailFehler("Der Mail-Dienst ist nicht erreichbar (Test).")
        mailversand.nachricht(einrichtung, an, betreff, text, html)
        self.mails.append({"an": an, "betreff": betreff, "text": text, "html": html})

    def code(self) -> str:
        treffer = re.findall(r"^(\d{6})$", self.mails[-1]["text"], re.M)
        assert len(treffer) == 1, self.mails[-1]["text"]
        return treffer[0]


EINRICHTUNG = mailversand.Einrichtung("smtp.example.org", 465, POSTFACH_ADRESSE,
                                      "nur-zum-testen", POSTFACH_ADRESSE,
                                      "aquaticy-test.vercel.app", direkt=True)


@pytest.fixture
def auth(tmp_path: Path) -> AuthStore:
    store = AuthStore(tmp_path / "konten", "PRO234567")
    store.register("jonas@example.org", PASSWORT, "normal", username="Jonas",
                   terms_accepted=True, terms_version="test")
    return store


@pytest.fixture
def uhr() -> Uhr:
    return Uhr()


@pytest.fixture
def postfach() -> Postfach:
    return Postfach()


@pytest.fixture
def zf(auth: AuthStore, uhr: Uhr, postfach: Postfach) -> ZweiFaktor:
    return ZweiFaktor(auth, SqliteAblage(auth.db_path), mail=EINRICHTUNG, umgebung={}, uhr=uhr,
                      senden=postfach)


def konto(auth: AuthStore) -> Any:
    gefunden = auth.authenticate("jonas@example.org", PASSWORT)
    assert gefunden is not None
    return gefunden


# -- Absender und Mail ----------------------------------------------------------------------

def test_without_smtp_there_is_no_mail_service() -> None:
    assert mailversand.aus_umgebung({}) is None
    assert mailversand.aus_umgebung({"AQUATICY_SMTP_HOST": "smtp.gmail.com",
                                     "AQUATICY_SMTP_USER": POSTFACH_ADRESSE}) is None
    # Port 25 ist unverschluesselt: kein Versand.
    assert mailversand.aus_umgebung({
        "AQUATICY_SMTP_HOST": "smtp.gmail.com", "AQUATICY_SMTP_PORT": "25",
        "AQUATICY_SMTP_USER": POSTFACH_ADRESSE, "AQUATICY_SMTP_PASSWORD": "x"}) is None


def test_a_vercel_app_domain_is_the_name_not_the_sender() -> None:
    einrichtung = mailversand.aus_umgebung({
        "AQUATICY_SMTP_HOST": "smtp.gmail.com", "AQUATICY_SMTP_USER": POSTFACH_ADRESSE,
        "AQUATICY_SMTP_PASSWORD": "x", "VERCEL_PROJECT_PRODUCTION_URL": "aquaticy-test.vercel.app"})
    assert einrichtung is not None
    assert einrichtung.absender == POSTFACH_ADRESSE
    assert einrichtung.name == "Aquaticy (aquaticy-test.vercel.app)"
    assert einrichtung.direkt is True
    mail = mailversand.nachricht(einrichtung, "jonas@example.org", "Betreff", "Text")
    # Wegen der Klammern setzt die Mail den Namen in Anfuehrungszeichen (RFC 5322).
    assert mail["From"] == f'"Aquaticy (aquaticy-test.vercel.app)" <{POSTFACH_ADRESSE}>'


def test_an_own_domain_becomes_the_sender() -> None:
    umgebung = {"AQUATICY_SMTP_HOST": "smtp.resend.com", "AQUATICY_SMTP_PORT": "587",
                "AQUATICY_SMTP_USER": "resend", "AQUATICY_SMTP_PASSWORD": "x",
                "VERCEL_PROJECT_PRODUCTION_URL": "aquaticy.example.org"}
    einrichtung = mailversand.aus_umgebung(umgebung)
    assert einrichtung is not None and einrichtung.absender == "no-reply@aquaticy.example.org"
    assert einrichtung.direkt is False
    umgebung["AQUATICY_MAIL_FROM"] = "hallo@aquaticy.example.org"
    einrichtung = mailversand.aus_umgebung(umgebung)
    assert einrichtung is not None and einrichtung.absender == "hallo@aquaticy.example.org"
    umgebung["AQUATICY_MAIL_FROM"] = "x@y.de\r\nBcc: alle@example.org"
    assert mailversand.aus_umgebung(umgebung) is None


@pytest.mark.parametrize("an, betreff", [
    ("jonas@example.org\r\nBcc: alle@example.org", "Code"),
    ("jonas@example.org", "Code\r\nBcc: alle@example.org"),
    ("kein-at-zeichen", "Code"),
])
def test_line_breaks_in_headers_are_refused(an: str, betreff: str) -> None:
    with pytest.raises(mailversand.MailFehler):
        mailversand.nachricht(EINRICHTUNG, an, betreff, "Text")


def test_the_mails_escape_names_and_never_name_google() -> None:
    betreff, text, html = mail_code(ANMELDEN, "<script>x</script>", "jonas@example.org",
                                    "123456", "aquaticy-test.vercel.app")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "123456" in text and "123456" in html
    assert "https://aquaticy-test.vercel.app" in text and "10 Minuten" in text
    for teil in (betreff, text, html):
        assert "google" not in teil.lower()
    betreff, text, _ = mail_warnung("Jonas", "jonas@example.org", 1_800_000_000.0,
                                    "Chrome auf Linux", "", "de")
    assert betreff == "Sicherheitswarnung für dein Aquaticy-Konto"
    assert "falscher Bestätigungscode" in text and "Chrome auf Linux" in text
    assert "Uhr (" in text
    assert "Security alert" in mail_warnung("Jonas", "j@x.de", 1.0, "", "", "en")[0]


def test_addresses_are_masked() -> None:
    assert maskiert("jonas@example.org") == "jo•••@example.org"
    assert maskiert("abc@example.org") == "a•••@example.org"
    assert maskiert("") == "•••"


# -- Echtes smtplib gegen einen Nachbau auf 127.0.0.1 ---------------------------------------

def _zertifikat(ordner: Path) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    schluessel = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    jetzt = datetime.datetime.now(datetime.UTC)
    zert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(schluessel.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(jetzt - datetime.timedelta(minutes=5))
            .not_valid_after(jetzt + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]),
                           critical=False)
            .sign(schluessel, hashes.SHA256()))
    zert_pfad, schluessel_pfad = ordner / "zert.pem", ordner / "schluessel.pem"
    zert_pfad.write_bytes(zert.public_bytes(serialization.Encoding.PEM))
    schluessel_pfad.write_bytes(schluessel.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    return zert_pfad, schluessel_pfad


class SmtpNachbau(threading.Thread):
    """Ein SMTP-Dienst fuer genau eine Verbindung: TLS (direkt oder STARTTLS), AUTH PLAIN."""

    def __init__(self, zert: Path, schluessel: Path, *, direkt: bool = False,
                 starttls: bool = True) -> None:
        super().__init__(daemon=True)
        self.lauscher = socket.create_server(("127.0.0.1", 0))
        self.port = self.lauscher.getsockname()[1]
        self.kontext = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.kontext.load_cert_chain(zert, schluessel)
        self.direkt, self.starttls = direkt, starttls
        self.anmeldungen: list[bool] = []
        self.mails: list[str] = []

    def run(self) -> None:
        self.lauscher.settimeout(10)
        try:
            verbindung, _ = self.lauscher.accept()
        except OSError:
            return
        with contextlib.suppress(Exception):
            self._bedienen(verbindung)
        with contextlib.suppress(Exception):
            verbindung.close()
        self.lauscher.close()

    def _bedienen(self, verbindung: socket.socket) -> None:
        tls = self.direkt
        if tls:
            verbindung = self.kontext.wrap_socket(verbindung, server_side=True)
        datei = verbindung.makefile("rwb")

        def sag(zeile: str) -> None:
            datei.write(zeile.encode() + b"\r\n")
            datei.flush()

        sag("220 nachbau ESMTP")
        while True:
            zeile = datei.readline().decode("utf-8", "replace").rstrip("\r\n")
            if not zeile:
                return
            befehl = zeile.split(" ", 1)[0].upper()
            if befehl in ("EHLO", "HELO"):
                angebot = ["nachbau"] + (["STARTTLS"] if self.starttls and not tls else [])
                angebot += ["AUTH PLAIN"] if tls else []
                for i, eintrag in enumerate(angebot):
                    sag(("250 " if i == len(angebot) - 1 else "250-") + eintrag)
            elif befehl == "STARTTLS":
                sag("220 los")
                datei.close()
                verbindung = self.kontext.wrap_socket(verbindung, server_side=True)
                datei = verbindung.makefile("rwb")
                tls = True
            elif befehl == "AUTH":
                teile = zeile.split()
                roh = base64.b64decode(teile[2]).split(b"\0") if len(teile) == 3 else []
                richtig = roh[1:] == [POSTFACH_ADRESSE.encode(), b"nur-zum-testen"]
                self.anmeldungen.append(richtig)
                sag("235 ok" if richtig else "535 nein")
            elif befehl in ("MAIL", "RCPT", "RSET", "NOOP"):
                sag("250 ok")
            elif befehl == "DATA":
                sag("354 los")
                teile_der_mail = []
                while (stueck := datei.readline()) not in (b".\r\n", b""):
                    teile_der_mail.append(stueck.decode("utf-8", "replace"))
                self.mails.append("".join(teile_der_mail))
                sag("250 angenommen")
            elif befehl == "QUIT":
                sag("221 tschuess")
                return
            else:
                sag("502 unbekannt")


@pytest.fixture
def tls(tmp_path: Path) -> tuple[Path, Path, ssl.SSLContext]:
    zert, schluessel = _zertifikat(tmp_path)
    kontext = ssl.create_default_context(cafile=str(zert))
    kontext.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
    return zert, schluessel, kontext


def _einrichtung(port: int, *, direkt: bool, passwort: str = "nur-zum-testen") -> Any:
    return mailversand.Einrichtung("localhost", port, POSTFACH_ADRESSE, passwort,
                                   POSTFACH_ADRESSE, "aquaticy-test.vercel.app", direkt=direkt)


@pytest.mark.parametrize("direkt", [False, True])
def test_smtplib_sends_only_over_tls(tls: Any, direkt: bool) -> None:
    zert, schluessel, kontext = tls
    dienst = SmtpNachbau(zert, schluessel, direkt=direkt)
    dienst.start()
    betreff, text, html = mail_code(ANMELDEN, "Jonas", "jonas@example.org", "123456",
                                    "aquaticy-test.vercel.app")
    mailversand.senden(_einrichtung(dienst.port, direkt=direkt), "jonas@example.org", betreff,
                       text, html, kontext=kontext)
    dienst.join(5)
    assert dienst.anmeldungen == [True]
    assert len(dienst.mails) == 1
    assert 'From: "Aquaticy (aquaticy-test.vercel.app)" <aquaticy@example.org>' in \
        dienst.mails[0]
    assert "123456" in dienst.mails[0]


def test_without_starttls_the_password_never_goes_out(tls: Any) -> None:
    zert, schluessel, kontext = tls
    dienst = SmtpNachbau(zert, schluessel, starttls=False)
    dienst.start()
    with pytest.raises(mailversand.MailFehler, match="keine Verschlüsselung"):
        mailversand.senden(_einrichtung(dienst.port, direkt=False), "jonas@example.org",
                           "Betreff", "Text", kontext=kontext)
    dienst.join(5)
    assert dienst.anmeldungen == [] and dienst.mails == []


def test_a_wrong_smtp_password_is_reported_without_the_password(tls: Any) -> None:
    zert, schluessel, kontext = tls
    dienst = SmtpNachbau(zert, schluessel, direkt=True)
    dienst.start()
    with pytest.raises(mailversand.MailFehler) as fehler:
        mailversand.senden(_einrichtung(dienst.port, direkt=True, passwort="falsch-falsch"),
                           "jonas@example.org", "Betreff", "Text", kontext=kontext)
    dienst.join(5)
    assert "lehnt die Anmeldung ab" in str(fehler.value)
    assert "falsch-falsch" not in str(fehler.value)


# -- Der Ablauf -----------------------------------------------------------------------------

def test_it_is_off_until_switched_on(zf: ZweiFaktor, auth: AuthStore) -> None:
    assert zf.noetig(konto(auth)) is False
    assert zf.zustand(konto(auth)) == {"an": False, "moeglich": True, "grund": "",
                                        "email": "jo•••@example.org", "abgeschaltet": False}


def test_the_right_code_signs_in_once(zf: ZweiFaktor, auth: AuthStore,
                                      postfach: Postfach) -> None:
    antwort = zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    assert antwort["an"] == "jo•••@example.org"
    assert postfach.mails[-1]["an"] == "jonas@example.org"
    assert postfach.mails[-1]["betreff"] == "Dein Aquaticy-Bestätigungscode"
    code = postfach.code()
    rohdaten = Path(auth.db_path).read_bytes()
    with sqlite3.connect(auth.db_path) as conn:
        zeilen = conn.execute("SELECT kennung, code_hash FROM zf_codes").fetchall()
    assert zeilen and all(code not in wert for zeile in zeilen for wert in zeile)
    assert antwort["challenge"].encode() not in rohdaten
    assert zf.pruefen(antwort["challenge"], code, ANMELDEN, GERAET, KEKS).id == konto(auth).id
    with pytest.raises(ZweiFaktorFehler) as fehler:
        zf.pruefen(antwort["challenge"], code, ANMELDEN, GERAET, KEKS)
    assert fehler.value.neu_anmelden


def test_a_wrong_code_warns_once_and_five_end_it(zf: ZweiFaktor, auth: AuthStore,
                                                  postfach: Postfach) -> None:
    antwort = zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    code = postfach.code()
    falsch = "000000" if code != "000000" else "111111"
    with pytest.raises(ZweiFaktorFehler, match="Du hast noch 4 Versuche"):
        zf.pruefen(antwort["challenge"], falsch, ANMELDEN, GERAET, KEKS, geraet="Chrome auf Linux")
    assert postfach.mails[-1]["betreff"] == "Sicherheitswarnung für dein Aquaticy-Konto"
    assert "Chrome auf Linux" in postfach.mails[-1]["text"]
    for rest in ("3 Versuche", "2 Versuche", "einen Versuch"):
        with pytest.raises(ZweiFaktorFehler, match=rest):
            zf.pruefen(antwort["challenge"], falsch, ANMELDEN, GERAET, KEKS)
    # Hoechstens eine Warnung in zehn Minuten -- sonst flutet ein Angreifer das Postfach.
    assert sum(m["betreff"].startswith("Sicherheitswarnung") for m in postfach.mails) == 1
    with pytest.raises(ZweiFaktorFehler) as fehler:
        zf.pruefen(antwort["challenge"], falsch, ANMELDEN, GERAET, KEKS)
    assert fehler.value.neu_anmelden
    with pytest.raises(ZweiFaktorFehler):
        zf.pruefen(antwort["challenge"], code, ANMELDEN, GERAET, KEKS)


def test_a_code_expires_after_ten_minutes(zf: ZweiFaktor, auth: AuthStore, postfach: Postfach,
                                          uhr: Uhr) -> None:
    antwort = zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    uhr.t += 601
    with pytest.raises(ZweiFaktorFehler, match="abgelaufen"):
        zf.pruefen(antwort["challenge"], postfach.code(), ANMELDEN, GERAET, KEKS)


@pytest.mark.parametrize("anderes", [(GERAET, "fremder-keks"), ("Firefox\x1fen", KEKS)])
def test_a_code_works_only_in_the_same_browser(zf: ZweiFaktor, auth: AuthStore,
                                                postfach: Postfach, anderes: tuple) -> None:
    antwort = zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    with pytest.raises(ZweiFaktorFehler):
        zf.pruefen(antwort["challenge"], postfach.code(), ANMELDEN, *anderes)
    # Danach gilt die Anmeldung auch im richtigen Browser nicht mehr.
    with pytest.raises(ZweiFaktorFehler):
        zf.pruefen(antwort["challenge"], postfach.code(), ANMELDEN, GERAET, KEKS)


def test_a_new_password_ends_a_pending_sign_in(zf: ZweiFaktor, auth: AuthStore,
                                                postfach: Postfach) -> None:
    antwort = zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    auth.change_password(konto(auth), PASSWORT, "ein neues langes Passwort")
    with pytest.raises(ZweiFaktorFehler):
        zf.pruefen(antwort["challenge"], postfach.code(), ANMELDEN, GERAET, KEKS)


def test_codes_are_rationed(zf: ZweiFaktor, auth: AuthStore, uhr: Uhr) -> None:
    for _ in range(5):
        zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
        uhr.t += 10
    with pytest.raises(ZweiFaktorFehler) as fehler:
        zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    assert fehler.value.status == 429
    for _ in range(15):
        uhr.t += 16 * 60
        zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    with pytest.raises(ZweiFaktorFehler):  # 20 am Tag
        zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)


def test_a_new_code_replaces_the_old_and_attempts_add_up(zf: ZweiFaktor, auth: AuthStore,
                                                         postfach: Postfach, uhr: Uhr) -> None:
    antwort = zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    alt = postfach.code()
    with pytest.raises(ZweiFaktorFehler, match="Sekunden"):
        zf.neu_senden(antwort["challenge"], GERAET, KEKS)
    falsch = "000000" if alt != "000000" else "111111"
    for _ in range(MAX_VERSUCHE - 1):
        with pytest.raises(ZweiFaktorFehler):
            zf.pruefen(antwort["challenge"], falsch, ANMELDEN, GERAET, KEKS)
    uhr.t += 61
    zf.neu_senden(antwort["challenge"], GERAET, KEKS)
    neu = postfach.code()
    if neu != alt:
        with pytest.raises(ZweiFaktorFehler):
            zf.pruefen(antwort["challenge"], alt, ANMELDEN, GERAET, KEKS)
    else:
        assert zf.pruefen(antwort["challenge"], neu, ANMELDEN, GERAET, KEKS)


def test_switching_on_needs_a_code_and_off_the_password(zf: ZweiFaktor, auth: AuthStore,
                                                        postfach: Postfach) -> None:
    antwort = zf.beginnen(konto(auth), EINSCHALTEN, GERAET, KEKS)
    assert postfach.mails[-1]["betreff"] == "Bestätige deine E-Mail-Adresse für Aquaticy"
    with pytest.raises(ZweiFaktorFehler):  # ein Code zum Einschalten meldet nicht an
        zf.pruefen(antwort["challenge"], postfach.code(), ANMELDEN, GERAET, KEKS)
    antwort = zf.beginnen(konto(auth), EINSCHALTEN, GERAET, KEKS)
    zf.einschalten(konto(auth), antwort["challenge"], postfach.code(), GERAET, KEKS)
    assert zf.ist_an(konto(auth).id) and zf.noetig(konto(auth))
    assert postfach.mails[-1]["betreff"] == "Die Bestätigung in zwei Schritten ist jetzt an"
    assert zf.ausschalten(konto(auth), "falsches Passwort") is False
    assert zf.ist_an(konto(auth).id)
    assert zf.ausschalten(konto(auth), PASSWORT) is True
    assert not zf.ist_an(konto(auth).id)
    assert postfach.mails[-1]["betreff"] == "Die Bestätigung in zwei Schritten ist jetzt aus"


def test_no_silent_skip_when_mail_is_gone(auth: AuthStore, uhr: Uhr) -> None:
    ohne = ZweiFaktor(auth, SqliteAblage(auth.db_path), umgebung={}, uhr=uhr)
    ohne.ablage.setzen(konto(auth).id, True, uhr())
    assert ohne.noetig(konto(auth)) is True
    with pytest.raises(ZweiFaktorFehler, match="AQUATICY_2FA_AUS=1") as fehler:
        ohne.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    assert fehler.value.status == 424
    notfall = ZweiFaktor(auth, SqliteAblage(auth.db_path), umgebung={"AQUATICY_2FA_AUS": "1"})
    assert notfall.noetig(konto(auth)) is False
    assert ohne.zustand(konto(auth))["moeglich"] is True  # ausschalten geht weiter


def test_a_failed_mail_leaves_no_usable_code(zf: ZweiFaktor, auth: AuthStore,
                                             postfach: Postfach) -> None:
    postfach.kaputt = True
    with pytest.raises(ZweiFaktorFehler) as fehler:
        zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    assert fehler.value.status == 424
    with sqlite3.connect(auth.db_path) as conn:
        assert conn.execute("SELECT count(*) FROM zf_codes").fetchone()[0] == 0


def test_an_internal_address_cannot_switch_it_on(tmp_path: Path, uhr: Uhr) -> None:
    store = AuthStore(tmp_path / "eins", "PRO234567", single=True)
    store.register("", PASSWORT, "ultra", username="Eins", trusted=True)
    eins = store.owner()
    assert eins is not None
    zf = ZweiFaktor(store, SqliteAblage(store.db_path), mail=EINRICHTUNG, umgebung={}, uhr=uhr,
                    senden=Postfach())
    assert zf.zustand(eins)["moeglich"] is False
    with pytest.raises(ZweiFaktorFehler, match="keine E-Mail-Adresse"):
        zf.beginnen(eins, EINSCHALTEN, GERAET, KEKS)


def test_parallel_guesses_never_exceed_the_limit(zf: ZweiFaktor, auth: AuthStore,
                                                 postfach: Postfach) -> None:
    antwort = zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    falsch = "000000" if postfach.code() != "000000" else "111111"
    gezaehlt: list[int] = []
    zweite = SqliteAblage(auth.db_path)

    def raten() -> None:
        for ablage in (zf.ablage, zweite):
            kennung = zf._hash("kennung", antwort["challenge"])
            versuch = ablage.versuch(kennung, zf.uhr())
            if versuch is not None:
                gezaehlt.append(versuch.versuche)

    faeden = [threading.Thread(target=raten) for _ in range(10)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join()
    assert sorted(gezaehlt) == list(range(1, MAX_VERSUCHE + 1))
    with pytest.raises(ZweiFaktorFehler):
        zf.pruefen(antwort["challenge"], falsch, ANMELDEN, GERAET, KEKS)


# -- Ueber den echten Server ----------------------------------------------------------------

@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, postfach: Postfach):
    monkeypatch.setattr(web, "AUTH", AuthStore(tmp_path / "accounts", "PRO234567"))
    monkeypatch.setattr(web, "SESSIONS", web.SessionRegistry())
    monkeypatch.setattr(web, "SESSION", web.SessionProxy())
    monkeypatch.setattr(web, "strong_models", lambda *args, **kwargs: [])
    monkeypatch.setattr(web, "AUTH_LIMIT", web.RateLimiter(attempts=100, window_seconds=60))
    monkeypatch.setattr(web, "ZWEI_FAKTOR", ZweiFaktor(
        web.AUTH, SqliteAblage(web.AUTH.db_path), mail=EINRICHTUNG, umgebung={},
        senden=postfach))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    faden = threading.Thread(target=httpd.serve_forever, daemon=True)
    faden.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


class Browser:
    def __init__(self, port: int) -> None:
        self.port = port
        self.kekse: dict[str, str] = {}

    def __call__(self, methode: str, pfad: str, body: Any = None) -> tuple[int, dict[str, Any]]:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        kopf = {"Content-Type": "application/json", "User-Agent": AGENT,
                "Accept-Language": SPRACHE, **FETCH}
        if self.kekse:
            kopf["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.kekse.items())
        conn.request(methode, pfad, body=None if body is None else json.dumps(body),
                     headers=kopf)
        antwort = conn.getresponse()
        roh = antwort.read()
        for name, wert in antwort.getheaders():
            if name.lower() == "set-cookie":
                schluessel, _, rest = wert.partition("=")
                if "Max-Age=0;" in wert:
                    self.kekse.pop(schluessel, None)
                else:
                    self.kekse[schluessel] = rest.split(";", 1)[0]
        conn.close()
        return antwort.status, (json.loads(roh) if roh else {})


def _angemeldet(port: int) -> tuple[Browser, str]:
    browser = Browser(port)
    browser("POST", "/api/consent", {"accepted": True})
    email = f"t{os.urandom(3).hex()}@example.org"
    status, daten = browser("POST", "/api/auth/register", {
        "email": email, "username": f"T{os.urandom(3).hex()}", "password": PASSWORT,
        "plan": "normal", "terms_accepted": True})
    assert status == 200, daten
    return browser, email


def _anmelden(browser: Browser, email: str) -> tuple[int, dict[str, Any]]:
    browser("POST", "/api/auth/logout", {})
    return browser("POST", "/api/auth/login", wie_die_app(
        {"email": email, "password": PASSWORT, "lang": "de"}))


def test_without_the_second_step_sign_in_stays_as_before(server: int) -> None:
    browser, email = _angemeldet(server)
    status, daten = _anmelden(browser, email)
    assert status == 200 and daten["ok"] is True and "zwei_faktor" not in daten
    assert web.AUTH_COOKIE in browser.kekse


def test_sign_in_with_the_code_from_the_mail(server: int, postfach: Postfach) -> None:
    browser, email = _angemeldet(server)
    account = web.AUTH.authenticate(email, PASSWORT)
    web.ZWEI_FAKTOR.ablage.setzen(account.id, True, 1.0)
    status, daten = _anmelden(browser, email)
    assert status == 200 and daten["ok"] is False and daten["zwei_faktor"] is True
    assert web.AUTH_COOKIE not in browser.kekse
    assert browser("GET", "/api/account")[0] == 401
    code = postfach.code()
    falsch = "000000" if code != "000000" else "111111"
    status, daten = browser("POST", "/api/auth/code",
                            {"challenge": daten["challenge"], "code": falsch, "lang": "de"})
    assert status == 401 and daten["error"] == "Der Code stimmt nicht. Du hast noch 4 Versuche."
    assert postfach.mails[-1]["betreff"] == "Sicherheitswarnung für dein Aquaticy-Konto"
    assert web.AUTH_COOKIE not in browser.kekse
    challenge = _anmelden(browser, email)[1]["challenge"]
    status, daten = browser("POST", "/api/auth/code",
                            {"challenge": challenge, "code": postfach.code()})
    assert status == 200 and daten["ok"] is True
    assert browser("GET", "/api/account")[0] == 200


def test_the_settings_switch_it_on_and_off(server: int, postfach: Postfach) -> None:
    browser, _ = _angemeldet(server)
    status, daten = browser("GET", "/api/account/security")
    assert status == 200 and daten["zwei_faktor"]["an"] is False
    status, daten = browser("POST", "/api/account/2fa", {"action": "start"})
    assert status == 200 and daten["challenge"]
    status, daten = browser("POST", "/api/account/2fa", {
        "action": "bestaetigen", "challenge": daten["challenge"], "code": postfach.code()})
    assert status == 200 and daten["zustand"]["an"] is True
    status, daten = browser("POST", "/api/account/2fa", {"action": "aus",
                                                          "password": "falsches Passwort"})
    assert status == 403
    status, daten = browser("POST", "/api/account/2fa", {"action": "aus", "password": PASSWORT})
    assert status == 200 and daten["zustand"]["an"] is False


def test_a_failed_mail_reaches_the_user_and_gives_no_session(server: int,
                                                             postfach: Postfach) -> None:
    browser, email = _angemeldet(server)
    web.ZWEI_FAKTOR.ablage.setzen(web.AUTH.authenticate(email, PASSWORT).id, True, 1.0)
    postfach.kaputt = True
    status, daten = _anmelden(browser, email)
    # Nicht 503: ab 500 ersetzt der Server jede Meldung durch einen allgemeinen Satz.
    assert status == 424
    assert daten["error"] == ("Die E-Mail mit dem Code ließ sich gerade nicht verschicken. "
                              "Versuch es gleich noch einmal.")
    assert web.AUTH_COOKIE not in browser.kekse


def test_a_database_outage_gives_no_session(server: int, postfach: Postfach,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    browser, email = _angemeldet(server)
    account = web.AUTH.authenticate(email, PASSWORT)
    kopie = SqliteAblage(web.AUTH.db_path)
    kopie.setzen(account.id, True, 1.0)

    class Weg:
        def __getattr__(self, name: str) -> Any:
            def kaputt(*_: Any, **__: Any) -> Any:
                raise RuntimeError("Postgres antwortet nicht")
            return kaputt

    monkeypatch.setattr(web, "ZWEI_FAKTOR", ZweiFaktor(
        web.AUTH, Weg(), kopie=kopie, mail=EINRICHTUNG, umgebung={}, senden=postfach))
    status, daten = _anmelden(browser, email)
    assert status == 424
    assert daten["error"] == "Die Anmeldung geht gerade nicht. Versuch es gleich noch einmal."
    assert web.AUTH_COOKIE not in browser.kekse


def test_the_code_route_needs_the_device_cookie(server: int) -> None:
    status, daten = Browser(server)("POST", "/api/auth/code", {"challenge": "x", "code": "1"})
    assert status == 401 and daten["neu_anmelden"] is True


def test_a_foreign_origin_cannot_send_a_code(server: int) -> None:
    conn = HTTPConnection("127.0.0.1", server, timeout=10)
    conn.request("POST", "/api/auth/code", body=json.dumps({"challenge": "x", "code": "1"}),
                 headers={"Content-Type": "application/json", "Origin": "https://evil.example",
                          "Host": f"127.0.0.1:{server}"})
    antwort = conn.getresponse()
    antwort.read()
    conn.close()
    assert antwort.status == 403


# -- Gegen echtes Postgres ------------------------------------------------------------------

POSTGRES = os.environ.get("AQUATICY_TEST_POSTGRES", "").strip()


@pytest.mark.skipif(not POSTGRES, reason="AQUATICY_TEST_POSTGRES ist nicht gesetzt")
def test_two_instances_share_one_counter_in_postgres(auth: AuthStore, postfach: Postfach,
                                                     uhr: Uhr) -> None:
    import psycopg

    from aquaticy import vercel_verbund
    from aquaticy.zweifaktor import PostgresAblage

    with psycopg.connect(POSTGRES + "eins", autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS aquaticy.zf_codes, aquaticy.zf_konten, "
                     "aquaticy.zf_mails, aquaticy.zf_warnungen")
    eins = ZweiFaktor(auth, PostgresAblage(vercel_verbund.Datenbank("eins", POSTGRES + "eins")),
                      mail=EINRICHTUNG, umgebung={}, uhr=uhr, senden=postfach)
    zwei = ZweiFaktor(auth, PostgresAblage(vercel_verbund.Datenbank("zwei", POSTGRES + "eins")),
                      mail=EINRICHTUNG, umgebung={}, uhr=uhr, senden=postfach)
    antwort = eins.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    code = postfach.code()
    falsch = "000000" if code != "000000" else "111111"
    kennung = eins._hash("kennung", antwort["challenge"])
    gezaehlt: list[int] = []

    def raten(instanz: ZweiFaktor) -> None:
        versuch = instanz.ablage.versuch(kennung, uhr())
        if versuch is not None:
            gezaehlt.append(versuch.versuche)

    faeden = [threading.Thread(target=raten, args=(i,)) for i in (eins, zwei) * 6]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join()
    assert sorted(gezaehlt) == list(range(1, MAX_VERSUCHE + 1))
    with pytest.raises(ZweiFaktorFehler):
        zwei.pruefen(antwort["challenge"], falsch, ANMELDEN, GERAET, KEKS)
    # Ein richtiger Code wird nur einmal verbraucht, auch ueber zwei Instanzen.
    antwort = zwei.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    code = postfach.code()
    assert eins.pruefen(antwort["challenge"], code, ANMELDEN, GERAET, KEKS)
    with pytest.raises(ZweiFaktorFehler):
        zwei.pruefen(antwort["challenge"], code, ANMELDEN, GERAET, KEKS)
    eins.ablage.setzen(konto(auth).id, True, uhr())
    assert zwei.ist_an(konto(auth).id) is True


# -- Fehlersuche 16.5.7: Aquaticy Standard auf Englisch --------------------------------------

JETZT_STANDARD = datetime.datetime(2026, 11, 22, 15, 10, tzinfo=ZoneInfo("Europe/Berlin"))


def frag_standard(frage: str, holen: Any = None) -> str:
    return standard._antwort(frage, [], holen=holen or (lambda url: None), jetzt=JETZT_STANDARD)


@pytest.mark.parametrize("frage, erwartet", [
    ("What day is tomorrow?", "Tomorrow is **Monday, 23 November 2026**."),
    ("Which day is tomorrow?", "Tomorrow is **Monday, 23 November 2026**."),
    ("What day was yesterday?", "Yesterday was **Saturday, 21 November 2026**."),
    ("What day of the week is it?", "Today is **Sunday, 22 November 2026**."),
    ("What day is the day after tomorrow?",
     "The day after tomorrow is **Tuesday, 24 November 2026**."),
    ("What is tomorrow's date?", "Tomorrow is **Monday, 23 November 2026**."),
    ("How many days in 2028?", "2028 has **366 days**."),
    ("How many days does 2027 have?", "2027 has **365 days**."),
])
def test_english_day_questions_get_an_answer(frage: str, erwartet: str) -> None:
    # Vorher "Sorry, I can't answer that" -- auf Deutsch ging es.
    assert frag_standard(frage) == erwartet


def test_english_answers_that_worked_stay_the_same() -> None:
    assert frag_standard("What day is it?") == "Today is 2026-11-22."
    assert frag_standard("How many days are in February 2028?") == "February 2028 has **29 days**."
    assert frag_standard("What year is it?") == "It is **2026**."


@pytest.mark.parametrize("frage", ["What day will it rain in Berlin?",
                                   "Which day will it rain in Berlin?"])
def test_an_english_weather_question_finds_the_place(frage: str) -> None:
    # Vorher suchte Aquaticy den Ort "day Berlin".
    gefragt: list[str] = []

    def holen(url: str) -> None:
        gefragt.append(url)

    frag_standard(frage, holen)
    orte = [u.split("name=")[1].split("&")[0] for u in gefragt if "name=" in u]
    assert orte == ["Berlin"]
