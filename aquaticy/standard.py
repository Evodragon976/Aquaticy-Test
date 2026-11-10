"""Aquaticy Standard: antwortet ohne Sprachmodell (16.0.0, Aquaticy-Test).

Wer noch keinen API-Schluessel hat, bekommt trotzdem Antworten -- aus festen Regeln und
freien, oeffentlichen Quellen. Die Idee stammt aus dem Antwortsystem des Cloudflare-Workers
(worker/src/antworten.js); hier ist sie in Python, fuer die ganze App, und verbessert:

* **Rechnen** ueber den sicheren Rechner (aquaticy/calc.py, AST mit Positivliste), dazu
  Prozente und Mehrwertsteuer ("200 plus 19 %", "119 € brutto in netto").
* **Einheiten**: Laenge, Gewicht, Volumen, Flaeche, Tempo, Zeit, Daten und Temperatur.
* **Datum und Uhrzeit** in deutscher Zeit (aquaticy/zeit.py), Tage bis Weihnachten, Silvester,
  Ostern oder einem Datum, der Wochentag eines Datums, Kalenderwoche.
* **Wetter** (Open-Meteo), **Wechselkurse** (EZB ueber Frankfurter), **Nachrichten**
  (Tagesschau) und **Wissen** (Wikipedia-Zusammenfassung) -- jeweils mit Quelle.
* **Gespraechsspeicher**: "Fuer welchen Ort?" -> "Erkelenz" reicht; der zuletzt genannte Ort
  gilt weiter ("und morgen?", "was soll ich anziehen?").
* **Zufall und Spass**: Wuerfel, Muenze, Zufallszahl, "A oder B?", Witze.
* **Secure Pro**: Antworten aus dem festen Sicherheitswissen (aquaticy/secure_knowledge.py).
* **Deine Daten**: Was du ihm sagst ("ich wohne in Bremen"), merkt sich Aquaticy wie sonst im
  Gedaechtnis (aquaticy/memory_auto.py, feste Muster, ohne Modell). Aquaticy Standard bestaetigt
  das und nutzt es: Eine Wetterfrage ohne Ort gilt fuer deinen Wohnort.

Netz: nur feste, oeffentliche HTTPS-Adressen (keine Adresse aus der Frage), kurze Zeitgrenzen,
hoechstens 512 KB je Antwort. Findet Aquaticy Standard nichts, sagt es das ehrlich -- und dass
ein API-Schluessel (Add-ons) freie Antworten auf alles bringt.
"""

from __future__ import annotations

import json
import math
import random
import re
import unicodedata
from collections.abc import Callable
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

MODEL_ID = "aquaticy/standard"
LABEL = "Aquaticy Standard"
MAX_BYTES = 512 * 1024
TIMEOUT = 8.0

#: Was ein Abruf liefern muss: (url) -> JSON oder None. Tests geben eine eigene Funktion.
Holen = Callable[[str], Any]

KEY_HINT = ("\n\n*Übrigens: Ich bin Aquaticy Standard und komme ohne Sprachmodell aus. Mit "
            "einem API-Schlüssel (Einstellungen → Add-ons) kann ich dir zu allem frei antworten.*")
KEY_HINT_EN = ("\n\n*Aquaticy Standard answers without a language model. With an API key "
               "(Settings → Add-ons) you get free answers to anything.*")


# -- Netz ---------------------------------------------------------------------------------------

ERLAUBTE_HOSTS = ("de.wikipedia.org", "en.wikipedia.org", "api.open-meteo.com",
                  "geocoding-api.open-meteo.com", "api.frankfurter.app", "www.tagesschau.de")


def holen_json(url: str) -> Any:
    """Holt JSON von einer der festen Adressen. None bei jedem Fehler."""
    from urllib.parse import urlsplit

    teile = urlsplit(url)
    if teile.scheme != "https" or teile.hostname not in ERLAUBTE_HOSTS:
        return None
    try:
        import httpx

        with httpx.Client(timeout=TIMEOUT, follow_redirects=False,
                          headers={"User-Agent": "Aquaticy-Standard/16"}
                          ) as client, client.stream("GET", url) as antwort:
            if antwort.status_code != 200:
                return None
            daten = b""
            for stueck in antwort.iter_bytes():
                daten += stueck
                if len(daten) > MAX_BYTES:
                    return None
        return json.loads(daten)
    except Exception:
        return None


# -- Text ---------------------------------------------------------------------------------------

def falten(text: str) -> str:
    """Kleinbuchstaben, Umlaute als ae/oe/ue, ohne Satzzeichen am Rand."""
    text = text.lower().replace("ß", "ss")
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        text = text.replace(alt, neu)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip(" ?!.,;:")


def zahl(text: str) -> float:
    """'1.234,5' oder '1234.5' oder '1,5' als Zahl."""
    text = text.strip().replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    return float(text)


def schoen(wert: float, stellen: int = 2) -> str:
    """Deutsche Schreibweise: 1.234,56 -- ohne ueberfluessige Nullen."""
    if math.isinf(wert) or math.isnan(wert):
        return str(wert)
    gerundet = round(wert, stellen)
    if gerundet == int(gerundet) and abs(gerundet) < 1e15:
        text = f"{int(gerundet):,}"
    else:
        text = f"{gerundet:,.{stellen}f}".rstrip("0").rstrip(".")
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


ZAHL = r"(-?\d[\d.,]*)"


# -- Rechnen und Prozente -----------------------------------------------------------------------

RECHEN_VORN = re.compile(
    r"^(?:was\s+(?:ist|ergibt|gibt|sind|macht)|wie\s*viel\s+(?:ist|sind|ergibt|macht)|"
    r"rechne(?:\s+mal)?(?:\s+aus)?|berechne(?:\s+mir)?|what\s+is|calculate)\s+")
WOERTER = (("plus", "+"), ("minus", "-"), ("mal", "*"), ("geteilt durch", "/"),
           ("durch", "/"), ("hoch", "**"), ("x", "*"), ("×", "*"), ("÷", "/"), ("^", "**"))


def rechnen(text: str) -> str:
    from aquaticy.calc import calculate

    kern = RECHEN_VORN.sub("", falten(text)).rstrip("= ")
    for wort, zeichen in WOERTER:
        kern = re.sub(rf"(?<=[\d\s)]){re.escape(wort)}(?=[\s\d(])", f" {zeichen} ", kern)
    kern = kern.replace("wurzel aus", "sqrt").replace("wurzel", "sqrt")
    if not re.fullmatch(r"[\d\s.,+\-*/()%sqrt]+", kern) or not re.search(r"\d", kern):
        return ""
    if not re.search(r"[+\-*/%]|sqrt", kern):
        return ""
    try:
        ergebnis = calculate(kern)
    except Exception:
        return ""
    return f"**{schoen(ergebnis, 6)}**"


PROZENT_VON = re.compile(rf"{ZAHL}\s*(?:%|prozent)\s+(?:von|aus)\s+{ZAHL}")
PROZENT_PLUS = re.compile(rf"{ZAHL}\s*(?:€|eur|euro)?\s*(plus|minus|\+|-)\s*{ZAHL}\s*(?:%|prozent)")
BRUTTO_NETTO = re.compile(rf"{ZAHL}\s*(?:€|eur|euro)?\s*(brutto|netto)\s*(?:in|zu|nach)\s*"
                          r"(netto|brutto)")


def prozente(text: str) -> str:
    kern = falten(text).replace("€", " € ")
    treffer = PROZENT_VON.search(kern)
    if treffer:
        p, g = zahl(treffer.group(1)), zahl(treffer.group(2))
        return f"{schoen(p)} % von {schoen(g)} sind **{schoen(g * p / 100)}**."
    treffer = PROZENT_PLUS.search(kern)
    if treffer:
        g, art, p = zahl(treffer.group(1)), treffer.group(2), zahl(treffer.group(3))
        faktor = 1 + p / 100 if art in ("plus", "+") else 1 - p / 100
        return (f"{schoen(g)} {'plus' if faktor > 1 else 'minus'} {schoen(p)} % sind "
                f"**{schoen(g * faktor)}** (Unterschied: {schoen(abs(g * faktor - g))}).")
    treffer = BRUTTO_NETTO.search(kern)
    if treffer:
        betrag, von, nach = zahl(treffer.group(1)), treffer.group(2), treffer.group(3)
        if von == nach:
            return ""
        if von == "brutto":
            netto = betrag / 1.19
            return (f"{schoen(betrag)} € brutto sind **{schoen(netto)} € netto** "
                    f"(19 % MwSt.: {schoen(betrag - netto)} €).")
        return (f"{schoen(betrag)} € netto sind **{schoen(betrag * 1.19)} € brutto** "
                f"(19 % MwSt.: {schoen(betrag * 0.19)} €).")
    return ""


# -- Einheiten ----------------------------------------------------------------------------------

