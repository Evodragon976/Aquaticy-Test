"""E-Mails verschicken: Codes und Warnungen der Bestaetigung in zwei Schritten (16.5.7).

Aquaticy schickt Mails ueber einen SMTP-Dienst, den der Betreiber in der Umgebung eintraegt --
nur verschluesselt (Port 465 mit TLS, sonst STARTTLS; ohne Verschluesselung bricht es ab).

Warum nicht einfach "no-reply@aquaticy-test.vercel.app"? Die Domain gehoert Vercel. Niemand
ausser Vercel kann fuer sie die DNS-Eintraege (SPF, DKIM) setzen, ohne die Gmail, Outlook und
Co. Mails heute abweisen oder als Spam einsortieren. Kein Mail-Dienst verschickt darum Mails
mit einer vercel.app-Adresse als Absender. So geht es trotzdem ueber die vercel.app-Seite:

* Die Mails tragen als Namen "Aquaticy (aquaticy-test.vercel.app)" und verlinken dorthin.
* Absenderadresse ist das Postfach des SMTP-Dienstes (``AQUATICY_SMTP_USER``), zum Beispiel
  ein Gmail-Konto mit App-Passwort.
* Hat das Projekt eine eigene Domain, nimmt Aquaticy ``no-reply@<domain>`` -- das geht, sobald
  der Mail-Dienst die Domain bestaetigt hat.

Umgebung: ``AQUATICY_SMTP_HOST``, ``AQUATICY_SMTP_PORT`` (465), ``AQUATICY_SMTP_USER``,
``AQUATICY_SMTP_PASSWORD``, optional ``AQUATICY_MAIL_FROM`` (Absender) und
``AQUATICY_WEBSITE`` (Adresse der Seite; sonst ``VERCEL_PROJECT_PRODUCTION_URL``).
Zugangsdaten stehen nie in einer Meldung.
"""

from __future__ import annotations

import os
import re
import smtplib
import ssl
from collections.abc import Mapping
from dataclasses import dataclass, field
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

PORT = 465
FRIST = 15.0
#: Die Seite in einer vercel.app-Domain: als Name in der Mail, nicht als Absenderadresse.
VERCEL_DOMAIN = re.compile(r"(?:^|\.)vercel\.app$", re.I)
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_ADRESSE = re.compile(r"^[^@\s<>\"',;:\\]{1,64}@[^@\s<>\"',;:\\]{1,253}$")


class MailFehler(RuntimeError):
    """Eine Mail ging nicht raus -- ohne Zugangsdaten in der Meldung."""


@dataclass(frozen=True, slots=True)
class Einrichtung:
    host: str
    port: int
    benutzer: str
    passwort: str = field(repr=False)
    absender: str
    website: str = ""
    #: TLS von Anfang an (Port 465). Sonst STARTTLS -- ohne geht nichts raus.
    direkt: bool = False

    @property
    def name(self) -> str:
        """Der Name in der Mail: "Aquaticy" und die Adresse der Seite."""
        return f"Aquaticy ({self.website})" if self.website else "Aquaticy"


def _ohne_steuerzeichen(wert: str) -> bool:
    return not any(ord(z) < 32 or ord(z) == 127 for z in wert)


def website_aus(umgebung: Mapping[str, str]) -> str:
    """Die Adresse der Seite (ohne https://) -- eigene Angabe, sonst die von Vercel."""
    roh = str(umgebung.get("AQUATICY_WEBSITE") or umgebung.get("VERCEL_PROJECT_PRODUCTION_URL")
              or "").strip().lower()
    roh = re.sub(r"^https?://", "", roh).split("/", 1)[0].split(":", 1)[0].rstrip(".")
    return roh if _DOMAIN.fullmatch(roh) else ""


def absender_fuer(website: str, benutzer: str, eigener: str = "") -> str:
    """Wer als Absender in der Mail steht -- oder "" (dann geht es nicht).

    Eine vercel.app-Domain taugt nicht als Absender (siehe oben): Dann ist es das Postfach
    des SMTP-Dienstes. Eine eigene Domain wird zu ``no-reply@<domain>``.
    """
    eigener = eigener.strip()
    if eigener:
        return eigener if _ADRESSE.fullmatch(eigener) and _ohne_steuerzeichen(eigener) else ""
    if website and not VERCEL_DOMAIN.search(website):
        return f"no-reply@{website}"
    benutzer = benutzer.strip()
    return benutzer if _ADRESSE.fullmatch(benutzer) and _ohne_steuerzeichen(benutzer) else ""


