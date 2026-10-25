// Weitere Faehigkeiten ohne Sprachmodell: Prozente, Einheiten, Daten und Countdowns,
// Weltzeit, Sonnenzeiten, Zufall und Uebersetzen.
//
// Jede Funktion bekommt den Text der Frage und liefert {text, schritt?} -- oder null,
// wenn die Frage nicht zu ihr gehoert. Gerechnet wird ohne eval.

import * as dienste from "./dienste.js";
import { falten } from "./sprache.js";
import { eine, sp } from "./stil.js";

const zahl = (wert, sprache = "de", stellen = 2) => Number(wert).toLocaleString(
  sprache === "en" ? "en-GB" : "de-DE", { maximumFractionDigits: stellen });
const ZAHL = String.raw`-?\d+(?:[.,]\d+)?`;
/** Geldbetraege immer mit zwei Nachkommastellen: 9,50 statt 9,5. */
const geld = (wert, sprache = "de") => Number(wert).toLocaleString(
  sprache === "en" ? "en-GB" : "de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const alsZahl = (text) => Number(String(text).replace(/(\d)\.(\d{3})(?!\d)/g, "$1$2")
  .replace(",", "."));
/** Gefaltet, ohne Satzzeichen am Ende, Tausenderpunkte ("1.000") ohne Punkt. */
const glatt = (text) => falten(text).trim().replace(/[?!.]+$/, "").trim()
  .replace(/(\d)\.(\d{3})(?!\d)/g, "$1$2");

// -- Prozente und Mehrwertsteuer ---------------------------------------------
export function prozentAntwort(text, sprache = "de") {
  const t = glatt(text);
  let m = new RegExp(`(?:wie\\s*viel(?:e)?|wieviel)\\s+prozent\\s+(?:sind|ist|macht|machen)\\s+(${ZAHL})\\s+(?:von|aus)\\s+(${ZAHL})|what\\s+percent(?:age)?\\s+(?:is|of)\\s+(${ZAHL})\\s+(?:of|from)\\s+(${ZAHL})`).exec(t);
  if (m) {
    const teil = alsZahl(m[1] ?? m[3]), ganz = alsZahl(m[2] ?? m[4]);
    if (!ganz) return { text: sp(sprache, "Von null kann man keinen Anteil ausrechnen.", "You can't take a share of zero.") };
    const p = (teil / ganz) * 100;
    return { text: sp(sprache, `${zahl(teil, sprache)} von ${zahl(ganz, sprache)} sind **${zahl(p, sprache)} %**.`,
      `${zahl(teil, sprache)} of ${zahl(ganz, sprache)} is **${zahl(p, sprache)} %**.`) };
  }
  // "200 plus 19 %", "80 € minus 25 Prozent"
  m = new RegExp(`^(?:was\\s+(?:ist|sind|macht)\\s+|wie\\s*viel\\s+(?:ist|sind)\\s+|rechne\\s+)?(${ZAHL})\\s*(?:€|euro|eur|\\$|dollar)?\\s*(plus|\\+|minus|-|abzueglich|zuzueglich|mit|ohne)\\s*(${ZAHL})\\s*(?:%|prozent|percent)(?:\\s+(?:rabatt|aufschlag|mehr|weniger))?$`).exec(t);
  if (m) {
    const basis = alsZahl(m[1]), p = alsZahl(m[3]);
    const plus = /plus|\+|zuzueglich|mit/.test(m[2]);
    const ergebnis = basis * (1 + (plus ? p : -p) / 100);
    const diff = Math.abs(ergebnis - basis);
    return { text: sp(sprache,
      `${zahl(basis, sprache)} ${plus ? "plus" : "minus"} ${zahl(p, sprache)} % sind **${zahl(ergebnis, sprache)}**. `
        + `Der Unterschied beträgt ${zahl(diff, sprache)}.`,
      `${zahl(basis, sprache)} ${plus ? "plus" : "minus"} ${zahl(p, sprache)} % is **${zahl(ergebnis, sprache)}**. `
        + `The difference is ${zahl(diff, sprache)}.`) };
  }
  // Mehrwertsteuer: "100 euro netto in brutto", "119 brutto in netto", "mwst von 50"
  const steuer = /(?:7|sieben)\s*(?:%|prozent)/.test(t) ? 7 : 19;
  m = new RegExp(`(${ZAHL})\\s*(?:€|euro|eur)?\\s*(netto|brutto)(?:\\s+(?:in|nach|zu|als)\\s+(netto|brutto))?|(?:mwst|mehrwertsteuer|umsatzsteuer|ust)\\s+(?:von|auf|fuer)\\s+(${ZAHL})|(${ZAHL})\\s*(?:€|euro|eur)?\\s+(?:mit|plus|inkl|inklusive|zzgl)\\s+(?:\\d+\\s*(?:%|prozent)\\s+)?(?:mwst|mehrwertsteuer|ust)`).exec(t);
  if (m) {
    const satz = steuer / 100;
    if (m[4] !== undefined) {
      const netto = alsZahl(m[4]);
      return { text: sp(sprache, `Auf ${geld(netto, sprache)} € netto kommen **${geld(netto * satz, sprache)} €** `
        + `Mehrwertsteuer (${steuer} %). Brutto sind das ${geld(netto * (1 + satz), sprache)} €.`,
      `On €${geld(netto, sprache)} net, German VAT (${steuer} %) is **€${geld(netto * satz, sprache)}**. `
        + `Gross: €${geld(netto * (1 + satz), sprache)}.`) };
    }
    const betrag = alsZahl(m[1] ?? m[5]);
    const vonBrutto = m[2] === "brutto" && m[3] !== "brutto";
    if (vonBrutto) {
      const netto = betrag / (1 + satz);
      return { text: sp(sprache, `${geld(betrag, sprache)} € brutto sind **${geld(netto, sprache)} € netto**. `
        + `Darin stecken ${geld(betrag - netto, sprache)} € Mehrwertsteuer (${steuer} %).`,
      `€${geld(betrag, sprache)} gross is **€${geld(netto, sprache)} net**, including `
        + `€${geld(betrag - netto, sprache)} German VAT (${steuer} %).`) };
    }
    return { text: sp(sprache, `${geld(betrag, sprache)} € netto sind **${geld(betrag * (1 + satz), sprache)} € brutto**. `
      + `Die Mehrwertsteuer (${steuer} %) beträgt ${geld(betrag * satz, sprache)} €.`,
    `€${geld(betrag, sprache)} net is **€${geld(betrag * (1 + satz), sprache)} gross**. `
      + `German VAT (${steuer} %): €${geld(betrag * satz, sprache)}.`) };
  }
  return null;
}