_EINHEITEN_JE_ART: dict[str, list[tuple[str, float]]] = {
    "laenge": [("mm", .001), ("millimeter", .001), ("cm", .01), ("zentimeter", .01),
               ("m", 1), ("meter", 1), ("km", 1000), ("kilometer", 1000), ("zoll", .0254),
               ("inch", .0254), ("fuss", .3048), ("feet", .3048), ("ft", .3048),
               ("meile", 1609.344), ("meilen", 1609.344), ("mile", 1609.344),
               ("miles", 1609.344), ("seemeile", 1852), ("seemeilen", 1852)],
    "gewicht": [("mg", .001), ("g", 1), ("gramm", 1), ("kg", 1000), ("kilo", 1000),
                ("kilogramm", 1000), ("t", 1e6), ("tonne", 1e6), ("tonnen", 1e6),
                ("pfund", 500), ("lb", 453.59237), ("lbs", 453.59237), ("unze", 28.349523),
                ("unzen", 28.349523), ("oz", 28.349523)],
    "volumen": [("ml", .001), ("milliliter", .001), ("cl", .01), ("l", 1), ("liter", 1),
                ("gallone", 3.785411784), ("gallonen", 3.785411784), ("gallon", 3.785411784),
                ("m3", 1000), ("kubikmeter", 1000)],
    "flaeche": [("m2", 1), ("quadratmeter", 1), ("qm", 1), ("km2", 1e6),
                ("quadratkilometer", 1e6), ("ha", 1e4), ("hektar", 1e4), ("ar", 100)],
    "tempo": [("km/h", 1), ("kmh", 1), ("m/s", 3.6), ("mph", 1.609344), ("knoten", 1.852)],
    "zeit": [("sekunde", 1), ("sekunden", 1), ("s", 1), ("minute", 60), ("minuten", 60),
             ("min", 60), ("stunde", 3600), ("stunden", 3600), ("h", 3600), ("tag", 86400),
             ("tage", 86400), ("woche", 604800), ("wochen", 604800), ("jahr", 31557600),
             ("jahre", 31557600)],
    "daten": [("byte", 1), ("bytes", 1), ("kb", 1e3), ("mb", 1e6), ("gb", 1e9), ("tb", 1e12),
              ("kib", 1024), ("mib", 1024**2), ("gib", 1024**3), ("tib", 1024**4)],
}
EINHEITEN: dict[str, tuple[str, float]] = {
    name: (art, faktor) for art, liste in _EINHEITEN_JE_ART.items() for name, faktor in liste}
TEMPERATUR = {"c": "c", "grad": "c", "celsius": "c", "°c": "c", "f": "f", "fahrenheit": "f",
              "°f": "f", "k": "k", "kelvin": "k"}
UMRECHNEN = re.compile(rf"{ZAHL}\s*([a-z°/0-9]+)\s+(?:in|nach|zu|to|=)\s+([a-z°/0-9]+)")


def anzeige(name: str) -> str:
    """Einheit so geschrieben, wie man sie liest: GB, Meilen, km/h."""
    if EINHEITEN.get(name, ("",))[0] == "daten":
        return name.upper().replace("IB", "iB")
    if name.isalpha() and len(name) > 3:
        return name.capitalize()
    return name


def einheiten(text: str) -> str:
    treffer = UMRECHNEN.search(falten(text).replace("grad celsius", "celsius")
                               .replace("grad fahrenheit", "fahrenheit"))
    if not treffer:
        return ""
    wert, von, nach = zahl(treffer.group(1)), treffer.group(2), treffer.group(3)
    if von in TEMPERATUR and nach in TEMPERATUR:
        celsius = {"c": wert, "f": (wert - 32) * 5 / 9, "k": wert - 273.15}[TEMPERATUR[von]]
        ziel = {"c": celsius, "f": celsius * 9 / 5 + 32, "k": celsius + 273.15}[TEMPERATUR[nach]]
        zeichen = {"c": "°C", "f": "°F", "k": "K"}
        return (f"{schoen(wert)} {zeichen[TEMPERATUR[von]]} sind "
                f"**{schoen(ziel)} {zeichen[TEMPERATUR[nach]]}**.")
    if von not in EINHEITEN or nach not in EINHEITEN or EINHEITEN[von][0] != EINHEITEN[nach][0]:
        return ""
    ergebnis = wert * EINHEITEN[von][1] / EINHEITEN[nach][1]
    return f"{schoen(wert)} {anzeige(von)} sind **{schoen(ergebnis, 4)} {anzeige(nach)}**."


# -- Datum und Uhrzeit --------------------------------------------------------------------------

WOCHENTAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
MONATE = ("januar", "februar", "maerz", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "dezember")


def ostern(jahr: int) -> date:
    """Ostersonntag nach Gauss/Anonymous Gregorian."""
    a, b, c = jahr % 19, jahr // 100, jahr % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    monat = (h + l_ - 7 * m + 114) // 31
    tag = (h + l_ - 7 * m + 114) % 31 + 1
    return date(jahr, monat, tag)


def datum_aus(text: str, heute: date) -> date | None:
    """'24.12.', '24.12.2026', '3. Oktober', '3 oktober 2027'."""
    treffer = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})?", text)
    try:
        if treffer:
            jahr = int(treffer.group(3)) if treffer.group(3) else heute.year
            jahr += 2000 if jahr < 100 else 0
            return date(jahr, int(treffer.group(2)), int(treffer.group(1)))
        treffer = re.search(r"\b(\d{1,2})\.?\s+(" + "|".join(MONATE) + r")\s*(\d{4})?", text)
        if treffer:
            jahr = int(treffer.group(3)) if treffer.group(3) else heute.year
            return date(jahr, MONATE.index(treffer.group(2)) + 1, int(treffer.group(1)))
    except ValueError:
        return None
    return None


def tage_text(tage: int, was: str, wann: str = "") -> str:
    wann = f" ({wann})" if wann else ""
    if tage == 0:
        return f"{was}{wann} ist **heute**."
    if tage == 1:
        return f"Bis {was}{wann} ist es noch **1 Tag**."
    return f"Bis {was}{wann} sind es noch **{tage} Tage**."


def zeit(text: str, jetzt: datetime | None = None) -> str:
    from aquaticy import zeit as zeit_mod

    jetzt = jetzt or zeit_mod.jetzt()
    heute = jetzt.date()
    kern = falten(text)
    if re.search(r"\b(wie\s*spaet|uhrzeit|wieviel\s+uhr|wie\s+viel\s+uhr)\b", kern):
        return f"Es ist **{jetzt:%H:%M} Uhr** ({zeit_mod.kurz(jetzt)})."
    if re.search(r"\b(welche[rs]?\s+(tag|datum)|den\s+wievielten|welches\s+datum|"
                 r"was\s+fuer\s+ein\s+tag)\b", kern):
        return (f"Heute ist **{WOCHENTAGE[heute.weekday()]}, der {heute:%d.%m.%Y}** "
                f"(KW {heute.isocalendar()[1]}).")
    if re.search(r"\b(kalenderwoche|kw)\b", kern):
        return f"Wir haben **KW {heute.isocalendar()[1]}**."
    if re.search(r"\bwie\s*(viele|lange)\b.*\bbis\b|\bbis\s+(weihnachten|silvester|ostern)\b|"
                 r"\btage\s+bis\b", kern):
        ziele = {"weihnachten": date(heute.year, 12, 24), "heiligabend": date(heute.year, 12, 24),
                 "silvester": date(heute.year, 12, 31), "neujahr": date(heute.year + 1, 1, 1),
                 "ostern": ostern(heute.year)}
        for name, tag in ziele.items():
            if name in kern:
                if tag < heute:
                    tag = (ostern(heute.year + 1) if name == "ostern"
                           else tag.replace(year=tag.year + 1))
                anzeige = {"heiligabend": "Heiligabend"}.get(name, name.capitalize())
                return tage_text((tag - heute).days, anzeige, f"{tag:%d.%m.%Y}")
        gesucht = datum_aus(kern, heute)
        if gesucht:
            if gesucht < heute and not re.search(r"\d{4}", kern):
                gesucht = gesucht.replace(year=gesucht.year + 1)
            if gesucht >= heute:
                return tage_text((gesucht - heute).days, f"zum {gesucht:%d.%m.%Y}")
    treffer = re.search(r"\b(welche[rs]?\s+(?:wochen)?tag\s+(?:ist|war|wird|faellt)|"
                        r"auf\s+welchen\s+tag)\b", kern)
    if treffer:
        gesucht = datum_aus(kern, heute)
        if gesucht:
            zeitform = "war" if gesucht < heute else "ist"
            return f"Der {gesucht:%d.%m.%Y} {zeitform} ein **{WOCHENTAGE[gesucht.weekday()]}**."
    if re.search(r"\bwann\s+ist\s+ostern\b", kern):
        tag = ostern(heute.year)
        if tag < heute:
            tag = ostern(heute.year + 1)
        return f"Ostersonntag ist am **{tag:%d.%m.%Y}**."
    return ""


# -- Zufall und Spass ---------------------------------------------------------------------------

