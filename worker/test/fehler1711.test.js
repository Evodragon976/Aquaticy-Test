// 17.1.1: Fehler aus der Suche nach 300 Funden (Feiertage, Wetter, Zeit, Einheiten). Ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { festeAntwort } from "../src/antworten.js";

const JETZT = new Date("2026-11-25T09:30:00Z");

function ostersonntag(jahr) {
  const a = jahr % 19, b = Math.floor(jahr / 100), c = jahr % 100, d = Math.floor(b / 4);
  const e = b % 4, f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  const monat = Math.floor((h + l - 7 * m + 114) / 31), tag = ((h + l - 7 * m + 114) % 31) + 1;
  return Date.UTC(jahr, monat - 1, tag);
}

function feiertage(jahr) {
  const iso = (ms) => new Date(ms).toISOString().slice(0, 10);
  const plus = (n) => iso(ostersonntag(jahr) + n * 864e5);
  const alle = [["Neujahr", "New Year's Day", `${jahr}-01-01`, null],
    ["Karfreitag", "Good Friday", plus(-2), null], ["Ostermontag", "Easter Monday", plus(1), null],
    ["Tag der Arbeit", "Labour Day", `${jahr}-05-01`, null],
    ["Christi Himmelfahrt", "Ascension Day", plus(39), null],
    ["Pfingstmontag", "Whit Monday", plus(50), null],
    ["Fronleichnam", "Corpus Christi", plus(60), ["DE-BW", "DE-BY"]],
    ["Mariä Himmelfahrt", "Assumption Day", `${jahr}-08-15`, ["DE-SL"]],
    ["Tag der Deutschen Einheit", "German Unity Day", `${jahr}-10-03`, null],
    ["Reformationstag", "Reformation Day", `${jahr}-10-31`, ["DE-HH", "DE-NI"]],
    ["Allerheiligen", "All Saints' Day", `${jahr}-11-01`, ["DE-BW", "DE-BY"]],
    ["Erster Weihnachtstag", "Christmas Day", `${jahr}-12-25`, null],
    ["Zweiter Weihnachtstag", "St. Stephen's Day", `${jahr}-12-26`, null]];
  return alle.map(([localName, name, date, counties]) => ({ date, localName, name,
    global: !counties, counties })).sort((x, y) => x.date.localeCompare(y.date));
}

const ORTE = { berlin: [52.52, 13.41, "Europe/Berlin", "Berlin"], london: [51.51, -0.13, "Europe/London", "London"],
  "new york": [40.71, -74.01, "America/New_York", "New York"], tokio: [35.69, 139.69, "Asia/Tokyo", "Tokio"],
  tokyo: [35.69, 139.69, "Asia/Tokyo", "Tokyo"], madrid: [40.42, -3.7, "Europe/Madrid", "Madrid"] };
const TAGE = [...Array(7)].map((_, i) => new Date(Date.UTC(2026, 10, 25 + i)).toISOString().slice(0, 10));
const json = (d) => new Response(JSON.stringify(d), { status: 200, headers: { "content-type": "application/json" } });

const anfragen = [];
const holen = async (url) => {
  anfragen.push(String(url));
  const u = new URL(String(url));
  if (u.hostname.includes("geocoding")) {
    const o = ORTE[(u.searchParams.get("name") || "").toLowerCase().trim()];
    return json(o ? { results: [{ name: o[3], latitude: o[0], longitude: o[1], timezone: o[2], country_code: "XX" }] }
      : { results: [] });
  }
  if (u.hostname.includes("open-meteo")) {
    return json({ timezone: "Europe/Berlin", current: { temperature_2m: 7.2, apparent_temperature: 5.1,
      weather_code: 61, wind_speed_10m: 14 }, daily: { time: TAGE, weather_code: [61, 0, 3, 71, 95, 45, 1],
      temperature_2m_max: [9.4, 11, 8.2, -1, 24.5, 5, 31], temperature_2m_min: [3.1, 4, 2, -6.5, 15, -0.4, 19],
      precipitation_probability_max: [70, 10, 20, 80, 90, 5, 0], sunrise: TAGE.map((d) => d + "T07:48"),
      sunset: TAGE.map((d) => d + "T16:05") } });
  }
  if (u.hostname.includes("frankfurter")) {
    return json({ base: "EUR", date: "2026-11-25", rates: { USD: 1.0823 } });
  }
  if (u.hostname.includes("tagesschau")) {
    return json({ news: [{ title: "Meldung A", shareURL: "https://www.tagesschau.de/a" }] });
  }
  if (u.hostname.includes("nager")) {
    const jahr = Number(u.pathname.split("/").filter(Boolean).at(-2));
    return new Response(JSON.stringify(feiertage(jahr)), { status: 200,
      headers: { "content-type": "application/json" } });
  }
  return new Response("{}", { status: 404 });
};
const frag = async (frage, sprache = "de") =>
  (await festeAntwort(frage, { holen, jetzt: JETZT, sprache }))?.text ?? null;