// -- Einheiten -----------------------------------------------------------------
// [Art, Faktor zur Grundeinheit, Name DE, Name EN]
const E = {};
const einheit = (namen, art, faktor, de, en) => {
  for (const n of namen) E[n] = { art, faktor, de, en };
};
einheit(["mm", "millimeter", "millimetern"], "laenge", 0.001, "mm", "mm");
einheit(["cm", "zentimeter", "zentimetern", "centimeter", "centimeters"], "laenge", 0.01, "cm", "cm");
einheit(["m", "meter", "metern", "metre", "metres", "meters"], "laenge", 1, "m", "m");
einheit(["km", "kilometer", "kilometern", "kilometres", "kilometers"], "laenge", 1000, "km", "km");
einheit(["zoll", "inch", "inches", "in"], "laenge", 0.0254, "Zoll", "inches");
einheit(["fuss", "feet", "foot", "ft"], "laenge", 0.3048, "Fuß", "feet");
einheit(["yard", "yards", "yd"], "laenge", 0.9144, "Yard", "yards");
einheit(["meile", "meilen", "mile", "miles", "mi"], "laenge", 1609.344, "Meilen", "miles");
einheit(["seemeile", "seemeilen", "nautical"], "laenge", 1852, "Seemeilen", "nautical miles");
einheit(["mg", "milligramm"], "masse", 1e-6, "mg", "mg");
einheit(["g", "gramm", "gram", "grams"], "masse", 0.001, "g", "g");
einheit(["kg", "kilo", "kilogramm", "kilogram", "kilograms", "kilos"], "masse", 1, "kg", "kg");
einheit(["t", "tonne", "tonnen", "tonnes"], "masse", 1000, "t", "t");
einheit(["lb", "lbs", "pound", "pounds"], "masse", 0.45359237, "lb", "lb");
einheit(["pfund"], "masse", 0.5, "Pfund", "German pounds (500 g)");
einheit(["oz", "unze", "unzen", "ounce", "ounces"], "masse", 0.028349523125, "oz", "oz");
einheit(["ml", "milliliter"], "volumen", 0.001, "ml", "ml");
einheit(["cl", "zentiliter"], "volumen", 0.01, "cl", "cl");
einheit(["dl", "deziliter"], "volumen", 0.1, "dl", "dl");
einheit(["l", "liter", "litre", "litres", "liters"], "volumen", 1, "l", "l");
einheit(["kubikmeter", "m3", "m³"], "volumen", 1000, "m³", "m³");
einheit(["gallone", "gallonen", "gallon", "gallons", "gal"], "volumen", 3.785411784, "Gallonen (US)", "US gallons");
einheit(["pint", "pints"], "volumen", 0.473176473, "Pints (US)", "US pints");
einheit(["tasse", "tassen", "cup", "cups"], "volumen", 0.2365882365, "Tassen (US)", "US cups");
einheit(["quadratmeter", "qm", "m2", "m²"], "flaeche", 1, "m²", "m²");
einheit(["quadratkilometer", "km2", "km²"], "flaeche", 1e6, "km²", "km²");
einheit(["hektar", "ha", "hectare", "hectares"], "flaeche", 1e4, "ha", "ha");
einheit(["ar"], "flaeche", 100, "Ar", "ares");
einheit(["acre", "acres"], "flaeche", 4046.8564224, "Acres", "acres");
einheit(["fussballfeld", "fussballfelder", "fussballfeldern"], "flaeche", 7140, "Fußballfelder", "football pitches");
einheit(["kmh", "km/h", "stundenkilometer", "kph"], "tempo", 1 / 3.6, "km/h", "km/h");
einheit(["m/s", "ms"], "tempo", 1, "m/s", "m/s");
einheit(["mph"], "tempo", 0.44704, "mph", "mph");
einheit(["knoten", "knots", "kn"], "tempo", 0.514444, "Knoten", "knots");
einheit(["sekunde", "sekunden", "sek", "s", "second", "seconds", "sec"], "zeit", 1, "Sekunden", "seconds");
einheit(["minute", "minuten", "min", "minutes"], "zeit", 60, "Minuten", "minutes");
einheit(["stunde", "stunden", "std", "h", "hour", "hours"], "zeit", 3600, "Stunden", "hours");
einheit(["tag", "tage", "tagen", "day", "days"], "zeit", 86400, "Tage", "days");
einheit(["woche", "wochen", "week", "weeks"], "zeit", 604800, "Wochen", "weeks");
einheit(["jahr", "jahre", "jahren", "year", "years"], "zeit", 31557600, "Jahre", "years");
einheit(["byte", "bytes", "b"], "daten", 1, "Byte", "bytes");
einheit(["kb", "kilobyte"], "daten", 1e3, "KB", "KB");
einheit(["mb", "megabyte"], "daten", 1e6, "MB", "MB");
einheit(["gb", "gigabyte"], "daten", 1e9, "GB", "GB");
einheit(["tb", "terabyte"], "daten", 1e12, "TB", "TB");
einheit(["kib", "kibibyte"], "daten", 1024, "KiB", "KiB");
einheit(["mib", "mebibyte"], "daten", 1024 ** 2, "MiB", "MiB");
einheit(["gib", "gibibyte"], "daten", 1024 ** 3, "GiB", "GiB");
const TEMPERATUR = { celsius: "C", c: "C", "°c": "C", fahrenheit: "F", f: "F", "°f": "F",
  kelvin: "K", k: "K" };