WITZE = (
    "Treffen sich zwei Magneten. Sagt der eine: „Was soll ich heute bloß anziehen?“",
    "Warum können Geister so schlecht lügen? Weil man durch sie hindurchsieht.",
    "Was macht ein Pirat am Computer? Er drückt die Enter-Taste.",
    "Wie nennt man einen Bumerang, der nicht zurückkommt? Stock.",
    "Was ist orange und läuft durch den Wald? Eine Wanderine.",
    "Treffen sich zwei Kerzen. Fragt die eine: „Ist Wachs gefährlich?“",
)


def zufall(text: str, wuerfel: random.Random | None = None) -> str:
    rnd = wuerfel or random.SystemRandom()
    kern = falten(text)
    if re.search(r"\bwuerf(el|le)\b", kern):
        return f"🎲 Gewürfelt: **{rnd.randint(1, 6)}**"
    if re.search(r"\b(muenze|kopf\s+oder\s+zahl)\b", kern):
        return f"🪙 **{rnd.choice(('Kopf', 'Zahl'))}**"
    treffer = re.search(r"zufallszahl(?:\s+zwischen)?\s+(-?\d+)\s+(?:und|bis|-)\s+(-?\d+)", kern)
    if treffer:
        a, b = sorted((int(treffer.group(1)), int(treffer.group(2))))
        return f"Zufallszahl: **{rnd.randint(a, b)}**"
    if re.search(r"\bzufallszahl\b", kern):
        return f"Zufallszahl zwischen 1 und 100: **{rnd.randint(1, 100)}**"
    treffer = re.match(r"^soll\s+ich\s+(?:lieber\s+)?(.{1,60}?)\s+oder\s+(.{1,60}?)"
                       r"(?:\s+(?:essen|machen|nehmen|kaufen|tun|gehen|spielen))?[?!. ]*$",
                       str(text).strip(), re.I)
    if treffer:
        return f"Ich würde sagen: **{rnd.choice((treffer.group(1), treffer.group(2)))}**."
    if re.search(r"\b(witz|erzaehl\s+(mir\s+)?was\s+lustiges)\b", kern):
        return rnd.choice(WITZE)
    return ""


# -- Wetter -------------------------------------------------------------------------------------

WETTERCODES = {0: "klar ☀️", 1: "überwiegend klar 🌤️", 2: "teils bewölkt ⛅", 3: "bedeckt ☁️",
               45: "Nebel 🌫️", 48: "Nebel mit Reif 🌫️", 51: "leichter Niesel 🌦️",
               53: "Niesel 🌦️", 55: "starker Niesel 🌧️", 61: "leichter Regen 🌦️",
               63: "Regen 🌧️", 65: "starker Regen 🌧️", 66: "gefrierender Regen 🌧️",
               67: "starker gefrierender Regen 🌧️", 71: "leichter Schnee 🌨️", 73: "Schnee 🌨️",
               75: "starker Schnee ❄️", 77: "Schneegriesel 🌨️", 80: "Regenschauer 🌦️",
               81: "kräftige Schauer 🌧️", 82: "heftige Schauer ⛈️", 85: "Schneeschauer 🌨️",
               86: "kräftige Schneeschauer ❄️", 95: "Gewitter ⛈️", 96: "Gewitter mit Hagel ⛈️",
               99: "schweres Gewitter mit Hagel ⛈️"}
WETTER_WORT = re.compile(r"\b(wetter|regnet|regnen|regen|sonne|sonnig|temperatur|grad\s+warm|"
                         r"wie\s+warm|wie\s+kalt|schnee|schneit|schneien|gewitter|vorhersage|"
                         r"wind|windig|sturm|frost|glatt|glatteis)\b")
ANZIEHEN_WORT = re.compile(r"\b(anziehen|anzieh|kleidung|klamotten|jacke|mantel|pulli|pullover|"
                           r"kurze\s+hose|kurzer?\s+hose|muetze|handschuhe|t-?shirt|outfit|"
                           r"what\s+(?:should\s+i|to)\s+wear)\b")
SCHIRM_WORT = re.compile(r"\b((regen)?schirm|umbrella|nass\s+werden|regenjacke)\b")
SONNE_WORT = re.compile(r"\b(sonnenaufgang|sonnenuntergang|sonne\s+(?:auf|unter)|"
                        r"geht\s+die\s+sonne|wird\s+es\s+(?:hell|dunkel)|sunrise|sunset)\b")
ORT_NACH = re.compile(r"\b(?:in|fuer|bei|um|im)\s+([a-z][a-z\s.\-]{1,40}?)"
                      r"(?:\s+(?:heute|morgen|uebermorgen|am\s+wochenende|diese\s+woche|"
                      r"die\s+naechsten\s+tage|am\s+\w+tag|am\s+mittwoch|am\s+samstag|"
                      r"am\s+sonntag|an|aus|anziehen|mitnehmen))?$")
FUELLWORTE = (r"\b(heute|morgen|uebermorgen|wetter|das|die|der|den|regnen|regnet|schneien|"
              r"schneit|sonnig|warm|kalt|werden|wird|es|sein|geben|wochenende|woche|naechsten|"
              r"tage|diese|am|anziehen|mitnehmen|soll|ich|einen|schirm|regenschirm|jacke|"
              r"brauche|draussen|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)\b")
QUELLE_WETTER = "\n\nQuelle: [Open-Meteo](https://open-meteo.com)"
ORT_FRAGE = "Für welchen Ort soll ich nachsehen?"
ORT_BEISPIEL = " Schreib einfach den Namen, zum Beispiel „Berlin“."
WOCHENTAG_KURZ = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
WOCHENTAG_WORT = ("montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag")


def waehle(optionen: tuple[str, ...], schluessel: str) -> str:
    """Eine Formulierung je Frage -- abwechslungsreich, aber fuer dieselbe Frage immer gleich."""
    import hashlib

    nummer = int(hashlib.sha256(schluessel.encode("utf-8")).hexdigest()[:8], 16)
    return optionen[nummer % len(optionen)]


def tage_aus(kern: str, heute: date) -> list[int]:
    """Welche Tage gemeint sind: [0] heute, [1] morgen, Wochenende, Wochentag, naechste Tage."""
    if re.search(r"\b(naechsten\s+tage|diese\s+woche|ganze\s+woche|woche|7\s+tage)\b", kern):
        return list(range(0, 7))
    if "wochenende" in kern:
        sa = (5 - heute.weekday()) % 7
        return [sa, sa + 1] if sa + 1 < 7 else [sa]
    if "uebermorgen" in kern:
        return [2]
    if re.search(r"\bmorgen\b", kern):
        return [1]
    for nummer, name in enumerate(WOCHENTAG_WORT):
        if re.search(rf"\b(am\s+)?{name}\b", kern):
            return [(nummer - heute.weekday()) % 7]
    return [0]


def tag_aus(kern: str) -> int:
    if "uebermorgen" in kern:
        return 2
    if re.search(r"\bmorgen\b", kern):
        return 1
    return 0


def ort_aus(kern: str) -> str:
    treffer = ORT_NACH.search(kern)
    if not treffer:
        return ""
    ort = re.sub(FUELLWORTE, "", treffer.group(1))
    return re.sub(r"\s+", " ", ort).strip(" .-")


def _liste(werte: Any, n: int) -> list[Any]:
    return list(werte)[:n] + [None] * max(0, n - len(werte)) if isinstance(werte, list) else (
        [None] * n)


def wetterdaten(ort: str, holen: Holen, heute: date | None = None) -> dict[str, Any] | str:
    """Vorhersage fuer sieben Tage. Returns: die Daten -- oder einen Satz, warum nicht."""
    geo = holen("https://geocoding-api.open-meteo.com/v1/search?count=1&language=de&name="
                + quote(ort))
    treffer = (geo or {}).get("results") or []
    if not treffer:
        return (f"Hm, einen Ort namens „{ort}“ finde ich nicht. Magst du ihn anders schreiben, "
                "vielleicht mit dem Land dazu?")
    stelle = treffer[0]
    daten = holen("https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&daily="
                  "weather_code,temperature_2m_max,temperature_2m_min,"
                  "apparent_temperature_max,apparent_temperature_min,"
                  "precipitation_probability_max,precipitation_sum,wind_speed_10m_max,"
                  "uv_index_max,sunrise,sunset&current=temperature_2m,apparent_temperature,"
                  "weather_code,wind_speed_10m&timezone=auto&forecast_days=7"
                  .format(stelle.get("latitude"), stelle.get("longitude")))
    if not daten or "daily" not in daten:
        return "Das Wetter lässt sich gerade nicht abrufen. Versuch es gleich noch einmal."
    t = daten["daily"]
    n = len(t.get("weather_code") or []) or 1
    spalten = {k: _liste(t.get(k), n) for k in (
        "time", "weather_code", "temperature_2m_max", "temperature_2m_min",
        "apparent_temperature_max", "apparent_temperature_min", "precipitation_probability_max",
        "precipitation_sum", "wind_speed_10m_max", "uv_index_max", "sunrise", "sunset")}
    tage = []
    for i in range(n):
        try:
            datum = (date.fromisoformat(str(spalten["time"][i])[:10]) if spalten["time"][i]
                     else (heute or date.today()).fromordinal((heute or date.today())
                                                              .toordinal() + i))
        except ValueError:
            datum = None
        tage.append({"datum": datum, "code": spalten["weather_code"][i],
                     "hoch": spalten["temperature_2m_max"][i],
                     "tief": spalten["temperature_2m_min"][i],
                     "gefuehlt_hoch": spalten["apparent_temperature_max"][i],
                     "gefuehlt_tief": spalten["apparent_temperature_min"][i],
                     "regen": spalten["precipitation_probability_max"][i],
                     "menge": spalten["precipitation_sum"][i],
                     "wind": spalten["wind_speed_10m_max"][i], "uv": spalten["uv_index_max"][i],
                     "auf": spalten["sunrise"][i], "unter": spalten["sunset"][i]})
    return {"name": stelle.get("name", ort), "zone": stelle.get("timezone") or "",
            "tage": tage, "jetzt": daten.get("current") or {}}