def aus_umgebung(umgebung: Mapping[str, str] | None = None) -> Einrichtung | None:
    """Die Einrichtung aus der Umgebung -- None, wenn kein Versand eingerichtet ist."""
    umgebung = os.environ if umgebung is None else umgebung
    host = str(umgebung.get("AQUATICY_SMTP_HOST") or "").strip().lower()
    benutzer = str(umgebung.get("AQUATICY_SMTP_USER") or "").strip()
    passwort = str(umgebung.get("AQUATICY_SMTP_PASSWORD") or "")
    if not host or not benutzer or not passwort or not _DOMAIN.fullmatch(host):
        return None
    try:
        port = int(str(umgebung.get("AQUATICY_SMTP_PORT") or PORT).strip())
    except ValueError:
        return None
    if not 0 < port < 65536 or port == 25:
        # Port 25 ist unverschluesselt und in Rechenzentren meist gesperrt.
        return None
    website = website_aus(umgebung)
    absender = absender_fuer(website, benutzer, str(umgebung.get("AQUATICY_MAIL_FROM") or ""))
    if not absender:
        return None
    return Einrichtung(host, port, benutzer, passwort, absender, website, direkt=port == 465)


def nachricht(einrichtung: Einrichtung, an: str, betreff: str, text: str,
              html: str = "") -> EmailMessage:
    """Baut die Mail. Raises: MailFehler bei ungueltiger Adresse oder Zeilenumbruch im Kopf."""
    an = (an or "").strip()
    if not _ADRESSE.fullmatch(an) or not _ohne_steuerzeichen(an):
        raise MailFehler("Die E-Mail-Adresse ist ungültig.")
    if not _ohne_steuerzeichen(betreff):
        raise MailFehler("Der Betreff ist ungültig.")
    lokal, _, domain = einrichtung.absender.partition("@")
    mail = EmailMessage()
    mail["From"] = Address(einrichtung.name, lokal, domain)
    mail["To"] = an
    mail["Subject"] = betreff
    mail["Date"] = formatdate(localtime=False)
    mail["Message-ID"] = make_msgid(domain=domain or None)
    mail["Auto-Submitted"] = "auto-generated"
    mail.set_content(text)
    if html:
        mail.add_alternative(html, subtype="html")
    return mail


def senden(einrichtung: Einrichtung, an: str, betreff: str, text: str, html: str = "", *,
           kontext: ssl.SSLContext | None = None) -> None:
    """Schickt eine Mail -- nur verschluesselt.

    Raises:
        MailFehler: Adresse ungueltig, Dienst nicht erreichbar, Anmeldung abgelehnt, kein TLS.
    """
    mail = nachricht(einrichtung, an, betreff, text, html)
    kontext = kontext or ssl.create_default_context()
    try:
        if einrichtung.direkt:
            verbindung: smtplib.SMTP = smtplib.SMTP_SSL(
                einrichtung.host, einrichtung.port, timeout=FRIST, context=kontext)
        else:
            verbindung = smtplib.SMTP(einrichtung.host, einrichtung.port, timeout=FRIST)
        with verbindung:
            verbindung.ehlo()
            if not einrichtung.direkt:
                if not verbindung.has_extn("starttls"):
                    raise MailFehler("Der Mail-Dienst bietet keine Verschlüsselung an.")
                verbindung.starttls(context=kontext)
                verbindung.ehlo()
            verbindung.login(einrichtung.benutzer, einrichtung.passwort)
            verbindung.send_message(mail)
    except MailFehler:
        raise
    except smtplib.SMTPAuthenticationError:
        raise MailFehler("Der Mail-Dienst lehnt die Anmeldung ab.") from None
    except smtplib.SMTPRecipientsRefused:
        raise MailFehler("Der Mail-Dienst nimmt diese Adresse nicht an.") from None
    except (smtplib.SMTPException, OSError) as fehler:
        raise MailFehler(
            f"Der Mail-Dienst ist nicht erreichbar ({type(fehler).__name__}).") from None