function tempUmrechnen(wert, von, nach) {
  const kelvin = von === "C" ? wert + 273.15 : von === "F" ? (wert - 32) * 5 / 9 + 273.15 : wert;
  return nach === "C" ? kelvin - 273.15 : nach === "F" ? (kelvin - 273.15) * 9 / 5 + 32 : kelvin;
}

const EINHEIT = String.raw`(?:grad\s+)?[a-z°µ²³/]+(?:\s+(?:celsius|fahrenheit))?`;

export function einheitenAntwort(text, sprache = "de") {
  const t = glatt(text).replace(/\bpro\s+stunde\b/g, "/h").replace(/km\s*\/\s*h/g, "km/h");
  const m = new RegExp(`(${ZAHL})\\s*(${EINHEIT})\\s+(?:in|nach|zu|to|into|als|=|sind\\s+wie\\s*viel(?:e)?)\\s+(${EINHEIT})$`).exec(t);
  if (!m) return null;
  const wert = alsZahl(m[1]);
  const name = (roh) => roh.replace(/^grad\s+/, "").replace(/\s+/g, " ").trim();
  let von = name(m[2]), nach = name(m[3]);
  // "Grad" allein heisst Celsius
  if (/^grad\b/.test(m[2]) && !TEMPERATUR[von]) von = "celsius";
  if (/^grad\b/.test(m[3]) && !TEMPERATUR[nach]) nach = "celsius";
  if (TEMPERATUR[von] && TEMPERATUR[nach]) {
    const a = TEMPERATUR[von], b = TEMPERATUR[nach];
    const ergebnis = tempUmrechnen(wert, a, b);
    const zeichen = (x) => (x === "K" ? " K" : ` °${x}`);
    return { text: sp(sprache, `${zahl(wert, sprache)}${zeichen(a)} sind **${zahl(ergebnis, sprache, 2)}${zeichen(b)}**.`,
      `${zahl(wert, sprache)}${zeichen(a)} is **${zahl(ergebnis, sprache, 2)}${zeichen(b)}**.`) };
  }
  const a = E[von], b = E[nach];
  if (!a || !b) return null;
  if (a.art !== b.art) {
    return { text: sp(sprache, `${a.de} und ${b.de} kann man nicht ineinander umrechnen – das eine ist `
      + "eine andere Größe als das andere.", `You can't convert ${a.en} into ${b.en} – they measure different things.`) };
  }
  const ergebnis = (wert * a.faktor) / b.faktor;
  const stellen = Math.abs(ergebnis) >= 100 ? 2 : Math.abs(ergebnis) >= 1 ? 3 : 6;
  return { text: sp(sprache, `${zahl(wert, sprache)} ${a.de} sind **${zahl(ergebnis, sprache, stellen)} ${b.de}**.`,
    `${zahl(wert, sprache)} ${a.en} is **${zahl(ergebnis, sprache, stellen)} ${b.en}**.`) };
}

// -- Daten und Countdowns ----------------------------------------------------------
const MONATE = { januar: 1, jan: 1, january: 1, februar: 2, feb: 2, february: 2, maerz: 3,
  mrz: 3, march: 3, mar: 3, april: 4, apr: 4, mai: 5, may: 5, juni: 6, jun: 6, june: 6, juli: 7,
  jul: 7, july: 7, august: 8, aug: 8, september: 9, sep: 9, sept: 9, oktober: 10, okt: 10,
  october: 10, oct: 10, november: 11, nov: 11, dezember: 12, dez: 12, december: 12, dec: 12 };

/** Ostersonntag nach dem gregorianischen Kalender (Algorithmus von Meeus/Jones/Butcher). */
export function ostern(jahr) {
  const a = jahr % 19, b = Math.floor(jahr / 100), c = jahr % 100;
  const d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const monat = Math.floor((h + l - 7 * m + 114) / 31), tag = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(Date.UTC(jahr, monat - 1, tag));
}

const tagNach = (datum, tage) => new Date(datum.getTime() + tage * 86400000);
const nterSonntag = (jahr, monat, n) => {
  const erster = new Date(Date.UTC(jahr, monat - 1, 1));
  return tagNach(erster, ((7 - erster.getUTCDay()) % 7) + (n - 1) * 7);
};