def _grad(wert: Any) -> str:
    return "?" if wert is None else schoen(float(wert), 0)


def _tagesname(tag: int, datum: date | None) -> str:
    if tag < 3:
        return ("Heute", "Morgen", "Übermorgen")[tag]
    if datum is None:
        return f"In {tag} Tagen"
    return f"{WOCHENTAGE[datum.weekday()]}, {datum:%d.%m.}"


def _einschaetzung(t: dict[str, Any]) -> str:
    """Ein Satz, wie sich der Tag anfuehlt -- wie man es einem Freund sagen wuerde."""
    hoch = t.get("hoch")
    regen = t.get("regen") or 0
    code = int(t.get("code") or 0)
    wind = t.get("wind") or 0
    if code >= 95:
        return "Bei Gewitter bleibst du am besten drinnen."
    if code in (66, 67) or (t.get("tief") is not None and t["tief"] <= 0 and regen >= 40):
        return "Pass auf, es kann glatt werden."
    if t.get("tief") is not None and t["tief"] <= 0:
        return "Morgens ist es frostig – auf Brücken und Gehwegen kann es glatt sein."
    if code >= 71 and code <= 86 and code not in (80, 81, 82):
        return "Schnee! Zieh dich warm an und plane mehr Zeit ein."
    if regen >= 70:
        return "Ziemlich nass – ein Schirm lohnt sich auf jeden Fall."
    if wind >= 50:
        return "Es wird stürmisch, halt deinen Hut fest."
    if hoch is not None and hoch >= 28:
        return "Richtig warm! Trink genug und denk an Sonnencreme."
    if hoch is not None and hoch >= 20 and regen < 30:
        return "Schönes Wetter, um rauszugehen."
    if hoch is not None and hoch <= 5:
        return "Ganz schön frisch, eine warme Jacke ist eine gute Idee."
    if regen >= 40:
        return "Ein paar Tropfen sind drin, also lieber einen Schirm einpacken."
    return "Ein ziemlich normaler Tag, nichts Besonderes zu beachten."


def wetter_text(d: dict[str, Any], tage: list[int], frage: str = "") -> str:
    name = d["name"]
    verfuegbar = [i for i in tage if i < len(d["tage"])]
    if not verfuegbar:
        return f"So weit kann ich für {name} leider nicht vorausschauen – nur sieben Tage."
    if len(verfuegbar) == 1:
        i = verfuegbar[0]
        t = d["tage"][i]
        zeile = (f"**{_tagesname(i, t['datum'])} in {name}:** "
                 f"{WETTERCODES.get(int(t['code'] or 0), 'wechselhaft')}, "
                 f"{_grad(t['tief'])} bis {_grad(t['hoch'])} °C")
        if t.get("regen") is not None:
            zeile += f", Regenrisiko {t['regen']} %"
        zeile += "."
        jetzt = d["jetzt"]
        if i == 0 and jetzt.get("temperature_2m") is not None:
            zeile += f" Gerade sind es {_grad(jetzt['temperature_2m'])} °C"
            gefuehlt = jetzt.get("apparent_temperature")
            if gefuehlt is not None and abs(float(gefuehlt) - float(jetzt["temperature_2m"])) >= 2:
                zeile += f", gefühlt eher {_grad(gefuehlt)} °C"
            zeile += "."
        tipp = _einschaetzung(t)
        ideen = ["Willst du wissen, was du am besten anziehst?"]
        ideen.append("Soll ich auch nach morgen schauen?" if i == 0 else
                     "Soll ich dir auch die nächsten Tage zeigen?")
        if (t.get("regen") or 0) < 40:
            ideen.append("Frag mich gern, ob du einen Schirm brauchst.")
        weiter = waehle(tuple(ideen), name + frage + str(i))
        vorn = waehle(("Ich hab für dich nachgesehen.", "Klar, hier ist das Wetter.",
                       "Gern, so sieht es aus.", "Hier kommt die Vorhersage."), name + frage)
        return f"{vorn}\n\n{zeile}\n\n{tipp} {weiter}{QUELLE_WETTER}"
    kopf = ("Das Wochenende" if len(verfuegbar) == 2 and d["tage"][verfuegbar[0]]["datum"] and
            d["tage"][verfuegbar[0]]["datum"].weekday() == 5 else "Die nächsten Tage")
    zeilen = [f"**{kopf} in {name}:**"]
    for i in verfuegbar:
        t = d["tage"][i]
        datum = t["datum"]
        tagname = ("heute" if i == 0 else "morgen" if i == 1 else
                   (f"{WOCHENTAG_KURZ[datum.weekday()]} {datum:%d.%m.}" if datum else f"Tag {i}"))
        regen = f", Regen {t['regen']} %" if t.get("regen") is not None else ""
        zeilen.append(f"- **{tagname}:** {WETTERCODES.get(int(t['code'] or 0), 'wechselhaft')}, "
                      f"{_grad(t['tief'])} bis {_grad(t['hoch'])} °C{regen}")
    trocken = [i for i in verfuegbar if (d["tage"][i].get("regen") or 0) < 30]
    if trocken and len(trocken) < len(verfuegbar):
        beste = max(trocken, key=lambda i: d["tage"][i].get("hoch") or -99)
        name_beste = _tagesname(beste, d["tage"][beste]["datum"])
        name_beste = name_beste.lower() if beste < 3 else name_beste
        zeilen.append(f"\nAm schönsten wird es wohl **{name_beste.rstrip('.')}**.")
    elif not trocken:
        zeilen.append("\nEs bleibt leider durchweg nass – Schirm griffbereit halten.")
    else:
        zeilen.append("\nSieht gut aus: Es bleibt überwiegend trocken.")
    return "\n".join(zeilen) + QUELLE_WETTER


def anziehen_text(d: dict[str, Any], tag: int) -> str:
    """Was man anzieht -- aus Temperatur (gefuehlt), Regen, Wind und Sonne."""
    if tag >= len(d["tage"]):
        tag = 0
    t = d["tage"][tag]
    hoch = t.get("gefuehlt_hoch") if t.get("gefuehlt_hoch") is not None else t.get("hoch")
    tief = t.get("gefuehlt_tief") if t.get("gefuehlt_tief") is not None else t.get("tief")
    regen = t.get("regen") or 0
    wann = ("heute", "morgen", "übermorgen")[tag] if tag < 3 else _tagesname(tag, t["datum"])
    if hoch is None:
        return f"Für {d['name']} habe ich gerade keine Temperaturen. Versuch es gleich noch mal."
    if hoch >= 25:
        kleidung = "leichte Sachen: ein T-Shirt und eine kurze Hose oder ein luftiges Kleid"
    elif hoch >= 18:
        kleidung = "ein T-Shirt und für später eine dünne Jacke oder einen Pulli"
    elif hoch >= 12:
        kleidung = "eine lange Hose, einen Pulli und eine leichte Jacke"
    elif hoch >= 5:
        kleidung = "eine warme Jacke, einen Pulli und eine lange Hose"
    else:
        kleidung = "die dicke Winterjacke, dazu Mütze, Schal und Handschuhe"
    mitnehmen = []
    if regen >= 50:
        mitnehmen.append("eine Regenjacke oder einen Schirm")
    elif regen >= 30:
        mitnehmen.append("sicherheitshalber einen kleinen Schirm")
    if (t.get("uv") or 0) >= 6:
        mitnehmen.append("Sonnenbrille und Sonnencreme")
    extra = ""
    if (t.get("wind") or 0) >= 40 and hoch < 18:
        extra += " Es wird windig, also lieber etwas Winddichtes."
    if tief is not None and hoch - tief >= 10:
        extra += " Am besten im Zwiebellook – morgens ist es deutlich kühler."
    if mitnehmen:
        extra = (" Nimm außerdem " + " und ".join(mitnehmen) + " mit." + extra)
    einstieg = waehle(("Ich würde sagen:", "Mein Tipp:", "So wärst du gut angezogen:"),
                      d["name"] + str(tag))
    return (f"{einstieg} Für {wann} in **{d['name']}** zieh am besten {kleidung} an.{extra}\n\n"
            f"Es werden {_grad(t.get('tief'))} bis {_grad(t.get('hoch'))} °C"
            + (f", gefühlt bis {_grad(t.get('gefuehlt_hoch'))} °C" if t.get("gefuehlt_hoch")
               is not None and t.get("gefuehlt_hoch") != t.get("hoch") else "")
            + f", Regenrisiko {regen} %." + QUELLE_WETTER)


