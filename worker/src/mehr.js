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
  // Die Zahlen vor der Frage (16.4.5): "80 von 200 sind wie viel Prozent?", "80 ist wie viel
  // Prozent von 200?"
  m = m || new RegExp(`(${ZAHL})\\s+(?:von|aus)\\s+(${ZAHL})\\s+(?:sind|ist|macht)\\s+(?:wie\\s*viel(?:e)?|wieviel)\\s+prozent`).exec(t)
    || (() => {
      const r = new RegExp(`(${ZAHL})\\s+(?:ist|sind|macht)\\s+(?:wie\\s*viel(?:e)?|wieviel)\\s+prozent\\s+(?:von|aus)\\s+(${ZAHL})`).exec(t);
      return r;
    })();
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
const E = Object.create(null);
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
einheit(["ml", "milliliter", "millilitern"], "volumen", 0.001, "ml", "ml");
einheit(["cl", "zentiliter"], "volumen", 0.01, "cl", "cl");
einheit(["dl", "deziliter"], "volumen", 0.1, "dl", "dl");
einheit(["l", "liter", "litern", "litre", "litres", "liters"], "volumen", 1, "l", "l");
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
/** Einzahl der deutschen Namen fuer "1 Stunde ist ...". */
const EINZAHL = { __proto__: null,
  Sekunden: "Sekunde", Minuten: "Minute", Stunden: "Stunde", Tage: "Tag",
  Wochen: "Woche", Jahre: "Jahr", Meilen: "Meile", "Gallonen (US)": "Gallone (US)",
  "Pints (US)": "Pint (US)", "Tassen (US)": "Tasse (US)", Acres: "Acre",
  Fußballfelder: "Fußballfeld", Seemeilen: "Seemeile", Unzen: "Unze", Pfund: "Pfund",
  Zoll: "Zoll", Fuß: "Fuß", Yards: "Yard", Knoten: "Knoten" };
const TEMPERATUR = { __proto__: null,
  celsius: "C", c: "C", "°c": "C", fahrenheit: "F", f: "F", "°f": "F",
  kelvin: "K", k: "K" };

function tempUmrechnen(wert, von, nach) {
  const kelvin = von === "C" ? wert + 273.15 : von === "F" ? (wert - 32) * 5 / 9 + 273.15 : wert;
  return nach === "C" ? kelvin - 273.15 : nach === "F" ? (kelvin - 273.15) * 9 / 5 + 32 : kelvin;
}

const EINHEIT = String.raw`(?:grad\s+)?[a-z°µ²³/]+(?:\s+(?:celsius|fahrenheit))?`;