// Namen besonderer Tage -> Datum in einem Jahr
const ANLAESSE = [
  [/heiligabend|christmas\s+eve/, "Heiligabend", "Christmas Eve", (j) => new Date(Date.UTC(j, 11, 24))],
  [/weihnachten|christmas/, "Weihnachten (Heiligabend)", "Christmas", (j) => new Date(Date.UTC(j, 11, 24))],
  [/silvester|new\s+year'?s\s+eve/, "Silvester", "New Year's Eve", (j) => new Date(Date.UTC(j, 11, 31))],
  [/neujahr|new\s+year/, "Neujahr", "New Year's Day", (j) => new Date(Date.UTC(j, 0, 1))],
  [/ostern|easter/, "Ostern", "Easter", (j) => ostern(j)],
  [/pfingsten|pentecost/, "Pfingsten", "Pentecost", (j) => tagNach(ostern(j), 49)],
  [/himmelfahrt|vatertag|ascension/, "Christi Himmelfahrt (Vatertag)", "Ascension Day", (j) => tagNach(ostern(j), 39)],
  [/muttertag|mother'?s\s+day/, "Muttertag", "Mother's Day (Germany)", (j) => nterSonntag(j, 5, 2)],
  [/halloween/, "Halloween", "Halloween", (j) => new Date(Date.UTC(j, 9, 31))],
  [/valentinstag|valentine/, "Valentinstag", "Valentine's Day", (j) => new Date(Date.UTC(j, 1, 14))],
  [/nikolaus/, "Nikolaus", "St Nicholas' Day", (j) => new Date(Date.UTC(j, 11, 6))],
  [/tag\s+der\s+deutschen\s+einheit/, "Tag der Deutschen Einheit", "German Unity Day", (j) => new Date(Date.UTC(j, 9, 3))],
  [/fruehlingsanfang|fruehling/, "Frühlingsanfang (etwa)", "start of spring (approx.)", (j) => new Date(Date.UTC(j, 2, 20))],
  [/sommeranfang|sommer\b/, "Sommeranfang (etwa)", "start of summer (approx.)", (j) => new Date(Date.UTC(j, 5, 21))],
  [/herbstanfang|herbst\b/, "Herbstanfang (etwa)", "start of autumn (approx.)", (j) => new Date(Date.UTC(j, 8, 23))],
  [/winteranfang|winter\b/, "Winteranfang (etwa)", "start of winter (approx.)", (j) => new Date(Date.UTC(j, 11, 21))],
];

/** Ein Datum aus "24.12.", "3.10.1990", "1. mai 2027", "may 1", "2027-03-28". */
export function datumAus(t, jetztJahr) {
  let m = /\b(\d{4})-(\d{1,2})-(\d{1,2})\b/.exec(t);
  if (m) return { datum: new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])), mitJahr: true };
  m = /\b(\d{1,2})\.\s*(\d{1,2})(?:\.(?:\s*(\d{4}|\d{2}(?!\d)))?|(?=\s|$))/.exec(t);
  if (m) {
    const jahr = m[3] ? (m[3].length === 2 ? 2000 + Number(m[3]) : Number(m[3])) : jetztJahr;
    return { datum: new Date(Date.UTC(jahr, +m[2] - 1, +m[1])), mitJahr: Boolean(m[3]) };
  }
  m = /\b(\d{1,2})\.?\s+([a-z]+)(?:\s+(\d{4}))?\b/.exec(t);
  if (m && MONATE[m[2]]) {
    return { datum: new Date(Date.UTC(m[3] ? +m[3] : jetztJahr, MONATE[m[2]] - 1, +m[1])), mitJahr: Boolean(m[3]) };
  }
  m = /\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b/.exec(t);
  if (m && MONATE[m[1]]) {
    return { datum: new Date(Date.UTC(m[3] ? +m[3] : jetztJahr, MONATE[m[1]] - 1, +m[2])), mitJahr: Boolean(m[3]) };
  }
  return null;
}

const gueltig = (d) => d instanceof Date && !Number.isNaN(d.getTime());