def schirm_text(d: dict[str, Any], tag: int) -> str:
    if tag >= len(d["tage"]):
        tag = 0
    t = d["tage"][tag]
    regen = t.get("regen")
    wann = ("heute", "morgen", "übermorgen")[tag] if tag < 3 else _tagesname(tag, t["datum"])
    if regen is None:
        return f"Für {d['name']} kenne ich das Regenrisiko gerade nicht." + QUELLE_WETTER
    menge = t.get("menge")
    mm = f" (etwa {schoen(float(menge), 1)} mm)" if menge else ""
    if regen >= 60:
        satz = f"Ja, nimm auf jeden Fall einen Schirm mit. Das Regenrisiko liegt bei {regen} %{mm}."
    elif regen >= 30:
        satz = (f"Vielleicht. Das Regenrisiko liegt bei {regen} %{mm} – ein kleiner Schirm "
                "schadet nicht.")
    else:
        satz = (f"Eher nicht, den Schirm kannst du zu Hause lassen. Das Regenrisiko liegt nur bei "
                f"{regen} %.")
    return f"Für {wann} in **{d['name']}**: {satz}" + QUELLE_WETTER


def sonne_text(d: dict[str, Any], tag: int) -> str:
    if tag >= len(d["tage"]):
        tag = 0
    t = d["tage"][tag]
    auf, unter = str(t.get("auf") or ""), str(t.get("unter") or "")
    if len(auf) < 16 or len(unter) < 16:
        return f"Die Zeiten für Sonnenauf- und -untergang in {d['name']} habe ich gerade nicht."
    wann = ("Heute", "Morgen", "Übermorgen")[tag] if tag < 3 else _tagesname(tag, t["datum"])
    try:
        a, u = datetime.fromisoformat(auf), datetime.fromisoformat(unter)
        dauer = u - a
        stunden, rest = divmod(int(dauer.total_seconds()) // 60, 60)
        laenge = f" Der Tag ist damit {stunden} Stunden und {rest} Minuten lang."
    except ValueError:
        laenge = ""
    return (f"{wann} geht die Sonne in **{d['name']}** um **{auf[11:16]} Uhr** auf und um "
            f"**{unter[11:16]} Uhr** unter.{laenge}" + QUELLE_WETTER)


# -- Wechselkurse -------------------------------------------------------------------------------

WAEHRUNGEN = {"euro": "EUR", "eur": "EUR", "€": "EUR", "dollar": "USD", "usd": "USD",
              "$": "USD", "pfund": "GBP", "gbp": "GBP", "franken": "CHF", "chf": "CHF",
              "yen": "JPY", "jpy": "JPY", "zloty": "PLN", "pln": "PLN", "krone": "SEK",
              "kronen": "SEK", "sek": "SEK", "dkk": "DKK", "nok": "NOK", "yuan": "CNY",
              "cny": "CNY", "lira": "TRY", "try": "TRY", "aud": "AUD", "cad": "CAD"}
WAEHRUNG_SATZ = re.compile(rf"{ZAHL}?\s*([a-z€$]+)\s+(?:in|nach|zu|to)\s+([a-z€$]+)")


def waehrung(text: str, holen: Holen) -> str:
    kern = falten(text).replace("€", " € ").replace("$", " $ ")
    treffer = WAEHRUNG_SATZ.search(kern)
    if not treffer:
        return ""
    von, nach = WAEHRUNGEN.get(treffer.group(2)), WAEHRUNGEN.get(treffer.group(3))
    if not von or not nach or von == nach:
        return ""
    betrag = zahl(treffer.group(1)) if treffer.group(1) else 1.0
    daten = holen(f"https://api.frankfurter.app/latest?from={von}&to={nach}")
    kurs = ((daten or {}).get("rates") or {}).get(nach)
    if not kurs:
        return "Die Wechselkurse lassen sich gerade nicht abrufen."
    stand = (daten or {}).get("date", "")
    return (f"{schoen(betrag)} {von} sind **{schoen(betrag * float(kurs))} {nach}** "
            f"(Kurs {schoen(float(kurs), 4)}, Stand {stand}).\n\nQuelle: Europäische Zentralbank "
            "über [Frankfurter](https://www.frankfurter.app)")


# -- Nachrichten --------------------------------------------------------------------------------

def nachrichten(holen: Holen) -> str:
    daten = holen("https://www.tagesschau.de/api2u/homepage/")
    meldungen = [m for m in (daten or {}).get("news") or []
                 if isinstance(m, dict) and m.get("title")][:5]
    if not meldungen:
        return "Die Nachrichten lassen sich gerade nicht abrufen."
    zeilen = ["**Die wichtigsten Nachrichten:**"]
    for m in meldungen:
        link = m.get("shareURL") or m.get("detailsweb") or ""
        titel = str(m["title"]).replace("[", "(").replace("]", ")")
        zeilen.append(f"- [{titel}]({link})" if link.startswith("https://") else f"- {titel}")
    return "\n".join(zeilen) + "\n\nQuelle: [tagesschau.de](https://www.tagesschau.de)"


# -- Wissen (Wikipedia) -------------------------------------------------------------------------

WISSEN_VORN = re.compile(
    r"^(?:und\s+)?(?:wer|was)\s+(?:ist|sind|war|waren)\s+|^erzaehl\s+(?:mir\s+)?(?:etwas\s+|was\s+)?"
    r"(?:ueber|von)\s+|^was\s+weisst\s+du\s+(?:ueber|von)\s+|^erklaer(?:e)?\s+(?:mir\s+)?|"
    r"^was\s+bedeutet\s+|^was\s+versteht\s+man\s+unter\s+|^(?:who|what)\s+(?:is|are|was)\s+")
ARTIKEL = re.compile(r"^(?:der|die|das|ein|eine|einen|den|dem|des|the|a|an)\s+")


def thema_aus(text: str) -> str:
    roh = re.sub(r"\s+", " ", text).strip(" ?!.")
    kern = falten(roh)
    treffer = WISSEN_VORN.match(kern)
    if not treffer:
        return ""
    # Den Rest aus dem Original nehmen, damit Umlaute und Grossschreibung bleiben.
    worte = roh.split(" ")
    vorn = len(treffer.group(0).split())
    rest = " ".join(worte[vorn:]).strip()
    rest = ARTIKEL.sub("", rest) if ARTIKEL.match(rest.lower()) else rest
    return rest[:80]


def wissen(thema: str, holen: Holen) -> str:
    suche = holen("https://de.wikipedia.org/w/api.php?action=opensearch&limit=1&namespace=0"
                  "&format=json&search=" + quote(thema))
    titel = ""
    if isinstance(suche, list) and len(suche) > 1 and suche[1]:
        titel = str(suche[1][0])
    if not titel:
        return ""
    seite = holen("https://de.wikipedia.org/api/rest_v1/page/summary/"
                  + quote(titel.replace(" ", "_"), safe=""))
    if not isinstance(seite, dict) or seite.get("type") == "disambiguation":
        return (f"Zu „{thema}“ gibt es mehrere Bedeutungen. Sag mir genauer, welche du meinst."
                if isinstance(seite, dict) else "")
    auszug = str(seite.get("extract") or "").strip()
    if not auszug:
        return ""
    saetze = re.split(r"(?<=[.!?])\s+", auszug)
    kurz = " ".join(saetze[:3])
    link = ((seite.get("content_urls") or {}).get("desktop") or {}).get("page") or (
        "https://de.wikipedia.org/wiki/" + quote(titel.replace(" ", "_")))
    return f"**{seite.get('title', titel)}:** {kurz}\n\nQuelle: [Wikipedia]({link})"


# -- Uhrzeit in anderen Staedten ----------------------------------------------------------------

UHRZEIT_IN = re.compile(r"\b(?:wie\s*spaet|uhrzeit|wieviel\s+uhr|wie\s+viel\s+uhr)\b.*?\b"
                        r"(?:in|auf)\s+([a-z][a-z\s.\-]{1,40})$")


def uhrzeit_in(ort: str, holen: Holen, jetzt: datetime | None = None) -> str:
    from zoneinfo import ZoneInfo

    from aquaticy import zeit as zeit_mod

    geo = holen("https://geocoding-api.open-meteo.com/v1/search?count=1&language=de&name="
                + quote(ort))
    treffer = (geo or {}).get("results") or []
    zone = str((treffer[0] if treffer else {}).get("timezone") or "")
    if not zone:
        return f"Für „{ort}“ finde ich keine Zeitzone. Schreib die Stadt vielleicht etwas genauer?"
    try:
        dort = (jetzt or zeit_mod.jetzt()).astimezone(ZoneInfo(zone))
    except Exception:
        return f"Die Zeitzone von „{ort}“ kenne ich leider nicht."
    hier = jetzt or zeit_mod.jetzt()
    versatz_dort, versatz_hier = dort.utcoffset(), hier.utcoffset()
    diff = ((versatz_dort - versatz_hier).total_seconds() / 3600
            if versatz_dort is not None and versatz_hier is not None else 0.0)
    if diff:
        unterschied = (f" Das sind {schoen(abs(diff), 1)} Stunden "
                       f"{'mehr' if diff > 0 else 'weniger'} als bei dir.")
    else:
        unterschied = " Dieselbe Zeit wie bei dir."
    name = treffer[0].get("name", ort)
    return (f"In **{name}** ist es gerade **{dort:%H:%M} Uhr** "
            f"({WOCHENTAGE[dort.weekday()]}).{unterschied}")


# -- Feiertage und Mond -------------------------------------------------------------------------

def feiertage(jahr: int) -> list[tuple[date, str]]:
    """Die bundesweiten Feiertage in Deutschland."""
    from datetime import timedelta

    o = ostern(jahr)
    return sorted([
        (date(jahr, 1, 1), "Neujahr"), (o - timedelta(days=2), "Karfreitag"),
        (o + timedelta(days=1), "Ostermontag"), (date(jahr, 5, 1), "Tag der Arbeit"),
        (o + timedelta(days=39), "Christi Himmelfahrt"), (o + timedelta(days=50), "Pfingstmontag"),
        (date(jahr, 10, 3), "Tag der Deutschen Einheit"), (date(jahr, 12, 25), "1. Weihnachtstag"),
        (date(jahr, 12, 26), "2. Weihnachtstag")])


FEIERTAG_NAMEN = {"karfreitag": "Karfreitag", "ostermontag": "Ostermontag",
                  "himmelfahrt": "Christi Himmelfahrt", "vatertag": "Christi Himmelfahrt",
                  "pfingst": "Pfingstmontag", "tag der arbeit": "Tag der Arbeit",
                  "einheit": "Tag der Deutschen Einheit"}


def feiertag(text: str, heute: date) -> str:
    kern = falten(text)
    if "feiertag" not in kern and not any(k in kern for k in FEIERTAG_NAMEN):
        return ""
    alle = feiertage(heute.year) + feiertage(heute.year + 1)
    for wort, name in FEIERTAG_NAMEN.items():
        if wort in kern and "wann" in kern:
            tag = next(t for t, n in alle if n == name and t >= heute)
            return (f"{name} ist dieses Mal am **{WOCHENTAGE[tag.weekday()]}, {tag:%d.%m.%Y}** – "
                    f"in {(tag - heute).days} Tagen.")
    if re.search(r"\b(ist\s+heute|heute\s+ein)\b", kern):
        heutig = [n for t, n in alle if t == heute]
        if heutig:
            return f"Ja, heute ist **{heutig[0]}** – genieß den freien Tag!"
        return ("Nein, heute ist kein bundesweiter Feiertag. In manchen Bundesländern kann es "
                "anders sein.")
    naechste = [(t, n) for t, n in alle if t >= heute][:3]
    zeilen = [f"- **{n}:** {WOCHENTAGE[t.weekday()]}, {t:%d.%m.%Y}" for t, n in naechste]
    return ("Die nächsten bundesweiten Feiertage:\n" + "\n".join(zeilen)
            + "\n\nEinige Bundesländer haben noch weitere, zum Beispiel Fronleichnam oder den "
            "Reformationstag.")


MONDPHASEN = ("Neumond 🌑", "zunehmende Sichel 🌒", "erstes Viertel 🌓", "zunehmender Mond 🌔",
              "Vollmond 🌕", "abnehmender Mond 🌖", "letztes Viertel 🌗", "abnehmende Sichel 🌘")


def mond(text: str, heute: date) -> str:
    kern = falten(text)
    if not re.search(r"\b(mond|mondphase|vollmond|neumond)\b", kern):
        return ""
    synodisch = 29.530588853
    alter = (heute - date(2000, 1, 6)).days % synodisch
    phase = MONDPHASEN[int((alter / synodisch) * 8 + 0.5) % 8]
    bis_voll = (14.765 - alter) % synodisch
    satz = f"Heute ist **{phase}**."
    if "vollmond" in kern and not phase.startswith("Vollmond"):
        satz = f"Nein, heute ist kein Vollmond, sondern **{phase}**."
    elif "vollmond" in kern:
        satz = "Ja, heute ist **Vollmond 🌕**."
    if ("vollmond" in kern or "wann" in kern) and not phase.startswith("Vollmond"):
        satz += f" Der nächste Vollmond ist in etwa **{round(bis_voll)} Tagen**."
    return satz + " (Ungefähr berechnet, auf ein bis zwei Tage genau.)"


# -- Rechnen im Alltag --------------------------------------------------------------------------

def alter(text: str, heute: date) -> str:
    kern = falten(text)
    if not re.search(r"\b(wie\s+alt|alter|geboren|geburtstag)\b", kern):
        return ""
    geburt = datum_aus(kern, heute)
    if geburt is None:
        jahr = re.search(r"\b(19\d{2}|20\d{2})\b", kern)
        if not jahr or not re.search(r"\bgeboren\b", kern):
            return ""
        jahre = heute.year - int(jahr.group(1))
        return (f"Wenn du {jahr.group(1)} geboren bist, wirst du dieses Jahr **{jahre}** "
                f"(oder bist es schon, je nach Geburtstag).")
    if geburt > heute:
        return ""
    jahre = heute.year - geburt.year - ((heute.month, heute.day) < (geburt.month, geburt.day))
    naechster = geburt.replace(year=heute.year)
    if naechster < heute:
        naechster = naechster.replace(year=heute.year + 1)
    bis = (naechster - heute).days
    zusatz = ("Heute ist dein Geburtstag – herzlichen Glückwunsch! 🎉" if bis == 0 else
              f"Bis zum nächsten Geburtstag sind es noch {bis} Tage.")
    return f"Dann bist du **{jahre} Jahre** alt. {zusatz}"


BMI_SATZ = re.compile(r"\b(?:bmi|body\s*mass)\b.*?(\d{2,3}(?:[.,]\d)?)\s*kg.*?(\d[.,]\d{1,2}|\d{3})"
                      r"\s*(m|cm)?\b|\b(\d{2,3}(?:[.,]\d)?)\s*kg.*?(\d[.,]\d{1,2}|\d{3})\s*(m|cm)?"
                      r".*\bbmi\b")


def bmi(text: str) -> str:
    kern = falten(text)
    treffer = BMI_SATZ.search(kern)
    if not treffer:
        return ""
    kg, groesse, einheit = (treffer.group(1), treffer.group(2), treffer.group(3)) if treffer.group(
        1) else (treffer.group(4), treffer.group(5), treffer.group(6))
    meter = zahl(groesse)
    if einheit == "cm" or meter > 3:
        meter /= 100
    if not 0.5 < meter < 2.6:
        return ""
    wert = zahl(kg) / (meter * meter)
    stufe = ("Untergewicht" if wert < 18.5 else "Normalgewicht" if wert < 25 else
             "Übergewicht" if wert < 30 else "starkes Übergewicht")
    return (f"Dein BMI liegt bei **{schoen(wert, 1)}** – das gilt als {stufe}. Der BMI ist aber "
            "nur ein grober Wert: Muskeln, Alter und Körperbau zählt er nicht mit.")


TRINKGELD = re.compile(rf"(?:{ZAHL}\s*%\s*)?trinkgeld.*?{ZAHL}\s*(?:€|eur|euro)?|"
                       rf"{ZAHL}\s*(?:€|eur|euro)?.*?trinkgeld(?:.*?{ZAHL}\s*%)?")


def trinkgeld(text: str) -> str:
    kern = falten(text).replace("€", " € ")
    if "trinkgeld" not in kern:
        return ""
    zahlen = [zahl(z) for z in re.findall(r"\d[\d.,]*", kern)]
    prozent = re.search(r"(\d[\d.,]*)\s*%", kern)
    satz = zahl(prozent.group(1)) if prozent else 10.0
    betraege = [z for z in zahlen if not prozent or z != satz]
    if not betraege:
        return ("Üblich sind in Deutschland etwa 5 bis 10 % Trinkgeld. Nenn mir den Betrag, dann "
                "rechne ich es aus.")
    betrag = betraege[0]
    tg = betrag * satz / 100
    return (f"{schoen(satz)} % Trinkgeld auf {geld(betrag)} sind **{geld(tg)}** – "
            f"zusammen also **{geld(betrag + tg)}**. Aufrunden auf "
            f"{schoen(math.ceil(betrag + tg))} € geht auch.")


def geld(wert: float) -> str:
    """12,5 -> "12,50 €"."""
    return f"{wert:,.2f} €".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def passwort(text: str) -> str:
    import secrets
    import string

    kern = falten(text)
    if not re.search(r"\b(passwort|password|kennwort)\b", kern) or not re.search(
            r"\b(generier|erstell|erzeug|mach|gib|vorschlag|neues|zufaellig|sicheres)", kern):
        return ""
    laenge = re.search(r"\b(\d{1,3})\s*(?:zeichen|stellen|stellig|characters)", kern)
    n = max(12, min(64, int(laenge.group(1)))) if laenge else 20
    zeichen = string.ascii_letters + string.digits + "!@#$%&*+-=?"
    while True:
        wort = "".join(secrets.choice(zeichen) for _ in range(n))
        if (any(c.islower() for c in wort) and any(c.isupper() for c in wort)
                and any(c.isdigit() for c in wort)):
            break
    return (f"Hier ist ein zufälliges Passwort mit {n} Zeichen:\n\n`{wort}`\n\nEs wurde nur für "
            "dich erzeugt und nirgends gespeichert. Am besten legst du es gleich in einem "
            "Passwort-Manager ab.")


# -- Ein bisschen Gespraech ---------------------------------------------------------------------

LANGEWEILE = ("Wie wär's mit einem kurzen Spaziergang? Frische Luft wirkt Wunder.",
              "Lern doch heute fünf Wörter in einer neuen Sprache.",
              "Räum eine Schublade auf – das fühlt sich danach erstaunlich gut an.",
              "Schreib jemandem, von dem du lange nichts gehört hast.",
              "Probier ein neues Rezept mit dem aus, was gerade im Kühlschrank ist.",
              "Mach ein Foto von etwas Schönem in deiner Nähe.",
              "Hör ein Album komplett durch, das du noch nicht kennst.")
MUT = ("Du schaffst das. Ein Schritt nach dem anderen reicht völlig.",
       "Fehler sind kein Rückschritt, sondern ein Teil vom Weg.",
       "Denk daran, wie viel du schon geschafft hast. Das hier schaffst du auch.",
       "Es ist okay, eine Pause zu machen. Danach geht es mit frischer Kraft weiter.",
       "Kleine Fortschritte sind auch Fortschritte. Sei stolz darauf.")
FAKTEN = ("Honig verdirbt praktisch nie – in ägyptischen Gräbern fand man essbaren Honig.",
          "Ein Tag auf der Venus dauert länger als ein Jahr auf der Venus.",
          "Oktopusse haben drei Herzen und blaues Blut.",
          "Bananen sind botanisch gesehen Beeren, Erdbeeren dagegen nicht.",
          "Der Eiffelturm ist im Sommer bis zu 15 Zentimeter höher, weil sich das Eisen ausdehnt.",
          "Kühe haben beste Freundinnen und sind gestresst, wenn man sie trennt.",
          "Auf der Erde gibt es mehr Bäume als Sterne in der Milchstraße.")


def gespraech(text: str, rnd: random.Random) -> str:
    kern = falten(text)
    if re.search(r"\b(langweilig|langeweile|bored|was\s+(?:soll|kann)\s+ich\s+(?:heute\s+)?"
                 r"(?:machen|tun|unternehmen))\b", kern):
        ideen = rnd.sample(LANGEWEILE, 3)
        return ("Ich hab ein paar Ideen für dich:\n" + "\n".join(f"- {i}" for i in ideen)
                + "\n\nUnd wenn das Wetter mitspielt: Frag mich einfach, wie es draußen wird.")
    if re.search(r"\b(motivier|mut\s+machen|muntere\s+mich\s+auf|aufmuntern|bin\s+traurig|"
                 r"geht\s+es\s+mir\s+schlecht|hab\s+keine\s+lust|schaffe\s+das\s+nicht)\b", kern):
        return (rnd.choice(MUT) + "\n\nWenn es dir länger schlecht geht, rede mit jemandem, dem du "
                "vertraust. Bei der Telefonseelsorge erreichst du rund um die Uhr jemanden: "
                "0800 111 0 111 (kostenlos).")
    if re.search(r"\b(fun\s*fact|erzaehl\s+(?:mir\s+)?(?:was|etwas)\s+(?:interessantes|spannendes)|"
                 r"wusstest\s+du|interessante\s+tatsache)\b", kern):
        return "Wusstest du schon? " + rnd.choice(FAKTEN)
    if re.search(r"^(?:was\s+kannst\s+du|hilfe|help|was\s+(?:kann|koennte)\s+ich\s+dich\s+fragen|"
                 r"wie\s+funktionierst\s+du)\b", kern):
        return HILFE
    return ""


HILFE = ("Ich bin Aquaticy Standard und komme ganz ohne Sprachmodell aus. Das kann ich:\n"
         "- **Wetter:** heute, morgen, am Wochenende oder die ganze Woche – auch was du anziehen "
         "sollst, ob du einen Schirm brauchst und wann die Sonne aufgeht\n"
         "- **Rechnen:** Aufgaben, Prozente, Mehrwertsteuer, Trinkgeld, BMI und Einheiten\n"
         "- **Zeit:** Uhrzeit (auch in anderen Städten), Datum, Feiertage, Mondphase, "
         "Countdowns und dein Alter\n"
         "- **Wissen:** Nachrichten, Wechselkurse und kurze Antworten aus Wikipedia\n"
         "- **Kleinigkeiten:** Würfeln, Münzwurf, Witze, Fun Facts, Ideen gegen Langeweile und "
         "sichere Passwörter\n\n"
         "Ich merke mir auch, was du mir erzählst – zum Beispiel, wo du wohnst.")


# -- Secure Pro ---------------------------------------------------------------------------------

SICHERHEIT_TIPPS = {
    "phishing": ("**Phishing** sind gefälschte Mails, SMS oder Seiten, die an Passwörter oder Geld "
                 "wollen. So schützt du dich: Links nicht anklicken, sondern die Seite selbst "
                 "aufrufen. Absender genau prüfen. Nie Passwörter oder TANs per Mail oder Telefon "
                 "weitergeben. Zwei-Faktor-Anmeldung einschalten."),
    "passwort": ("**Gute Passwörter** sind lang (mindestens 12 Zeichen), für jeden Dienst anders "
                 "und zufällig. Am einfachsten mit einem Passwort-Manager. Schalte zusätzlich die "
                 "Zwei-Faktor-Anmeldung ein. Prüfen, ob ein Passwort geleakt ist: "
                 "[Have I Been Pwned](https://haveibeenpwned.com)."),
    "wlan": ("**WLAN sicher machen:** WPA3 oder WPA2 mit langem Passwort, WPS aus, das "
             "Router-Passwort ändern, Firmware aktuell halten, Gäste in ein eigenes Gastnetz."),
    "update": ("**Updates** schließen Sicherheitslücken. Schalte automatische Updates für System, "
               "Browser, Apps und Router ein. Geräte ohne Updates gehören nicht ins Internet."),
    "backup": ("**Backups** schützen vor Erpressersoftware: 3-2-1-Regel – drei Kopien, zwei "
               "verschiedene Speicher, eine davon außer Haus oder offline."),
}


def sicherheit(text: str) -> str:
    """Antwort aus dem festen Sicherheitswissen (aquaticy/secure_knowledge.py) -- oder ""."""
    from aquaticy import secure_knowledge

    kern = falten(text)
    for stichwort, tipp in SICHERHEIT_TIPPS.items():
        if stichwort in kern:
            return tipp
    port = re.search(r"\bport\s+(\d{1,5})\b", kern)
    worte = [w for w in re.findall(r"[a-z0-9-]{3,}", kern) if w not in {
        "was", "ist", "der", "die", "das", "wie", "bei", "mit", "und", "ich", "mein", "meine",
        "einen", "eine", "ein", "gegen", "schuetze", "schuetzen", "hilft", "port"}]
    for stichwort in ([port.group(1)] if port else []) + worte:
        try:
            treffer = secure_knowledge.lookup(stichwort)
        except Exception:
            continue
        ergebnisse = [e for e in (treffer or {}).get("results") or [] if isinstance(e, dict)]
        if not ergebnisse:
            continue
        zeilen = []
        for e in ergebnisse[:3]:
            kopf = f"**{e.get('name', '')}**" + (f" (Port {e['port']})" if e.get("port") else "")
            text_teile = [str(e[k]) for k in ("text", "signs") if e.get(k)]
            rat = e.get("hint") or e.get("defense")
            zeile = kopf + (": " + " ".join(text_teile) if text_teile else "")
            if rat:
                zeile += f" **Was tun:** {rat}"
            zeilen.append("- " + zeile)
        return "\n".join(zeilen) + "\n\n*Ein Treffer ist ein Verdacht, kein Beweis.*"
    return ""


# -- Gespraechsspeicher -------------------------------------------------------------------------

ORT_IM_TEXT = re.compile(r"\*\*(?:Heute|Morgen|Übermorgen|Das Wochenende|Die nächsten Tage|"
                         r"[A-ZÄÖÜ][a-zäöü]+, \d\d\.\d\d\.) in ([^:*]+):\*\*"
                         r"|\bin \*\*([^*]{2,40})\*\*")


def letzter_ort(verlauf: list[dict[str, Any]]) -> str:
    """Der Ort, um den es zuletzt ging -- aus den eigenen Antworten dieses Gespraechs.

    Hat der Nutzer danach gesagt, wo er wohnt, gilt das (der Wohnort kommt dann vom Aufrufer).
    """
    for eintrag in reversed(verlauf[-12:]):
        if eintrag.get("role") == "user" and re.search(
                r"\b(?:wohne|lebe)\s+(?:jetzt\s+|seit\s+\S+\s+)?in\b|\bi\s+live\s+in\b",
                falten(str(eintrag.get("content") or ""))):
            return ""
        if eintrag.get("role") != "assistant":
            continue
        treffer = ORT_IM_TEXT.search(str(eintrag.get("content") or ""))
        if treffer:
            return (treffer.group(1) or treffer.group(2)).strip()
    return ""


def letzte_wetterfrage(verlauf: list[dict[str, Any]]) -> tuple[str, int] | None:
    """Ort und Tag der letzten Wetterantwort -- fuer "und morgen?"."""
    for eintrag in reversed(verlauf[-6:]):
        if eintrag.get("role") != "assistant":
            continue
        treffer = re.search(r"\*\*(Heute|Morgen|Übermorgen) in ([^:*]+):\*\*",
                            str(eintrag.get("content") or ""))
        if treffer:
            return treffer.group(2).strip(), ("Heute", "Morgen", "Übermorgen").index(
                treffer.group(1))
    return None


def absicht(kern: str) -> str:
    """Was die Frage will -- fuer Antworten, die einen Ort brauchen."""
    if ANZIEHEN_WORT.search(kern):
        return "anziehen"
    if SCHIRM_WORT.search(kern):
        return "schirm"
    if SONNE_WORT.search(kern):
        return "sonne"
    if WETTER_WORT.search(kern):
        return "wetter"
    return ""


def offene_ortsfrage(verlauf: list[dict[str, Any]]) -> str:
    """Hat Aquaticy gerade nach dem Ort gefragt? Returns: die Frage davor -- oder ""."""
    if len(verlauf) < 2:
        return ""
    letzte = verlauf[-1]
    if letzte.get("role") != "assistant" or ORT_FRAGE not in str(letzte.get("content") or ""):
        return ""
    for eintrag in reversed(verlauf[:-1]):
        if eintrag.get("role") == "user":
            return str(eintrag.get("content") or "")
    return ""


def sieht_aus_wie_ort(text: str) -> bool:
    """"Erkelenz", "in Köln", "New York" -- kurz, ohne Fragewort und ohne Zahlenrechnung."""
    kern = falten(text)
    if not kern or len(kern) > 40 or len(kern.split()) > 4:
        return False
    if re.search(r"\b(was|wie|wer|wann|warum|wieso|weshalb|welche[rsmn]?|kannst|bitte|nein|ja|"
                 r"danke|ok|okay)\b|\d", kern):
        return False
    return bool(re.fullmatch(r"(?:in\s+|fuer\s+|nach\s+)?[a-z][a-z .\-]{1,38}", kern))


def mit_ort(art: str, ort: str, kern: str, holen: Holen, heute: date) -> str:
    """Antwortet auf eine Frage, die einen Ort braucht."""
    daten = wetterdaten(ort, holen, heute)
    if isinstance(daten, str):
        return daten
    tage = tage_aus(kern, heute)
    if art == "anziehen":
        return anziehen_text(daten, tage[0])
    if art == "schirm":
        return schirm_text(daten, tage[0])
    if art == "sonne":
        return sonne_text(daten, tage[0])
    return wetter_text(daten, tage, kern)


def ort_fragen(art: str) -> str:
    vorn = {"anziehen": "Gern helfe ich dir beim Anziehen! ",
            "schirm": "Das schaue ich gern nach! ",
            "sonne": "Gute Frage! "}.get(art, "")
    return vorn + ORT_FRAGE + ORT_BEISPIEL


# -- Zusammen -----------------------------------------------------------------------------------

def antwort(frage: str, verlauf: list[dict[str, Any]] | None = None, *, secure: bool = False,
            holen: Holen | None = None, jetzt: datetime | None = None,
            wuerfel: random.Random | None = None, wohnort: str = "",
            gemerkt: list[str] | None = None) -> str:
    """Die Antwort von Aquaticy Standard -- nie leer.

    Args:
        verlauf: das bisherige Gespraech. Daraus kennt Aquaticy Standard den zuletzt genannten
            Ort und eine offene Rueckfrage ("Fuer welchen Ort?" -> "Erkelenz").
        wohnort: aus dem Gedaechtnis oder den Einstellungen -- fuer Fragen ohne Ort.
        gemerkt: was sich Aquaticy in diesem Zug gerade gemerkt hat.
    """
    from aquaticy import zeit as zeit_mod

    holen = holen or holen_json
    verlauf = verlauf or []
    rnd = wuerfel or random.SystemRandom()
    frage = str(frage or "").strip()[:2000]
    kern = falten(frage)
    jetzt = jetzt or zeit_mod.jetzt()
    heute = jetzt.date()
    if not kern:
        return ("Frag mich ruhig etwas – zum Beispiel nach dem Wetter, einer Rechnung oder dem "
                "Datum.")
    if secure:
        text = sicherheit(frage)
        if text:
            return text + KEY_HINT
        return ("Dazu habe ich ohne Sprachmodell leider kein festes Sicherheitswissen. Frag mich "
                "nach einem Port (z. B. „Port 3389“), einem Dienst oder einer Malware." + KEY_HINT)

    # 1. Antwort auf die eigene Rueckfrage: "Fuer welchen Ort?" -> "Erkelenz"
    vorher_gefragt = offene_ortsfrage(verlauf)
    if vorher_gefragt and sieht_aus_wie_ort(frage):
        ort = re.sub(r"^(?:in|fuer|nach)\s+", "", frage.strip(" ?!.,"), flags=re.I)
        vorher_kern = falten(vorher_gefragt)
        art = absicht(vorher_kern) or "wetter"
        return mit_ort(art, ort, vorher_kern, holen, heute)

    for teil in (lambda: passwort(frage), lambda: gespraech(frage, rnd),
                 lambda: zufall(frage, wuerfel), lambda: feiertag(frage, heute),
                 lambda: mond(frage, heute), lambda: alter(frage, heute)):
        text = teil()
        if text:
            return text
    treffer = UHRZEIT_IN.search(kern)
    if treffer:
        ort = re.sub(FUELLWORTE, "", treffer.group(1)).strip(" .-")
        if ort:
            return uhrzeit_in(ort, holen, jetzt)
    for teil in (lambda: zeit(frage, jetzt), lambda: trinkgeld(frage), lambda: bmi(frage),
                 lambda: prozente(frage), lambda: einheiten(frage), lambda: rechnen(frage)):
        text = teil()
        if text:
            return text
    if re.search(r"\b(nachrichten|news|schlagzeilen|was\s+gibt\s+es\s+neues)\b", kern):
        return nachrichten(holen)
    if re.search(r"\b(kurs|wechselkurs|umrechnen)\b", kern) or WAEHRUNG_SATZ.search(kern):
        text = waehrung(frage, holen)
        if text:
            return text

    # 2. Folgefragen: "und morgen?", "und in Köln?", "und am Wochenende?"
    folge = re.fullmatch(r"(?:und\s+)?(heute|morgen|uebermorgen|am\s+wochenende|"
                         r"die\s+naechsten\s+tage|am\s+\w+)|und\s+(?:in|fuer)\s+(.+)", kern)
    vorher = letzte_wetterfrage(verlauf) or ((letzter_ort(verlauf), 0)
                                             if letzter_ort(verlauf) else None)
    if folge and vorher:
        ort = folge.group(2) or vorher[0]
        return mit_ort("wetter", ort, folge.group(1) or ("morgen" if vorher[1] == 1 else ""),
                       holen, heute)

    # 3. Alles, was einen Ort braucht: Wetter, Anziehen, Schirm, Sonne
    art = absicht(kern)
    if art:
        ort = ort_aus(kern) or letzter_ort(verlauf) or str(wohnort or "").strip()
        if not ort:
            return ort_fragen(art)
        return mit_ort(art, ort, kern, holen, heute)

    if gemerkt:
        return ("Alles klar, das merke ich mir:\n" + "\n".join(f"- {g}" for g in gemerkt[:5])
                + "\n\nIch nutze das später, zum Beispiel beim Wetter.")
    thema = thema_aus(frage)
    if thema:
        text = wissen(thema, holen)
        if text:
            return text
        return (f"Zu „{thema}“ finde ich auf Wikipedia leider nichts Passendes. Vielleicht hilft "
                "eine andere Schreibweise?" + KEY_HINT)
    return (waehle(("Hm, das kann ich ohne Sprachmodell leider nicht beantworten.",
                    "Das übersteigt leider, was ich ohne Sprachmodell kann.",
                    "Da muss ich passen – dafür bräuchte ich ein Sprachmodell."), kern)
            + " Aber frag mich gern nach dem Wetter (auch was du anziehen sollst), einer Rechnung,"
            " dem Datum, Feiertagen, Wechselkursen, Nachrichten oder Wissen aus Wikipedia. "
            "„Was kannst du?“ zeigt dir alles." + KEY_HINT)


def ist_standard(model: str) -> bool:
    return str(model or "").strip() == MODEL_ID


__all__ = ["LABEL", "MODEL_ID", "antwort", "ist_standard"]