test("W13: Ostern und Pfingsten sind Sonntage", async () => {
  // Vorher: "**Ostermontag** ist am **Montag, 29. März 2027**." und dasselbe für Pfingsten.
  assert.match(await frag("Wann ist Ostern?"),
    /^\*\*Ostersonntag\*\* ist am \*\*Sonntag, 28\. März 2027\*\*\. Feiertage sind Karfreitag/);
  assert.match(await frag("When is Easter?", "en"),
    /^\*\*Easter Sunday\*\* is on \*\*Sunday, 28 March 2027\*\*/);
  assert.match(await frag("Wann war Ostern?"), /^\*\*Ostersonntag\*\* war am \*\*Sonntag, 5\. April 2026/);
  assert.match(await frag("Wann ist Pfingsten?"),
    /^\*\*Pfingstsonntag\*\* ist am \*\*Sonntag, 16\. Mai 2027\*\*\. Feiertag ist Pfingstmontag/);
  // Der Ostermontag selbst bleibt der Ostermontag.
  assert.match(await frag("Wann ist Ostermontag 2027?"), /^\*\*Ostermontag\*\* ist am \*\*Montag, 29\. März 2027/);
});

test("W14: ein Jahr ausserhalb der Liste wird nicht still zum aktuellen Jahr", async () => {
  // Vorher: "Ostern 3000" und "Feiertage 1985" gaben die Daten von 2026/2027.
  assert.match(await frag("Wann ist Ostern 3000?"), /Sonntag, 13\. April 3000/);
  assert.match(await frag("Wann war Ostern 1600?"), /Sonntag, 2\. April 1600/);
  assert.match(await frag("Wann war Ostern 1500?"), /1583 bis 9999/);
  assert.equal(await frag("Feiertage 1985"), "Feiertage schlage ich für die Jahre 1990 bis 2100 nach.");
});

test("W15: Mariä Himmelfahrt ist nicht Christi Himmelfahrt", async () => {
  // Vorher: "**Christi Himmelfahrt** ist am Donnerstag, 6. Mai 2027." zuerst.
  assert.match(await frag("Wann ist Mariä Himmelfahrt?"), /^\*\*Mariä Himmelfahrt\*\* ist am \*\*Sonntag, 15\. August 2027/);
  assert.match(await frag("Wann ist Christi Himmelfahrt?"), /^\*\*Christi Himmelfahrt\*\* ist am \*\*Donnerstag, 6\. Mai 2027/);
  // Nur "Himmelfahrt": Christi zuerst, Mariä als Zusatz -- wie vorher.
  assert.match(await frag("Wann ist Himmelfahrt?"), /Dazu gehört auch:\n- \*\*Mariä Himmelfahrt\*\*/);
});

test("W16: ein regionaler Feiertag ist kein Ja fuer alle", async () => {
  // Vorher: "Ja, der Samstag, 31. Oktober 2026 war **Reformationstag**." ohne Hinweis.
  assert.match(await frag("Ist der 31. Oktober ein Feiertag?"),
    /^In einigen Bundesländern ja: Der Samstag, 31\. Oktober 2026 war \*\*Reformationstag\*\* \(nicht bundesweit\)/);
  assert.match(await frag("Is October 31 a holiday?", "en"), /^In some regions, yes: .*\(not nationwide\)/);
  assert.match(await frag("Ist der 3. Oktober ein Feiertag?"), /^Ja, der Samstag, 3\. Oktober 2026 war/);
});