export function datumAntwort(text, sprache = "de", jetzt = new Date()) {
  const t = glatt(text);
  const loc = sprache === "en" ? "en-GB" : "de-DE";
  const zeig = (d) => d.toLocaleDateString(loc, { weekday: "long", day: "numeric", month: "long",
    year: "numeric", timeZone: "UTC" });
  const heute = new Date(Date.UTC(jetzt.getUTCFullYear(), jetzt.getUTCMonth(), jetzt.getUTCDate()));
  // Countdown: "wie viele Tage bis Weihnachten", "wie lange noch bis zum 1. mai"
  let m = /(?:wie\s*(?:viele|lange)\s+(?:tage\s+)?(?:(?:ist\s+es\s+|sind\s+es\s+|dauert\s+es\s+)?noch\s+)?bis|how\s+(?:many\s+days|long)\s+(?:is\s+it\s+)?(?:until|till|to)|countdown\s+(?:bis|to)|tage\s+bis)\s+(?:zu[mr]?\s+|zu\s+)?(.+)$/.exec(t);
  if (m) {
    const ziel = m[1];
    let datum = null, name = "", istDatum = false;
    for (const [muster, de, en, rechnen] of ANLAESSE) {
      if (muster.test(ziel)) {
        datum = rechnen(heute.getUTCFullYear());
        if (datum < heute) datum = rechnen(heute.getUTCFullYear() + 1);
        name = sp(sprache, de, en);
        break;
      }
    }
    if (!datum) {
      const gefunden = datumAus(ziel, heute.getUTCFullYear());
      if (gefunden && gueltig(gefunden.datum)) {
        datum = gefunden.datum;
        if (!gefunden.mitJahr && datum < heute) {
          datum = new Date(Date.UTC(datum.getUTCFullYear() + 1, datum.getUTCMonth(), datum.getUTCDate()));
        }
        name = zeig(datum);
        istDatum = true;
      }
    }
    if (!datum) {
      if (/geburtstag|birthday/.test(ziel)) {
        return { text: sp(sprache, "Wann hast du Geburtstag? Schreib zum Beispiel: *Wie viele Tage bis zum 14.3.?*",
          "When is your birthday? For example, write: *How many days until March 14?*") };
      }
      return null;
    }
    const tage = Math.round((datum - heute) / 86400000);
    if (tage === 0) return { text: sp(sprache, `${name} ist **heute**! 🎉`, `${name} is **today**! 🎉`) };
    if (tage < 0) {
      return { text: sp(sprache, `Der ${name} war vor **${zahl(-tage, sprache)} Tagen**.`,
        `${name} was **${zahl(-tage, sprache)} days** ago.`) };
    }
    const wochen = tage >= 14 ? sp(sprache, ` – gut ${Math.floor(tage / 7)} Wochen`,
      ` – about ${Math.floor(tage / 7)} weeks`) : "";
    const wann = istDatum ? "" : ` (${zeig(datum)})`;
    const tagWort = sp(sprache, tage === 1 ? "Tag" : "Tage", tage === 1 ? "day" : "days");
    return { text: sp(sprache,
      `Bis ${istDatum ? "zum " : ""}${name} sind es noch **${zahl(tage, sprache)} ${tagWort}**${wochen}.${wann}`,
      `**${zahl(tage, sprache)} ${tagWort}** to go until ${name}${wochen}.${wann}`) };
  }
  // Wochentag eines Datums: "welcher wochentag war der 3.10.1990", "what day was july 4 1776"
  m = /(?:welche[rn]?\s+(?:wochen)?tag\s+(?:ist|war|wird|faellt)|what\s+day\s+(?:of\s+the\s+week\s+)?(?:is|was|will\s+be))\s+(?:der|am|on)?\s*(.+)$/.exec(t);
  if (m) {
    const ostern2 = /ostern|easter/.test(m[1]);
    const jahr = /\b(\d{4})\b/.exec(m[1]);
    const gefunden = ostern2
      ? { datum: ostern(jahr ? +jahr[1] : heute.getUTCFullYear()) }
      : datumAus(m[1], heute.getUTCFullYear());
    if (!gefunden || !gueltig(gefunden.datum)) return null;
    const war = gefunden.datum < heute;
    return { text: sp(sprache, `Der ${gefunden.datum.toLocaleDateString(loc, { day: "numeric", month: "long",
      year: "numeric", timeZone: "UTC" })} ${war ? "war" : "ist"} ein **${gefunden.datum.toLocaleDateString(loc,
      { weekday: "long", timeZone: "UTC" })}**.`, `${gefunden.datum.toLocaleDateString(loc, { day: "numeric",
      month: "long", year: "numeric", timeZone: "UTC" })} ${war ? "was" : "is"} a **${gefunden.datum
      .toLocaleDateString(loc, { weekday: "long", timeZone: "UTC" })}**.`) };
  }
  // Tage seit einem Datum: "wie viele tage seit dem 1.1.2020"
  m = /(?:wie\s*viele\s+tage\s+(?:sind\s+(?:es\s+)?|ist\s+es\s+)?(?:seit|her\s+seit)|how\s+many\s+days\s+since)\s+(?:dem\s+)?(.+)$/.exec(t);
  if (m) {
    const gefunden = datumAus(m[1], heute.getUTCFullYear());
    if (!gefunden || !gueltig(gefunden.datum)) return null;
    const tage = Math.round((heute - gefunden.datum) / 86400000);
    return { text: sp(sprache, `Seit dem ${zeig(gefunden.datum)} sind **${zahl(tage, sprache)} Tage** vergangen.`,
      `**${zahl(tage, sprache)} days** have passed since ${zeig(gefunden.datum)}.`) };
  }
  return null;
}

// -- Weltzeit und Sonne ----------------------------------------------------------
const DIENST_WEG = (sprache) => sp(sprache, "Der Ortsdienst antwortet gerade nicht. Versuch es gleich "
  + "noch einmal.", "The place lookup isn't answering right now. Try again in a moment.");
const ORT_ENDE = /\s+(?:heute|morgen|jetzt|gerade|today|tomorrow|now)$/;

export async function weltzeitAntwort(text, sprache, kontext) {
  const t = glatt(text);
  const m = /(?:wie\s*spaet\s+ist\s+es|wie\s*viel\s+uhr\s+ist\s+es|uhrzeit|what\s+time\s+is\s+it|time)\s+(?:gerade\s+|jetzt\s+)?(?:in|im|auf|bei|in\s+der|in\s+den)\s+(.{2,60})$/.exec(t);
  if (!m) return null;
  const roh = String(text).trim().replace(/[?!.]+$/, "").split(/\s+/);
  const name = roh.slice(roh.length - m[1].split(/\s+/).length).join(" ").replace(ORT_ENDE, "");
  const schritt = { type: "search", query: sp(sprache, `Uhrzeit ${name}`, `time ${name}`) };
  const platz = await dienste.ort(name, sprache, kontext.holen);
  if (platz?.fehler) return { schritt, text: DIENST_WEG(sprache) };
  if (!platz || !platz.zeitzone) {
    return { schritt, text: sp(sprache, `Einen Ort „${name}“ finde ich gerade nicht.`,
      `I can't find a place called “${name}” right now.`) };
  }
  const loc = sprache === "en" ? "en-GB" : "de-DE";
  const jetzt = kontext.jetzt || new Date();
  let uhr, tag, eigenerTag;
  try {
    uhr = jetzt.toLocaleTimeString(loc, { timeZone: platz.zeitzone, hour: "2-digit", minute: "2-digit" });
    tag = jetzt.toLocaleDateString(loc, { timeZone: platz.zeitzone, weekday: "long" });
    eigenerTag = jetzt.toLocaleDateString(loc, { timeZone: kontext.zeitzone || "Europe/Berlin", weekday: "long" });
  } catch {
    return null;
  }
  const anderer = tag !== eigenerTag ? sp(sprache, ` Dort ist schon bzw. noch ${tag}.`, ` It's ${tag} there.`) : "";
  return { schritt, text: sp(sprache, `In **${platz.name}** ist es gerade **${uhr} Uhr**.${anderer}`,
    `In **${platz.name}** it's **${uhr}** right now.${anderer}`) };
}