export function einheitenAntwort(text, sprache = "de") {
  // 16.4.5: "3 Fuß 6 Zoll in cm" rechnete vorher nur die 6 Zoll; "ein Zoll in cm" ging nicht.
  const t = glatt(text).replace(/\bpro\s+stunde\b/g, "/h").replace(/km\s*\/\s*h/g, "km/h")
    // 17.1.1: auch "degrees" und "5 feet 10 inches" (vorher nur die 10 Zoll).
    .replace(/\bdegrees?\s+(?=celsius|fahrenheit|kelvin|c\b|f\b)/g, "grad ")
    .replace(/(\d+(?:[.,]\d+)?)\s*(?:fuss|feet|foot|ft|')\s*(\d+(?:[.,]\d+)?)\s*(?:zoll|inches|inch|")/g,
      (_, a, b) => String(Number(a.replace(",", ".")) * 12 + Number(b.replace(",", "."))).replace(".", ",") + " zoll")
    .replace(/^(?:wie\s*viel\s+(?:ist|sind)\s+)?ein(?:e|en|em)?\s+(?=\S+\s+(?:in|nach|zu|to)\s)/, "1 ");
  // 16.4.5: "Wie viele Gramm sind ein Pfund?", "How many feet in a mile?" -- die Frage nach
  // vorn gestellt; Python konnte das schon.
  const vorn = new RegExp(`^(?:wie\\s*viele?|how\\s+many)\\s+(${EINHEIT})\\s+(?:sind|ist|hat|haben|ergeben|machen|are|is|in)\\s+(?:(${ZAHL})|ein(?:e|en|em)?|one|an?)\\s*(${EINHEIT})$`).exec(t);
  const umgestellt = vorn ? `${vorn[2] || "1"} ${vorn[3]} in ${vorn[1]}` : t;
  // 16.4.5: "3 Stunden 20 Minuten in Minuten" -- vorher "20 Minuten sind 20 Minuten".
  const dauer = /^(?:(\d+(?:[.,]\d+)?)\s*(?:stunden?|std|h|hours?)\s+(?:und\s+|and\s+)?)?(?:(\d+(?:[.,]\d+)?)\s*(?:minuten?|min|minutes?)\s*(?:und\s+|and\s+)?)?(?:(\d+(?:[.,]\d+)?)\s*(?:sekunden?|sek|s|seconds?))?\s+(?:in|nach|zu|to|into)\s+(stunden?|h|minuten?|min|sekunden?|s|hours|minutes|seconds)$/
    .exec(umgestellt.replace(/^(?:wie\s*viel(?:e)?\s+(?:ist|sind)|was\s+(?:ist|sind))\s+/, ""));
  if (dauer && [dauer[1], dauer[2], dauer[3]].filter(Boolean).length >= 2) {
    const sek = (dauer[1] ? alsZahl(dauer[1]) * 3600 : 0) + (dauer[2] ? alsZahl(dauer[2]) * 60 : 0)
      + (dauer[3] ? alsZahl(dauer[3]) : 0);
    const ziel = dauer[4];
    const faktor = /^(?:stunde|h)/.test(ziel) ? 3600 : /^min/.test(ziel) ? 60 : 1;
    const englisch = /^(?:hours|minutes|seconds)$/.test(ziel) || sprache === "en";
    const namen = englisch ? ["h", "min", "s"] : ["Std.", "Min.", "Sek."];
    const vorn = [dauer[1], dauer[2], dauer[3]].map((w, i) => (w ? `${zahl(alsZahl(w), sprache)} ${namen[i]}` : ""))
      .filter(Boolean).join(" ");
    const nameZiel = faktor === 3600 ? ["Stunden", "hours"] : faktor === 60 ? ["Minuten", "minutes"] : ["Sekunden", "seconds"];
    const wert = zahl(sek / faktor, sprache, 4);
    return { text: englisch ? `${vorn} is **${wert} ${nameZiel[1]}**.` : `${vorn} sind **${wert} ${nameZiel[0]}**.` };
  }
  const m = new RegExp(`(${ZAHL})\\s*(${EINHEIT})\\s+(?:in|nach|zu|to|into|als|=|sind\\s+wie\\s*viel(?:e)?)\\s+(${EINHEIT})$`).exec(umgestellt);
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
  // "1 Stunde ist", nicht "1 Stunden sind" (16.4.5)
  const eins = wert === 1;
  const vonDe = eins ? (EINZAHL[a.de] || a.de) : a.de;
  // 16.4.5: vorher "1 inche", "1 feet", "1 German pounds (500 g)".
  const EINZAHL_EN = { inches: "inch", feet: "foot", "German pounds (500 g)": "German pound (500 g)",
    "football pitches": "football pitch", "US cups": "US cup", "US gallons": "US gallon",
    "US pints": "US pint", "nautical miles": "nautical mile" };
  const vonEn = eins ? (EINZAHL_EN[a.en] || a.en.replace(/(?<=[a-z])s$/, "")) : a.en;
  return { text: sp(sprache, `${zahl(wert, sprache)} ${vonDe} ${eins ? "ist" : "sind"} **${zahl(ergebnis, sprache, stellen)} ${b.de}**.`,
    `${zahl(wert, sprache)} ${vonEn} is **${zahl(ergebnis, sprache, stellen)} ${b.en}**.`) };
}

// -- Daten und Countdowns ----------------------------------------------------------
const MONATE = { __proto__: null,
  januar: 1, jan: 1, january: 1, februar: 2, feb: 2, february: 2, maerz: 3,
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
  [/weihnachten/, "Weihnachten (Heiligabend)", "Christmas Eve", (j) => new Date(Date.UTC(j, 11, 24))],
  // 16.4.5: Englisch ist "Christmas" der 25. -- vorher zaehlte der Worker bis zum 24.
  [/christmas/, "1. Weihnachtstag", "Christmas Day", (j) => new Date(Date.UTC(j, 11, 25))],
  [/silvester|new\s+year'?s\s+eve/, "Silvester", "New Year's Eve", (j) => new Date(Date.UTC(j, 11, 31))],
  [/neujahr|new\s+year/, "Neujahr", "New Year's Day", (j) => new Date(Date.UTC(j, 0, 1))],
  [/ostern|easter/, "Ostern", "Easter", (j) => ostern(j)],
  // 16.4.6: gesetzliche Feiertage fuer Wochentag und Countdown -- vorher kam das Datum von heute.
  [/karfreitag|good\s+friday/, "Karfreitag", "Good Friday", (j) => tagNach(ostern(j), -2)],
  [/ostermontag|easter\s+monday/, "Ostermontag", "Easter Monday", (j) => tagNach(ostern(j), 1)],
  [/pfingstmontag|whit\s+monday/, "Pfingstmontag", "Whit Monday", (j) => tagNach(ostern(j), 50)],
  [/fronleichnam|corpus\s+christi/, "Fronleichnam", "Corpus Christi", (j) => tagNach(ostern(j), 60)],
  [/tag\s+der\s+arbeit/, "Tag der Arbeit", "Labour Day (Germany)", (j) => new Date(Date.UTC(j, 4, 1))],
  [/reformationstag/, "Reformationstag", "Reformation Day", (j) => new Date(Date.UTC(j, 9, 31))],
  [/allerheiligen/, "Allerheiligen", "All Saints' Day", (j) => new Date(Date.UTC(j, 10, 1))],
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

// 16.4.5: bundesweite Feiertage fuer die Zahl der Arbeitstage (wie aquaticy/standard.py).
function bundesweiteFeiertage(j) {
  const o = ostern(j);
  return [new Date(Date.UTC(j, 0, 1)), tagNach(o, -2), tagNach(o, 1), new Date(Date.UTC(j, 4, 1)),
    tagNach(o, 39), tagNach(o, 50), new Date(Date.UTC(j, 9, 3)), new Date(Date.UTC(j, 11, 25)),
    new Date(Date.UTC(j, 11, 26))].map((d) => d.getTime());
}

/** Montag bis Freitag ohne bundesweite Feiertage, von und bis mitgezaehlt. */
export function arbeitstage(von, bis) {
  if (bis < von) return 0;
  const frei = new Set();
  for (let j = von.getUTCFullYear(); j <= bis.getUTCFullYear(); j++) {
    for (const t of bundesweiteFeiertage(j)) frei.add(t);
  }
  let n = 0;
  for (let d = von; d <= bis; d = tagNach(d, 1)) {
    const w = d.getUTCDay();
    if (w !== 0 && w !== 6 && !frei.has(d.getTime())) n++;
  }
  return n;
}

/** Ein Datum aus "24.12.", "3.10.1990", "1. mai 2027", "may 1", "2027-03-28". */
// 17.1.0: Nur Daten, die es gibt. Date.UTC rechnete vorher weiter: "29.02.2027" wurde zum
// 1. Maerz, "31.04." zum 1. Mai -- und Jahre unter 100 wurden zu 19xx.
function echtesDatum(jahr, monat, tag) {
  if (!(jahr >= 1 && jahr <= 9999 && monat >= 1 && monat <= 12 && tag >= 1 && tag <= 31)) return null;
  const d = new Date(Date.UTC(2000, monat - 1, tag));
  d.setUTCFullYear(jahr);
  return d.getUTCFullYear() === jahr && d.getUTCMonth() === monat - 1 && d.getUTCDate() === tag ? d : null;
}

function datumFund(jahr, monat, tag, mitJahr) {
  // Ohne Jahr gibt es den 29. Februar im naechsten Schaltjahr (wie in aquaticy/standard.py).
  for (let j = jahr; j <= (mitJahr ? jahr : jahr + 8); j++) {
    const d = echtesDatum(j, monat, tag);
    if (d) return { datum: d, mitJahr };
  }
  return { datum: null, mitJahr, ungueltig: { jahr, monat, tag } };
}

export function ungueltigText(u, sprache) {
  const zwei = (n) => String(n).padStart(2, "0");
  const anzeige = `${zwei(u.tag)}.${zwei(u.monat)}.${String(u.jahr).padStart(4, "0")}`;
  const schalt = u.monat === 2 && u.tag === 29 && u.jahr >= 1 && u.jahr <= 9999;
  return sp(sprache, `Den ${anzeige} gibt es nicht${schalt ? ` – ${u.jahr} ist kein Schaltjahr` : ""}.`,
    `${anzeige} doesn't exist${schalt ? ` – ${u.jahr} isn't a leap year` : ""}.`);
}

export function datumAus(t, jetztJahr) {
  let m = /\b(\d{4})-(\d{1,2})-(\d{1,2})\b/.exec(t);
  if (m) return datumFund(+m[1], +m[2], +m[3], true);
  // Nie mitten in einer Zahlenkette ("1.1.1", "Version 1.24.12").
  m = /(?<![\d.])\b(\d{1,2})\.\s*(\d{1,2})(?:\.(?:\s*(\d{4}|\d{2}))?(?!\d)|(?=\s|$))/.exec(t);
  if (m) {
    const kurz = Number(m[3]);
    // "05.05.90" ist 1990, nicht 2090 -- mehr als 20 Jahre voraus gilt als 19xx (wie in Python).
    const jahr = m[3] ? (m[3].length === 2 ? (2000 + kurz <= jetztJahr + 20 ? 2000 + kurz : 1900 + kurz)
      : kurz) : jetztJahr;
    return datumFund(jahr, +m[2], +m[1], Boolean(m[3]));
  }
  m = /\b(\d{1,2})\.?\s+([a-z]+)(?:\s+(\d{4}))?\b/.exec(t);
  if (m && MONATE[m[2]]) return datumFund(m[3] ? +m[3] : jetztJahr, MONATE[m[2]], +m[1], Boolean(m[3]));
  m = /\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b/.exec(t);
  if (m && MONATE[m[1]]) return datumFund(m[3] ? +m[3] : jetztJahr, MONATE[m[1]], +m[2], Boolean(m[3]));
  return null;
}

const gueltig = (d) => d instanceof Date && !Number.isNaN(d.getTime());

export function datumAntwort(text, sprache = "de", jetzt = new Date()) {
  const t = glatt(text);
  const loc = sprache === "en" ? "en-GB" : "de-DE";
  const zeig = (d) => d.toLocaleDateString(loc, { weekday: "long", day: "numeric", month: "long",
    year: "numeric", timeZone: "UTC" });
  const heute = new Date(Date.UTC(jetzt.getUTCFullYear(), jetzt.getUTCMonth(), jetzt.getUTCDate()));
  // 16.4.5: "Welches Datum war vor 100 Tagen?" nannte vorher das Datum von heute.
  // 17.1.1: auch Monate und Jahre ("in einem Monat", "in one year") -- vorher das Datum von heute.
  const v = /\b(in|vor)\s+(\d{1,4}|einem|einer|einen|zwei|drei|a|an|one|two|three)\s+(tag|tagen|woche|wochen|monat|monaten|jahr|jahren|days?|weeks?|months?|years?)\b|\b(\d{1,4}|a|an|one|two|three)\s+(days?|weeks?|months?|years?)\s+ago\b/
    .exec(t);
  if (v && /\b(?:datum|tag|wochentag|date|day)\b/.test(t.replace(v[0], " "))) {
    const wort = v[2] || v[4];
    const n = Number(wort) || { zwei: 2, drei: 3, two: 2, three: 3 }[wort] || 1;
    const einheit = v[3] || v[5];
    const zurueck = v[1] === "vor" || v[4] !== undefined;
    const richtung = zurueck ? -1 : 1;
    let d;
    if (/^(?:monat|month|jahr|year)/.test(einheit)) {
      const monate = n * (/^(?:jahr|year)/.test(einheit) ? 12 : 1) * richtung;
      const ziel = new Date(Date.UTC(heute.getUTCFullYear(), heute.getUTCMonth() + monate, 1));
      const letzter = new Date(Date.UTC(ziel.getUTCFullYear(), ziel.getUTCMonth() + 1, 0)).getUTCDate();
      d = new Date(Date.UTC(ziel.getUTCFullYear(), ziel.getUTCMonth(), Math.min(heute.getUTCDate(), letzter)));
    } else {
      d = new Date(heute.getTime() + n * (/^w/.test(einheit) ? 7 : 1) * richtung * 86400000);
    }
    const deWort = { tag: "Tag", tagen: "Tagen", woche: "Woche", wochen: "Wochen", monat: "Monat",
      monaten: "Monaten", jahr: "Jahr", jahren: "Jahren" }[einheit] || einheit;
    return { text: sp(sprache, `${zurueck ? "Vor" : "In"} ${wort} ${deWort} ${zurueck ? "war" : "ist"} **${zeig(d)}**.`,
      zurueck ? `${wort} ${einheit} ago it was **${zeig(d)}**.` : `In ${wort} ${einheit} it will be **${zeig(d)}**.`) };
  }
  // 17.1.1: "Welches Datum ist der 100. Tag des Jahres?" -- vorher das Datum von heute.
  const nter = /\b(?:der\s+)?(\d{1,3})\.?\s*tag\s+(?:des|im)\s+jahr(?:es)?(?:\s+(\d{4}))?|\bthe\s+(\d{1,3})(?:st|nd|rd|th)\s+day\s+of\s+(?:the\s+year|(\d{4}))/
    .exec(t);
  if (nter) {
    const n = Number(nter[1] || nter[3]);
    const jahr = Number(nter[2] || nter[4]) || heute.getUTCFullYear();
    const laenge = (Date.UTC(jahr + 1, 0, 1) - Date.UTC(jahr, 0, 1)) / 86400000;
    if (n < 1 || n > laenge) {
      return { text: sp(sprache, `Das Jahr ${jahr} hat ${laenge} Tage.`, `${jahr} has ${laenge} days.`) };
    }
    const d = new Date(Date.UTC(jahr, 0, n));
    return { text: sp(sprache, `Der ${n}. Tag des Jahres ${jahr} ist **${zeig(d)}**.`,
      `Day ${n} of ${jahr} is **${zeig(d)}**.`) };
  }
  // Countdown: "wie viele Tage bis Weihnachten", "wie lange noch bis zum 1. mai"
  // 16.4.6: auch "How many weeks until Christmas?" (vorher die Liste der Feiertage).
  // 16.4.5: "Wie viele Tage sind es bis Weihnachten?" und "Wie viele Wochen bis ...?" gingen
  // vorher an die Feiertage (Antwort: Datum des 1. Weihnachtstags).
  let m = /(?:wie\s*(?:viele|lange)\s+(?:(?:werk|arbeits)?tage\s+|wochen\s+)?(?:(?:ist|sind|dauert)\s+es\s+)?(?:noch\s+)?bis|how\s+(?:many\s+(?:days|weeks)|long)\s+(?:is\s+it\s+|are\s+there\s+|are\s+left\s+)?(?:until|till|to)|countdown\s+(?:bis|to)|tage\s+bis)\s+(?:zu[mr]?\s+|zu\s+)?(.+)$/.exec(t);
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
      if (gefunden?.ungueltig) return { text: ungueltigText(gefunden.ungueltig, sprache) };
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
    // 16.4.5: "Wie viele Werktage bis Weihnachten?" nannte vorher alle Kalendertage.
    let arbeit = "";
    if (sprache !== "en" && /\b(?:werk|arbeits)tage?\b/.test(t) && tage >= 1 && tage <= 3660) {
      const n = arbeitstage(tagNach(heute, 1), tagNach(heute, tage - 1));
      arbeit = ` Dazwischen liegen **${zahl(n, sprache)} ${n === 1 ? "Arbeitstag" : "Arbeitstage"}** `
        + "(Montag bis Freitag, ohne bundesweite Feiertage).";
    }
    return { text: sp(sprache,
      `Bis ${istDatum ? "zum " : ""}${name} sind es noch **${zahl(tage, sprache)} ${tagWort}**${wochen}.${wann}${arbeit}`,
      `**${zahl(tage, sprache)} ${tagWort}** to go until ${name}${wochen}.${wann}`) };
  }
  // Wochentag eines Datums: "welcher wochentag war der 3.10.1990", "what day was july 4 1776"
  m = /(?:welche[rn]?\s+(?:wochen)?tag\s+(?:ist|war|wird|faellt)|auf\s+welchen\s+(?:wochen)?tag\s+faellt|what\s+day\s+(?:of\s+the\s+week\s+)?(?:is|was|will\s+be|falls\s+on))\s+(?:der|am|on)?\s*(.+)$/.exec(t);
  if (m) {
    const ostern2 = /ostern|easter/.test(m[1]);
    const jahr = /\b(\d{4})\b/.exec(m[1]);
    // 16.4.5: "Welcher Wochentag ist Heiligabend?", "What day of the week is Christmas?" -- der
    // Anlass war hier unbekannt, dann nannte die Uhrzeit das Datum von heute.
    const anlass = ostern2 ? null : ANLAESSE.find(([muster]) => muster.test(m[1]));
    let amAnlass = null;
    if (anlass) {
      amAnlass = anlass[3](jahr ? +jahr[1] : heute.getUTCFullYear());
      if (!jahr && amAnlass < heute) amAnlass = anlass[3](heute.getUTCFullYear() + 1);
    }
    const gefunden = amAnlass ? { datum: amAnlass } : ostern2
      ? { datum: ostern(jahr ? +jahr[1] : heute.getUTCFullYear()) }
      : datumAus(m[1], heute.getUTCFullYear());
    if (gefunden?.ungueltig) return { text: ungueltigText(gefunden.ungueltig, sprache) };
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
    if (gefunden?.ungueltig) return { text: ungueltigText(gefunden.ungueltig, sprache) };
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

/** Datum und Uhrzeit von *datum* in der Zeitzone *zone* (nur Zahlen). */
function zeitTeile(datum, zone) {
  const f = new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const o = Object.fromEntries(f.formatToParts(datum).map((x) => [x.type, x.value]));
  return { j: +o.year, m: +o.month, t: +o.day, h: +o.hour, min: +o.minute };
}

// 16.4.5: "Wenn es in Berlin 9 Uhr ist, wie spät ist es dann in Tokio?" nannte vorher die Zeit von
// hier, "Wie spät ist es in New York, wenn es bei uns 18 Uhr ist?" suchte einen Ort "wenn es bei
// uns 18 Uhr ist".
async function weltzeitWennEn(roh, kontext) {
  // 17.1.1: "If it's 3 pm here, what time is it in New York?" nannte die Zeit von jetzt.
  const frage = String.raw`what\s+time\s+(?:is\s+it|will\s+it\s+be)\s+(?:then\s+)?in\s+`;
  const bedingung = String.raw`if\s+it(?:'s|\s+is)\s+(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\s+(?:here|in\s+(.+?))`;
  let stunde, minute, halb, von, nach;
  const vorn = new RegExp(`^${bedingung}\\s*,?\\s+${frage}(.+)$`, "iu").exec(roh);
  const hinten = new RegExp(`^${frage}(.+?)\\s*,?\\s+${bedingung}$`, "iu").exec(roh);
  if (vorn) [, stunde, minute, halb, von, nach] = vorn;
  else if (hinten) [, nach, stunde, minute, halb, von] = hinten;
  else return null;
  let h = Number(stunde);
  if (h > 24 || Number(minute || 0) > 59 || (halb && (h < 1 || h > 12))) return null;
  if (halb && /^p/i.test(halb) && h < 12) h += 12;
  if (halb && /^a/i.test(halb) && h === 12) h = 0;
  const schritt = { type: "search", query: `time ${nach}` };
  let zoneVon = kontext.zeitzone || "Europe/Berlin";
  if (von) {
    const platzVon = await dienste.ort(von, "en", kontext.holen);
    if (platzVon?.fehler) return { schritt, text: DIENST_WEG("en") };
    if (!platzVon?.zeitzone) return { schritt, text: `I can't find a place called “${von}” right now.` };
    zoneVon = platzVon.zeitzone;
  }
  const platz = await dienste.ort(nach, "en", kontext.holen);
  if (platz?.fehler) return { schritt, text: DIENST_WEG("en") };
  if (!platz?.zeitzone) return { schritt, text: `I can't find a place called “${nach}” right now.` };
  const jetzt = kontext.jetzt || new Date();
  try {
    const hier = zeitTeile(jetzt, zoneVon);
    const lokal = Date.UTC(hier.j, hier.m - 1, hier.t, h, Number(minute || 0));
    const versatz = Date.UTC(hier.j, hier.m - 1, hier.t, hier.h, hier.min)
      - Math.floor(jetzt.getTime() / 60000) * 60000;
    const dort = zeitTeile(new Date(lokal - versatz), platz.zeitzone);
    const tage = Math.round((Date.UTC(dort.j, dort.m - 1, dort.t) - Date.UTC(hier.j, hier.m - 1, hier.t))
      / 86400000);
    const zwei = (n) => String(n).padStart(2, "0");
    const tagText = tage === 1 ? " – the next day" : tage === -1 ? " – the day before" : "";
    return { schritt, text: `If it's ${zwei(h)}:${zwei(Number(minute || 0))} ${von ? `in ${von}` : "where you are"}, `
      + `it's **${zwei(dort.h)}:${zwei(dort.min)}** in **${platz.name}**${tagText}.` };
  } catch {
    return null;
  }
}

async function weltzeitWenn(text, sprache, kontext) {
  const roh = String(text).trim().replace(/[?!.]+$/, "");
  if (sprache === "en" || /^if\s+it|what\s+time\s+(?:is\s+it|will\s+it\s+be)\s+(?:then\s+)?in\s+.+\bif\s+it/i.test(roh)) {
    return weltzeitWennEn(roh, kontext);
  }
  const frage = String.raw`(?:wie\s*sp(?:ä|ae)t|wie\s*viel\s+uhr)\s+ist\s+es\s+(?:dann\s+)?(?:in|auf)\s+`;
  const bedingung = String.raw`wenn\s+es\s+(?:bei\s+uns|hier|in\s+(.+?))\s+(\d{1,2})(?:[:.](\d{2}))?\s*uhr\s+ist`;
  let von, stunde, minute, nach;
  const vorn = new RegExp(`^${bedingung}\\s*,?\\s+${frage}(.+)$`, "iu").exec(roh);
  const hinten = new RegExp(`^${frage}(.+?)\\s*,?\\s+${bedingung}$`, "iu").exec(roh);
  if (vorn) [, von, stunde, minute, nach] = vorn;
  else if (hinten) [, nach, von, stunde, minute] = hinten;
  else return null;
  if (Number(stunde) > 24 || Number(minute || 0) > 59) return null;
  const schritt = { type: "search", query: `Uhrzeit ${nach}` };
  let zoneVon = kontext.zeitzone || "Europe/Berlin";
  if (von) {
    const platzVon = await dienste.ort(von, sprache, kontext.holen);
    if (platzVon?.fehler) return { schritt, text: DIENST_WEG(sprache) };
    if (!platzVon?.zeitzone) return { schritt, text: `Einen Ort „${von}“ finde ich gerade nicht.` };
    zoneVon = platzVon.zeitzone;
  }
  const platz = await dienste.ort(nach, sprache, kontext.holen);
  if (platz?.fehler) return { schritt, text: DIENST_WEG(sprache) };
  if (!platz?.zeitzone) return { schritt, text: `Einen Ort „${nach}“ finde ich gerade nicht.` };
  const jetzt = kontext.jetzt || new Date();
  try {
    const heute = zeitTeile(jetzt, zoneVon);
    const lokal = Date.UTC(heute.j, heute.m - 1, heute.t, Number(stunde), Number(minute || 0));
    const hier = zeitTeile(jetzt, zoneVon);
    const versatz = Date.UTC(hier.j, hier.m - 1, hier.t, hier.h, hier.min)
      - Math.floor(jetzt.getTime() / 60000) * 60000;
    const dort = zeitTeile(new Date(lokal - versatz), platz.zeitzone);
    const tage = Math.round((Date.UTC(dort.j, dort.m - 1, dort.t) - Date.UTC(heute.j, heute.m - 1, heute.t))
      / 86400000);
    const zwei = (n) => String(n).padStart(2, "0");
    const tagText = tage === 1 ? " – am nächsten Tag" : tage === -1 ? " – am Tag davor" : "";
    const wo = von ? `in ${von}` : "bei dir";
    return { schritt, text: `Wenn es ${wo} ${zwei(Number(stunde))}:${zwei(Number(minute || 0))} Uhr ist, `
      + `ist es in **${platz.name}** **${zwei(dort.h)}:${zwei(dort.min)} Uhr**${tagText}.` };
  } catch {
    return null;
  }
}

// 16.4.5: "Zeitverschiebung nach Tokio", "Zeitunterschied zwischen Berlin und New York" gingen
// vorher an Wikipedia.
async function zeitUnterschied(text, sprache, kontext) {
  if (sprache === "en") return null;
  const roh = String(text).trim().replace(/[?!.]+$/, "");
  const m = /zeit(?:verschiebung|unterschied|differenz)\s+(?:zwischen\s+(.+?)\s+und\s+(.+)|(?:nach|zu|mit|in)\s+(.+))$/iu
    .exec(roh);
  if (!m) return null;
  const namen = m[3] ? [null, m[3]] : [m[1], m[2]];
  const schritt = { type: "search", query: `Zeitverschiebung ${namen.filter(Boolean).join(" ")}` };
  const zonen = [];
  for (const name of namen) {
    if (!name) { zonen.push([kontext.zeitzone || "Europe/Berlin", "dir"]); continue; }
    const platz = await dienste.ort(name.replace(/^(?:der|die|den|dem|das)\s+/i, ""), sprache, kontext.holen);
    if (platz?.fehler) return { schritt, text: DIENST_WEG(sprache) };
    if (!platz?.zeitzone) return { schritt, text: `Einen Ort „${name}“ finde ich gerade nicht.` };
    zonen.push([platz.zeitzone, platz.name]);
  }
  const jetzt = kontext.jetzt || new Date();
  try {
    const minuten = (zone) => {
      const x = zeitTeile(jetzt, zone);
      return (Date.UTC(x.j, x.m - 1, x.t, x.h, x.min) - Math.floor(jetzt.getTime() / 60000) * 60000) / 60000;
    };
    const diff = (minuten(zonen[1][0]) - minuten(zonen[0][0])) / 60;
    const [a, b] = [zonen[0][1], zonen[1][1]];
    if (!diff) return { schritt, text: m[3] ? `In **${b}** ist es gerade dieselbe Uhrzeit wie bei dir.`
      : `**${a}** und **${b}** haben gerade dieselbe Uhrzeit.` };
    const stunden = `${zahl(Math.abs(diff), sprache, 1)} ${Math.abs(diff) === 1 ? "Stunde" : "Stunden"}`;
    const richtung = diff > 0 ? "später" : "früher";
    return { schritt, text: m[3]
      ? `In **${b}** ist es gerade **${stunden} ${richtung}** als bei dir.`
      : `Zwischen **${a}** und **${b}** liegen gerade **${stunden}** – in ${b.split(",")[0]} ist es ${richtung}.` };
  } catch {
    return null;
  }
}

export async function weltzeitAntwort(text, sprache, kontext) {
  const wenn = await weltzeitWenn(text, sprache, kontext) || await zeitUnterschied(text, sprache, kontext);
  if (wenn) return wenn;
  const t = glatt(text);
  const m = /(?:wie\s*spaet\s+ist\s+es|wie\s*viel\s+uhr\s+ist\s+es|uhrzeit|what\s+time\s+is\s+it|time)\s+(?:gerade\s+|jetzt\s+)?(?:in|im|auf|bei|in\s+der|in\s+den)\s+(.{2,80})$/.exec(t);
  if (!m) return null;
  // 17.1.1: "Wie spät ist es in 3 Stunden?" suchte einen Ort "3 Stunden".
  if (/^(?:\d{1,4}|einer|einem|an?|one)\s+(?:stunden?|minuten?|hours?|minutes?)\b/.test(m[1])) return null;
  const roh = String(text).trim().replace(/[?!.]+$/, "").split(/\s+/);
  const ganz = roh.slice(roh.length - m[1].split(/\s+/).length).join(" ").replace(ORT_ENDE, "");
  // 16.4.5: "in der Türkei" suchte "der Türkei", "in Tokio und in London" einen Ort
  // "Tokio und in London".
  const orte = ganz.split(/\s*,\s*|\s+(?:und|sowie|oder|and)\s+/i)
    .map((o) => o.replace(/^(?:in|im|der|die|den|dem|das|the)\s+/i, "").trim()).filter(Boolean);
  if (orte.length > 1) {
    const texte = [];
    for (const ort of orte.slice(0, 3)) {
      const einzeln = await weltzeitAntwort(sp(sprache, `Wie spät ist es in ${ort}`,
        `What time is it in ${ort}`), sprache, kontext);
      if (einzeln) texte.push(einzeln.text);
    }
    if (texte.length) {
      return { schritt: { type: "search", query: sp(sprache, `Uhrzeit ${orte.join(", ")}`,
        `time ${orte.join(", ")}`) }, text: texte.join("\n\n") };
    }
  }
  const name = orte[0] || ganz;
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
  if (!/sonne\w*\s+(?:\S+\s+){0,3}?(?:auf|unter)\b|sonnen(?:aufgang|untergang)|wann\s+wird\s+es\s+(?:hell|dunkel)|sunrise|sunset|sun\s+(?:rise|set)/.test(t)) {
    return null;
  }
  const m = /\b(?:in|im|fuer|bei|for|at)\s+([\p{L}][\p{L}\s.'-]{1,50})$/u.exec(String(text).trim()
    .replace(/[?!.]+$/, "").replace(/\s+(?:heute|morgen|today|tomorrow)$/i, ""));
  // 16.4.5: "Wann geht in Berlin die Sonne unter?" suchte "Berlin die Sonne unter".
  let name = m ? m[1].trim().replace(/\s+(?:geht\s+)?(?:die\s+)?sonne\s+(?:auf|unter)$/i, "")
    .replace(/\s+(?:auf|unter)$/i, "").trim() : "";
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
  if (/^(?:bitte\s+)?(?:wuerfel|wuerfle|wuerfeln|wuerfel\s+mal|wirf\s+(?:mal\s+)?(?:einen|zwei|drei|\d+)\s+(?:wuerfel|[wd]\d+)|roll\s+(?:a\s+|the\s+|two\s+|\d+\s+)?(?:die|dice|d\d+))\b/.test(t)) {
    const zahlwort = (x) => x?.replace(/zwei|two/, "2").replace(/drei|three/, "3");
    const anzahlRoh = (/\b(\d+|zwei|drei|two|three)\s+(?:wuerfel|dice|[wd]\d+)/.exec(t) || [])[1];
    const anzahl = Math.min(10, Math.max(1, Number(zahlwort(anzahlRoh)) || 1));
    // "einen W20", "zwei W20": vorher immer sechs Seiten (16.4.5)
    const seitenRoh = (/\b[wd](4|6|8|10|12|20|100)\b|\b(4|6|8|10|12|20|100)-?seitig/.exec(t) || []);
    let seiten = Number(seitenRoh[1] || seitenRoh[2]) || 6;
    let wieOft = anzahl;
    // 16.4.5: "Würfle 3W6", "2d20" -- vorher ein Wurf.
    const kombi = /\b([1-9]|1\d|20)\s*[wd](4|6|8|10|12|20|100)\b/.exec(t);
    if (kombi) { wieOft = Number(kombi[1]); seiten = Number(kombi[2]); }
    const wuerfe = Array.from({ length: wieOft }, () => ganz(1, seiten));
    const summe = wuerfe.reduce((a, b) => a + b, 0);
    return { text: `🎲 ${wuerfe.map((w) => `**${w}**`).join(" + ")}${wieOft > 1 ? ` = **${summe}**` : ""}` };
  }
  if (/(?:wirf|werfe|wirfst|flip|toss)\s+(?:mal\s+)?(?:eine\s+|a\s+)?(?:muenze|coin)|kopf\s+oder\s+zahl|heads\s+or\s+tails|muenzwurf/.test(t)) {
    const seite = zufall() < 0.5;
    return { text: sp(sprache, `🪙 **${seite ? "Kopf" : "Zahl"}**!`, `🪙 **${seite ? "Heads" : "Tails"}**!`) };
  }
  // 16.4.5: "zahl zwischen" verbrauchte das "zwischen" -- die Grenzen galten dann nicht.
  let m = /(?:zufallszahl|zufaellige\s+zahl|random\s+number|zahl(?=\s+zwischen)|number(?=\s+between))(?:\s+(?:zwischen|von|between|from)\s+(-?\d+)\s+(?:und|bis|and|to)\s+(-?\d+))?/.exec(t);
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
const SPRACHEN = { __proto__: null,
  englisch: "en", english: "en", deutsch: "de", german: "de", franzoesisch: "fr",
  french: "fr", spanisch: "es", spanish: "es", italienisch: "it", italian: "it", tuerkisch: "tr",
  turkish: "tr", niederlaendisch: "nl", hollaendisch: "nl", dutch: "nl", polnisch: "pl",
  polish: "pl", portugiesisch: "pt", portuguese: "pt", russisch: "ru", russian: "ru",
  ukrainisch: "uk", ukrainian: "uk", arabisch: "ar", arabic: "ar", chinesisch: "zh",
  chinese: "zh", japanisch: "ja", japanese: "ja", griechisch: "el", greek: "el",
  schwedisch: "sv", swedish: "sv", daenisch: "da", danish: "da", norwegisch: "no",
  norwegian: "no", tschechisch: "cs", czech: "cs", kroatisch: "hr", croatian: "hr",
  latein: "la", latin: "la", koreanisch: "ko", korean: "ko", finnisch: "fi", finnish: "fi",
  ungarisch: "hu", hungarian: "hu", rumaenisch: "ro", romanian: "ro" };
const SPRACHNAME = { __proto__: null,
  en: ["Englisch", "English"], de: ["Deutsch", "German"], fr: ["Französisch",
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
const FAKTEN = { __proto__: null,
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
const MUT = { __proto__: null,
  de: ["Kleine Schritte zählen auch. Hauptsache, du gehst los.",
    "Du musst nicht perfekt sein, um anzufangen – aber du musst anfangen, um besser zu werden.",
    "Heute ist ein guter Tag, um etwas zu schaffen, auf das du morgen stolz bist.",
    "Fehler sind Beweise dafür, dass du es versuchst.",
    "Eins nach dem anderen. Du schaffst das!"],
  en: ["Small steps count too. What matters is that you start.",
    "You don't have to be perfect to start – but you have to start to get better.",
    "Mistakes are proof that you're trying.", "One thing at a time. You've got this!"],
};
const IDEEN_ESSEN = { __proto__: null,
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
