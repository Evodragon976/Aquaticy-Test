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
* **Folgefragen**: nach einer Wetterfrage reicht "und morgen?" oder "und in Hamburg?".
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

KEY_HINT = ("\n\n*Aquaticy Standard antwortet ohne Sprachmodell. Mit einem API-Schlüssel "
            "(Einstellungen → Add-ons) bekommst du freie Antworten auf alles.*")
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
                         r"wie\s+warm|wie\s+kalt|schnee|schneit|schneien|gewitter)\b")
ORT_NACH = re.compile(r"\b(?:in|fuer|bei|um)\s+([a-z][a-z\s.\-]{1,40}?)"
                      r"(?:\s+(?:heute|morgen|uebermorgen|am\s+wochenende))?$")
QUELLE_WETTER = "\n\nQuelle: [Open-Meteo](https://open-meteo.com)"


def tag_aus(kern: str) -> int:
    if "uebermorgen" in kern:
        return 2
    if "morgen" in kern:
        return 1
    return 0


def ort_aus(kern: str) -> str:
    treffer = ORT_NACH.search(kern)
    if not treffer:
        return ""
    ort = re.sub(r"\b(heute|morgen|uebermorgen|wetter|das|die|der|regnen|regnet|schneien|"
                 r"schneit|sonnig|warm|kalt|werden|wird|es|sein|geben)\b", "", treffer.group(1))
    return re.sub(r"\s+", " ", ort).strip(" .-")


def wetter(ort: str, tag: int, holen: Holen) -> str:
    geo = holen("https://geocoding-api.open-meteo.com/v1/search?count=1&language=de&name="
                + quote(ort))
    treffer = (geo or {}).get("results") or []
    if not treffer:
        return f"Einen Ort „{ort}“ finde ich nicht."
    stelle = treffer[0]
    name = stelle.get("name", ort)
    daten = holen("https://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&daily="
                  "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
                  "&current=temperature_2m,weather_code&timezone=Europe%2FBerlin&forecast_days=3"
                  .format(stelle.get("latitude"), stelle.get("longitude")))
    if not daten or "daily" not in daten:
        return "Das Wetter lässt sich gerade nicht abrufen."
    t = daten["daily"]
    try:
        code = int(t["weather_code"][tag])
        hoch, tief = t["temperature_2m_max"][tag], t["temperature_2m_min"][tag]
        regen = (t.get("precipitation_probability_max") or [None] * 3)[tag]
    except (KeyError, IndexError, TypeError, ValueError):
        return "Das Wetter lässt sich gerade nicht abrufen."
    wann = ("Heute", "Morgen", "Übermorgen")[tag]
    zeile = (f"**{wann} in {name}:** {WETTERCODES.get(code, 'wechselhaft')}, "
             f"{schoen(tief, 0)} bis {schoen(hoch, 0)} °C")
    if regen is not None:
        zeile += f", Regenrisiko {regen} %"
    jetzt = (daten.get("current") or {}).get("temperature_2m")
    if tag == 0 and jetzt is not None:
        zeile += f". Gerade sind es {schoen(jetzt, 0)} °C"
    tipp = ""
    if regen is not None and regen >= 60:
        tipp = " Nimm einen Schirm mit."
    elif hoch is not None and hoch >= 28:
        tipp = " Denk an Sonnencreme und Wasser."
    elif tief is not None and tief <= 0:
        tipp = " Es kann glatt werden."
    return zeile + "." + tipp + QUELLE_WETTER


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


# -- Folgefragen --------------------------------------------------------------------------------

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


# -- Zusammen -----------------------------------------------------------------------------------

def antwort(frage: str, verlauf: list[dict[str, Any]] | None = None, *, secure: bool = False,
            holen: Holen | None = None, jetzt: datetime | None = None,
            wuerfel: random.Random | None = None, wohnort: str = "",
            gemerkt: list[str] | None = None) -> str:
    """Die Antwort von Aquaticy Standard -- nie leer.

    Args:
        wohnort: aus dem Gedaechtnis oder den Einstellungen -- fuer Fragen ohne Ort.
        gemerkt: was sich Aquaticy in diesem Zug gerade gemerkt hat.
    """
    holen = holen or holen_json
    verlauf = verlauf or []
    frage = str(frage or "").strip()[:2000]
    kern = falten(frage)
    if not kern:
        return "Frag mich etwas: Rechnen, Wetter, Datum, Wechselkurse, Nachrichten oder Wissen."
    if secure:
        text = sicherheit(frage)
        if text:
            return text + KEY_HINT
        return ("Dazu habe ich ohne Sprachmodell kein festes Sicherheitswissen. Frag nach einem "
                "Port (z. B. „Port 3389“), einem Dienst oder einer Malware." + KEY_HINT)
    for teil in (lambda: zufall(frage, wuerfel), lambda: zeit(frage, jetzt),
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
    folge = re.fullmatch(r"(?:und\s+)?(heute|morgen|uebermorgen)|und\s+(?:in|fuer)\s+(.+)", kern)
    vorher = letzte_wetterfrage(verlauf)
    if folge and vorher:
        ort = folge.group(2) or vorher[0]
        tag = tag_aus(folge.group(1) or "") if folge.group(1) else vorher[1]
        return wetter(ort, tag, holen)
    if WETTER_WORT.search(kern):
        ort = ort_aus(kern) or str(wohnort or "").strip()
        if not ort:
            return "Für welchen Ort? Schreib zum Beispiel „Wetter in Berlin“."
        return wetter(ort, tag_aus(kern), holen)
    if gemerkt:
        return "Alles klar, das merke ich mir:\n" + "\n".join(f"- {g}" for g in gemerkt[:5])
    thema = thema_aus(frage)
    if thema:
        text = wissen(thema, holen)
        if text:
            return text
        return f"Zu „{thema}“ finde ich auf Wikipedia nichts Passendes." + KEY_HINT
    return ("Das kann ich ohne Sprachmodell nicht beantworten. Ich kann rechnen, umrechnen, "
            "Datum und Uhrzeit, Wetter, Wechselkurse, Nachrichten und Wissen aus Wikipedia."
            + KEY_HINT)


def ist_standard(model: str) -> bool:
    return str(model or "").strip() == MODEL_ID


__all__ = ["LABEL", "MODEL_ID", "antwort", "ist_standard"]