export async function sonneAntwort(text, sprache, kontext) {
  const t = glatt(text);
  if (!/sonne\w*\s+(?:auf|unter)|sonnen(?:aufgang|untergang)|wann\s+wird\s+es\s+(?:hell|dunkel)|sunrise|sunset|sun\s+(?:rise|set)/.test(t)) {
    return null;
  }
  const m = /\b(?:in|im|fuer|bei|for|at)\s+([\p{L}][\p{L}\s.'-]{1,50})$/u.exec(String(text).trim()
    .replace(/[?!.]+$/, "").replace(/\s+(?:heute|morgen|today|tomorrow)$/i, ""));
  let name = m ? m[1].trim() : "";
  let naeherung = false;
  if (!name && kontext.stadt) { name = kontext.stadt; naeherung = true; }
  if (!name) {
    return { text: sp(sprache, "Für welchen Ort? Schreib zum Beispiel: *Sonnenuntergang in Hamburg*.",
      "For which place? For example: *sunset in London*.") };
  }
  const schritt = { type: "search", query: sp(sprache, `Sonne ${name}`, `sun ${name}`) };
  const platz = await dienste.ort(name, sprache, kontext.holen);
  if (platz?.fehler) return { schritt, text: DIENST_WEG(sprache) };
  if (!platz) {
    return { schritt, text: sp(sprache, `Einen Ort „${name}“ finde ich gerade nicht.`,
      `I can't find a place called “${name}” right now.`) };
  }
  const tage = await dienste.sonne(platz, kontext.holen);
  const nr = /morgen|tomorrow/.test(t) && !/heute\s+morgen/.test(t) ? 1 : 0;
  const tag = tage?.[nr];
  if (!tag?.auf) {
    return { schritt, text: sp(sprache, "Die Sonnenzeiten lassen sich gerade nicht laden.",
      "Sunrise and sunset times can't be loaded right now.") };
  }
  const uhr = (iso) => iso.slice(11, 16);
  const wann = nr ? sp(sprache, "Morgen", "Tomorrow") : sp(sprache, "Heute", "Today");
  const wo = naeherung ? sp(sprache, `in deiner Nähe (${platz.name}, geschätzt)`, `near you (${platz.name}, estimated)`)
    : sp(sprache, `in ${platz.name}`, `in ${platz.name}`);
  return { schritt, text: sp(sprache, `${wann} ${wo}: Sonnenaufgang um **${uhr(tag.auf)} Uhr**, `
    + `Sonnenuntergang um **${uhr(tag.unter)} Uhr** (Ortszeit).`, `${wann} ${wo}: sunrise at **${uhr(tag.auf)}**, `
    + `sunset at **${uhr(tag.unter)}** (local time).`)
    + sp(sprache, "\n\nQuelle: [Open-Meteo](https://open-meteo.com)", "\n\nSource: [Open-Meteo](https://open-meteo.com)") };
}

// -- Zufall --------------------------------------------------------------------
export function zufallAntwort(text, sprache = "de", zufall = Math.random) {
  const t = glatt(text);
  const ganz = (von, bis) => von + Math.floor(zufall() * (bis - von + 1));
  if (/^(?:bitte\s+)?(?:wuerfel|wuerfle|wuerfeln|wuerfel\s+mal|wirf\s+(?:mal\s+)?(?:einen|zwei|drei|\d+)\s+wuerfel|roll\s+(?:a\s+|the\s+|two\s+|\d+\s+)?(?:die|dice))\b/.test(t)) {
    const anzahl = Math.min(10, Math.max(1, Number((/\b(\d+|zwei|drei|two|three)\s+wuerfel|(\d+)\s+dice/.exec(t) || [])[1]
      ?.replace(/zwei|two/, "2").replace(/drei|three/, "3")) || 1));
    const wuerfe = Array.from({ length: anzahl }, () => ganz(1, 6));
    const summe = wuerfe.reduce((a, b) => a + b, 0);
    return { text: `🎲 ${wuerfe.map((w) => `**${w}**`).join(" + ")}${anzahl > 1 ? ` = **${summe}**` : ""}` };
  }
  if (/(?:wirf|werfe|wirfst|flip|toss)\s+(?:mal\s+)?(?:eine\s+|a\s+)?(?:muenze|coin)|kopf\s+oder\s+zahl|heads\s+or\s+tails|muenzwurf/.test(t)) {
    const seite = zufall() < 0.5;
    return { text: sp(sprache, `🪙 **${seite ? "Kopf" : "Zahl"}**!`, `🪙 **${seite ? "Heads" : "Tails"}**!`) };
  }
  let m = /(?:zufallszahl|zufaellige\s+zahl|random\s+number|zahl\s+zwischen)(?:\s+(?:zwischen|von|between|from)\s+(-?\d+)\s+(?:und|bis|and|to)\s+(-?\d+))?/.exec(t);
  if (m) {
    let a = m[1] !== undefined ? Number(m[1]) : 1, b = m[2] !== undefined ? Number(m[2]) : 100;
    if (a > b) [a, b] = [b, a];
    if (b - a > 1e12) return null;
    return { text: sp(sprache, `Deine Zufallszahl zwischen ${a} und ${b}: **${ganz(a, b)}**`,
      `Your random number between ${a} and ${b}: **${ganz(a, b)}**`) };
  }
  // Die Wahl im Original (Gross-/Kleinschreibung), nicht gefaltet
  m = /^(?:soll\s+ich|sollte\s+ich|should\s+i)\s+(.+?)\s+(?:oder|or)\s+(.+?)$/iu
    .exec(String(text).trim().replace(/[?!.]+$/, ""));
  if (m) {
    const wahl = zufall() < 0.5 ? m[1] : m[2];
    return { text: sp(sprache, `Ich würde sagen: **${wahl}**! 😉 (Ehrlich gesagt hat das der Zufall entschieden – `
      + "du kennst dich selbst am besten.)", `I'd say: **${wahl}**! 😉 (Honestly, chance decided – you know `
      + "yourself best.)") };
  }
  return null;
}

// -- Uebersetzen ------------------------------------------------------------------
const SPRACHEN = { englisch: "en", english: "en", deutsch: "de", german: "de", franzoesisch: "fr",
  french: "fr", spanisch: "es", spanish: "es", italienisch: "it", italian: "it", tuerkisch: "tr",
  turkish: "tr", niederlaendisch: "nl", hollaendisch: "nl", dutch: "nl", polnisch: "pl",
  polish: "pl", portugiesisch: "pt", portuguese: "pt", russisch: "ru", russian: "ru",
  ukrainisch: "uk", ukrainian: "uk", arabisch: "ar", arabic: "ar", chinesisch: "zh",
  chinese: "zh", japanisch: "ja", japanese: "ja", griechisch: "el", greek: "el",
  schwedisch: "sv", swedish: "sv", daenisch: "da", danish: "da", norwegisch: "no",
  norwegian: "no", tschechisch: "cs", czech: "cs", kroatisch: "hr", croatian: "hr",
  latein: "la", latin: "la", koreanisch: "ko", korean: "ko", finnisch: "fi", finnish: "fi",
  ungarisch: "hu", hungarian: "hu", rumaenisch: "ro", romanian: "ro" };
const SPRACHNAME = { en: ["Englisch", "English"], de: ["Deutsch", "German"], fr: ["Französisch",
  "French"], es: ["Spanisch", "Spanish"], it: ["Italienisch", "Italian"] };

function spracheAus(wort) {
  const w = falten(wort).replace(/[^a-z]/g, "");
  for (const [name, code] of Object.entries(SPRACHEN)) {
    if (w === name || w.startsWith(name)) return code;   // "englische", "ins englische"
  }
  return "";
}

export async function uebersetzenAntwort(text, sprache, kontext) {
  const roh = String(text).trim().replace(/[?!.]+$/, "");
  const muster = [
    /^(?:was|wie)\s+(?:hei(?:ß|ss)t|bedeutet|sagt\s+man|sage\s+ich|schreibt\s+man)\s+[„"'»]?(.+?)[“"'«]?\s+(?:auf|in|im)\s+([\p{L}]+)$/iu,
    /^(?:übersetz\w*|uebersetz\w*)\s+(?:mir\s+)?(?:bitte\s+)?[„"'»]?(.+?)[“"'«]?\s+(?:ins|in|auf|nach)\s+(?:das\s+)?([\p{L}]+)$/iu,
    /^(?:translate)\s+["']?(.+?)["']?\s+(?:to|into)\s+([\p{L}]+)$/iu,
    /^how\s+do\s+(?:you|i)\s+say\s+["']?(.+?)["']?\s+in\s+([\p{L}]+)$/iu,
  ];
  let m = null;
  for (const re of muster) { m = re.exec(roh); if (m) break; }
  if (!m) return null;
  const nach = spracheAus(m[2]);
  if (!nach) return null;
  const quelle = m[1].trim();
  const von = nach === "de" ? "en" : (kontext.quellSprache || "de");
  const schritt = { type: "search", query: sp(sprache, `Übersetzung → ${nach}`, `translation → ${nach}`) };
  const ergebnis = await dienste.uebersetzen(quelle, von, nach, kontext.holen);
  if (!ergebnis) {
    return { schritt, text: sp(sprache, "Die Übersetzung klappt gerade nicht. Versuch es gleich noch einmal.",
      "Translation isn't working right now. Try again in a moment.") };
  }
  const name = SPRACHNAME[nach] ? sp(sprache, SPRACHNAME[nach][0], SPRACHNAME[nach][1]) : nach.toUpperCase();
  return { schritt, text: sp(sprache, `„${quelle}“ heißt auf ${name}: **${ergebnis}**`,
    `“${quelle}” in ${name}: **${ergebnis}**`) + sp(sprache,
    "\n\nQuelle: [MyMemory](https://mymemory.translated.net) – maschinelle Übersetzung, kann danebenliegen.",
    "\n\nSource: [MyMemory](https://mymemory.translated.net) – machine translation, may be off.") };
}

// -- Gespraech: mehr als Hallo und Danke ------------------------------------------
const FAKTEN = {
  de: ["Ein Tag auf der Venus dauert länger als ein ganzes Venusjahr: Sie dreht sich in rund 243 Erdtagen "
    + "einmal um sich selbst, braucht für eine Runde um die Sonne aber nur etwa 225.",
  "Oktopusse haben drei Herzen und blaues Blut.",
  "Bananen sind botanisch gesehen Beeren – Erdbeeren dagegen nicht.",
  "Wombats machen würfelförmigen Kot. So rollt er nicht weg.",
  "Haie gab es schon, bevor es Bäume gab – rund 50 Millionen Jahre früher.",
  "Ein Blitz ist etwa fünfmal heißer als die Oberfläche der Sonne.",
  "Honig verdirbt praktisch nie. In alten ägyptischen Gräbern fand man jahrtausendealten Honig."],
  en: ["A day on Venus is longer than a year on Venus: it takes about 243 Earth days to turn once, "
    + "but only about 225 to orbit the Sun.", "Octopuses have three hearts and blue blood.",
  "Botanically, bananas are berries – strawberries aren't.", "Wombats produce cube-shaped poop.",
  "Sharks existed before trees – by roughly 50 million years.",
  "A lightning bolt is about five times hotter than the surface of the Sun."],
};
const MUT = {
  de: ["Kleine Schritte zählen auch. Hauptsache, du gehst los.",
    "Du musst nicht perfekt sein, um anzufangen – aber du musst anfangen, um besser zu werden.",
    "Heute ist ein guter Tag, um etwas zu schaffen, auf das du morgen stolz bist.",
    "Fehler sind Beweise dafür, dass du es versuchst.",
    "Eins nach dem anderen. Du schaffst das!"],
  en: ["Small steps count too. What matters is that you start.",
    "You don't have to be perfect to start – but you have to start to get better.",
    "Mistakes are proof that you're trying.", "One thing at a time. You've got this!"],
};
const IDEEN_ESSEN = {
  de: ["Wie wär's mit **Pfannkuchen**? Geht schnell und schmeckt süß wie herzhaft.",
    "Ein **Gemüse-Curry** mit Reis – lecker und gut für Reste.", "**Spaghetti aglio e olio**: "
    + "Knoblauch, Olivenöl, Chili, fertig in 15 Minuten.", "Eine **Ofenkartoffel** mit Kräuterquark.",
  "**Shakshuka** – Eier in Tomatensoße, dazu frisches Brot."],
  en: ["How about **pancakes**? Quick, and they work sweet or savoury.", "A **vegetable curry** with "
    + "rice – tasty and great for leftovers.", "**Spaghetti aglio e olio**: garlic, olive oil, chilli, "
    + "done in 15 minutes.", "**Shakshuka** – eggs in tomato sauce with fresh bread."],
};

export function gespraechMehr(kern, sprache, zufall) {
  const s = (de, en) => sp(sprache, de, en);
  if (/^(?:ich\s+(?:haette|habe|hab)\s+(?:mal\s+)?(?:eine|ne|'ne)\s+frage|(?:darf|kann)\s+ich\s+(?:dich\s+)?(?:mal\s+)?(?:was|etwas)\s+fragen|(?:nur\s+)?(?:eine\s+)?kurze\s+frage|eine\s+frage|frage|i\s+have\s+a\s+question|can\s+i\s+ask\s+(?:you\s+)?something)$/.test(kern)) {
    return eine([s("Klar, schieß los!", "Sure, go ahead!"), s("Na klar – frag einfach.", "Of course – just ask.")],
      `frage:${sprache}`, zufall);
  }
  if (/^(?:kannst\s+du\s+mir\s+(?:bitte\s+)?helfen|hilf\s+mir(?:\s+bitte)?|ich\s+brauche\s+hilfe|can\s+you\s+help\s+me|help\s+me)$/.test(kern)) {
    return s("Na klar! Worum geht's? Erzähl mir kurz, was du brauchst.", "Of course! What do you need?");
  }
  if (/fun\s*fact|erzaehl\s+(?:mir\s+)?(?:etwas|was)\s+(?:interessantes|spannendes|lustiges|neues)|wusstest\s+du|ueberrasch\s+mich|interesting\s+fact|tell\s+me\s+something\s+interesting|random\s+fact/.test(kern)) {
    return s("Wusstest du schon? ", "Did you know? ") + eine(FAKTEN[sprache], `fakt:${sprache}`, zufall);
  }
  if (/motivier\w*|motivation|aufmuntern|muntere\s+mich\s+auf|spruch\s+des\s+tages|motivate\s+me|cheer\s+me\s+up|inspire\s+me/.test(kern)) {
    return `💪 ${eine(MUT[sprache], `mut:${sprache}`, zufall)}`;
  }
  if (/^(?:was\s+soll\s+ich\s+(?:heute\s+)?(?:kochen|essen)|was\s+(?:koche|esse)\s+ich\s+heute|ich\s+weiss\s+nicht\s+was\s+ich\s+(?:kochen|essen)\s+soll|what\s+should\s+i\s+(?:cook|eat))/.test(kern)) {
    return eine(IDEEN_ESSEN[sprache], `essen:${sprache}`, zufall)
      + s(" Frag mich gern nach einem Gericht, dann erkläre ich es dir.", " Ask me about a dish and I'll explain it.");
  }
  if (/^(?:(?:ha|hi|he){2,}h?|lol+|lach\w*|xd+|rofl|😂|🤣)+$/u.test(kern.replace(/\s+/g, ""))) {
    return s("😄 Freut mich, dass ich dich zum Lachen bringe!", "😄 Glad I made you laugh!");
  }
  if (/^(?:warum|wieso|weshalb|why)$/.test(kern)) {
    return s("Wobei genau? Schreib mir die ganze Frage, dann suche ich die Antwort.",
      "About what exactly? Write the whole question and I'll look it up.");
  }
  if (/^(?:ja|jo|jep|jup|nein|ne|nee|noe|vielleicht|yes|yeah|no|nope|maybe)$/.test(kern)) {
    return s("Alles klar. Was möchtest du als Nächstes wissen?", "Alright. What would you like to know next?");
  }
  return "";
}