test("W17: seit einem Feiertag zaehlt rueckwaerts", async () => {
  // Vorher: "Wie viele Tage sind seit Neujahr vergangen?" nannte das nächste Neujahr.
  assert.match(await frag("Wie viele Tage sind seit Neujahr vergangen?"),
    /^Seit Neujahr \(Donnerstag, 1\. Januar 2026\) sind \*\*328 Tage\*\* vergangen\./);
});

test("W18: chinesisches Neujahr ist nicht der 1. Januar", async () => {
  // Vorher: "**Neujahr** ist am **Freitag, 1. Januar 2027**."
  assert.equal(await frag("Wann ist chinesisches Neujahr 2027?"), null);
  assert.equal(await frag("When is Chinese New Year?", "en"), null);
});

test("W21: englische Namen von Feiertagen", async () => {
  // Vorher: null (Wikipedia) oder die Liste der nächsten Feiertage.
  assert.match(await frag("When is Ascension Day?", "en"), /^\*\*Ascension Day\*\* is on \*\*Thursday, 6 May 2027/);
  assert.match(await frag("When is Good Friday?", "en"), /^\*\*Good Friday\*\* is on \*\*Friday, 26 March 2027/);
  assert.match(await frag("Is Good Friday a holiday?", "en"), /^\*\*Good Friday\*\* is on/);
  assert.match(await frag("When is Pentecost?", "en"), /^\*\*Whit Sunday \(Pentecost\)\*\* is on \*\*Sunday, 16 May 2027/);
  assert.match(await frag("When is Boxing Day?", "en"), /^\*\*St\. Stephen's Day\*\* is on/);
  assert.match(await frag("When is Corpus Christi 2027?", "en"), /^\*\*Corpus Christi\*\* is on \*\*Thursday, 27 May 2027/);
});

test("W1: Wetter fuer mehrere Orte", async () => {
  // Vorher: "Einen Ort „New York und in Tokio“ finde ich nicht."
  const a = await frag("Wetter in New York und in Tokio");
  assert.match(a, /in \*\*New York\*\*/);
  assert.match(a, /in \*\*Tokio\*\*/);
  assert.equal(a.match(/Quelle: \[Open-Meteo\]/g).length, 1);
  assert.match(await frag("Weather in New York and Tokyo", "en"), /in \*\*Tokyo\*\*/);
});

test("W2: die naechsten Tage sind kein Ort", async () => {
  // Vorher: "Einen Ort „7 Tage in Berlin“ finde ich nicht."
  const a = await frag("Wetter für die nächsten 7 Tage in Berlin");
  assert.match(a, /in \*\*Berlin\*\*/);
  assert.equal(a.match(/^- \*\*/gm).length, 7);
  const b = await frag("Wetter für die nächsten 3 Tage in Berlin");
  assert.equal(b.match(/^- \*\*/gm).length, 3);
});

test("W3: Wetter in ein paar Tagen", async () => {
  // Vorher: "Wetter in 3 Tagen in Berlin" zeigte heute.
  const a = await frag("Wetter in 3 Tagen in Berlin");
  assert.match(a, /^- \*\*Samstag, 28\.11\.\*\*/m);
  assert.equal(a.match(/^- \*\*/gm).length, 1);
  assert.match(await frag("Weather in London in 10 days", "en"), /doesn't reach that far – I can look 7 days ahead/);
});

test("W4: Datum in einem Monat oder Jahr", async () => {
  // Vorher: "Heute ist Mittwoch, 25. November 2026."
  assert.equal(await frag("Welches Datum ist in einem Monat?"), "In einem Monat ist **Freitag, 25. Dezember 2026**.");
  assert.equal(await frag("Welches Datum ist in einem Jahr?"), "In einem Jahr ist **Donnerstag, 25. November 2027**.");
  assert.equal(await frag("What date is it in one month?", "en"), "In one month it will be **Friday, 25 December 2026**.");
  // Den 31. Februar gibt es nicht: dann der letzte Tag im Monat.
  const ende = await festeAntwort("Welches Datum ist in einem Monat?",
    { holen, jetzt: new Date("2027-01-31T10:00:00Z"), sprache: "de" });
  assert.equal(ende.text, "In einem Monat ist **Sonntag, 28. Februar 2027**.");
});

test("W5: der n-te Tag des Jahres", async () => {
  assert.equal(await frag("Welches Datum ist der 100. Tag des Jahres?"),
    "Der 100. Tag des Jahres 2026 ist **Freitag, 10. April 2026**.");
  assert.equal(await frag("What date is the 366th day of 2026?", "en"), "2026 has 365 days.");
});

test("W6: Kalenderwoche eines Festtags", async () => {
  // Vorher: "Wir haben Kalenderwoche 48." bzw. das Datum von Weihnachten.
  assert.equal(await frag("In welcher Kalenderwoche ist Weihnachten?"),
    "Der Freitag, 25. Dezember 2026 liegt in **Kalenderwoche 52**.");
  assert.equal(await frag("What week is Christmas?", "en"), "Friday, 25 December 2026 is in **week 52**.");
  assert.match(await frag("In welcher Kalenderwoche ist Ostern?"), /Sonntag, 28\. März 2027 liegt in \*\*Kalenderwoche 12\*\*/);
});

test("W7: Uhrzeit in und vor ein paar Stunden", async () => {
  // Vorher: "Einen Ort „3 Stunden“ finde ich gerade nicht." bzw. die Uhrzeit von jetzt.
  assert.equal(await frag("Wie spät ist es in 3 Stunden?"), "In 3 Stunden ist es **13:30 Uhr**.");
  assert.equal(await frag("Wie spät war es vor 90 Minuten?"), "Vor 90 Minuten war es **09:00 Uhr**.");
  assert.equal(await frag("What time will it be in 3 hours?", "en"), "In 3 hours it will be **13:30**.");
  assert.match(await frag("Wie spät ist es in 15 Stunden?"), /^In 15 Stunden ist es \*\*01:30 Uhr\*\* \(Donnerstag, 26\. November\)\.$/);
});

test("W8: wenn es hier 15 Uhr ist (englisch)", async () => {
  // Vorher: die Uhrzeit in New York von jetzt.
  assert.equal(await frag("If it is 3 pm here, what time is it in New York?", "en"),
    "If it's 15:00 where you are, it's **09:00** in **New York**.");
});

test("W9: Sonnenaufgang mit what time", async () => {
  // Vorher: "It's 10:30 right now (time zone Berlin)."
  assert.match(await frag("What time is sunrise in Madrid tomorrow?", "en"), /sunrise at \*\*07:48\*\*/);
});

test("W10, W19: Fuss und Zoll, degrees Fahrenheit", async () => {
  // Vorher: "10 inches is 25.4 cm." bzw. keine Antwort.
  assert.equal(await frag("5 feet 10 inches in cm", "en"), "70 inches is **177.8 cm**.");
  assert.equal(await frag("Convert 70 degrees Fahrenheit to Celsius", "en"), "70 °F is **21.11 °C**.");
});

test("W11, W12: Euro mit Cent und die Einzahl", async () => {
  // Vorher: "Für **5 Euro** ..." und "**1 euros** is ...".
  assert.match(await frag("5 Euro 50 in Dollar"), /^Für \*\*5,50 Euro\*\* bekommst du gerade etwa \*\*5,95 US-Dollar\*\*/);
  assert.match(await frag("1 euro in dollars", "en"), /^\*\*1 euro\*\* is currently about \*\*1\.08 US dollars\*\*/);
});

test("W20: Prozent von Geld", async () => {
  // Vorher: keine Antwort.
  assert.match(await frag("What is 20 percent of 250 dollars?", "en"), /\*\*50\*\*/);
  assert.match(await frag("What is 15% of $80?", "en"), /\*\*12\*\*/);
});

test("W22: englische Woerter werden nicht verbessert", async () => {
  // Vorher: "show" -> "snow" (Wetter im Ort „Show news“), "next" -> "nett".
  assert.match(await frag("Show me the news", "en"), /Meldung A/);
  assert.match(await frag("Next public holiday 2027", "en"), /^The next public holiday is \*\*New Year's Day\*\*/);
});
