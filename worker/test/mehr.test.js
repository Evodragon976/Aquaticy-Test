// Tests fuer die weiteren Faehigkeiten: Prozente, Einheiten, Daten, Zufall, Weltzeit,
// Sonne, Uebersetzen, Gespraech und Folgefragen -- ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { beantworte, festeAntwort, folgefrageAufloesen, passtZu, plauderei, rechenAusdruck,
  rechne } from "../src/antworten.js";
import { datumAntwort, datumAus, einheitenAntwort, ostern, prozentAntwort, zufallAntwort }
  from "../src/mehr.js";
import { attrappe } from "./antworten.test.js";

const JETZT = new Date("2026-10-25T10:00:00Z");
const u = (...fragen) => fragen.map((content) => ({ role: "user", content }));

test("Prozente: Anteil, Auf- und Abschlag, Mehrwertsteuer", () => {
  assert.match(prozentAntwort("Wie viel Prozent sind 30 von 200?").text, /\*\*15 %\*\*/);
  assert.match(prozentAntwort("200 plus 19 %").text, /\*\*238\*\*/);
  assert.match(prozentAntwort("80 € minus 25 Prozent").text, /\*\*60\*\*/);
  assert.match(prozentAntwort("100 Euro netto in brutto").text, /\*\*119,00 € brutto\*\*/);
  assert.match(prozentAntwort("119 € brutto").text, /\*\*100,00 € netto\*\*/);
  assert.match(prozentAntwort("50 Euro mit 7 % MwSt").text, /\*\*53,50 € brutto\*\*/);
  assert.match(prozentAntwort("MwSt von 50").text, /\*\*9,50 €\*\*/);
  assert.equal(prozentAntwort("Was ist ein Prozent?"), null);
});

test("Einheiten: Laenge, Gewicht, Temperatur, Daten, Tempo -- und was nicht geht", () => {
  assert.match(einheitenAntwort("100 km in Meilen").text, /\*\*62,137 Meilen\*\*/);
  assert.match(einheitenAntwort("30 Grad in Fahrenheit").text, /\*\*86 °F\*\*/);
  assert.match(einheitenAntwort("0 kelvin in celsius").text, /\*\*-273,15 °C\*\*/);
  assert.match(einheitenAntwort("2 GB in MB").text, /\*\*2\.000 MB\*\*/);
  assert.match(einheitenAntwort("50 mph in km/h").text, /\*\*80,467 km\/h\*\*/);
  assert.match(einheitenAntwort("3 Stunden in Minuten").text, /\*\*180 Minuten\*\*/);
  assert.match(einheitenAntwort("10 Liter in kg").text, /nicht ineinander umrechnen/);
  assert.match(einheitenAntwort("6 feet in cm", "en").text, /\*\*182\.88 cm\*\*/);
  assert.equal(einheitenAntwort("100 Euro in Dollar"), null);
});

test("Rechnen: Funktionen, Konstanten, Fakultaet -- ohne eval", () => {
  assert.equal(rechne(rechenAusdruck("Sinus von 30")), 0.5);
  assert.equal(rechne(rechenAusdruck("cos 60")), 0.5);
  assert.equal(rechne(rechenAusdruck("log 1000")), 3);
  assert.equal(rechne(rechenAusdruck("5!")), 120);
  assert.equal(rechne(rechenAusdruck("5 Fakultät")), 120);
  assert.ok(Math.abs(rechne(rechenAusdruck("pi mal 2")) - 2 * Math.PI) < 1e-12);
  assert.throws(() => rechne("tan(90)"));
  assert.throws(() => rechne("ln(0)"));
  assert.throws(() => rechne("171!"));
  assert.throws(() => rechne("constructor"));
  assert.equal(rechenAusdruck("hallo!"), "");
});

test("Daten: Ostern, Countdown, Wochentag, Tage seit", () => {
  assert.equal(ostern(2026).toISOString().slice(0, 10), "2026-04-05");
  assert.equal(ostern(2027).toISOString().slice(0, 10), "2027-03-28");
  assert.equal(ostern(2000).toISOString().slice(0, 10), "2000-04-23");
  assert.match(datumAntwort("Wie viele Tage bis Weihnachten?", "de", JETZT).text, /\*\*60 Tage\*\*/);
  assert.match(datumAntwort("wie lange noch bis Ostern", "de", JETZT).text, /28\. März 2027/);
  assert.match(datumAntwort("tage bis zum 24.12.", "de", JETZT).text, /\*\*60 Tage\*\*/);
  assert.match(datumAntwort("how many days until christmas", "en", JETZT).text, /\*\*60 days\*\*/);
  assert.match(datumAntwort("Welcher Wochentag war der 9.11.1989?", "de", JETZT).text,
    /\*\*Donnerstag\*\*/);
  assert.match(datumAntwort("wie viele Tage seit dem 1.1.2026", "de", JETZT).text, /\*\*297 Tage\*\*/);
  assert.match(datumAntwort("Wie lange noch bis zu meinem Geburtstag?", "de", JETZT).text,
    /Wann hast du Geburtstag/);
  assert.equal(datumAntwort("Welcher Tag ist heute?", "de", JETZT), null);
  assert.equal(datumAus("3.5 kg", 2026)?.datum.getUTCMonth(), 4);
});

test("Zufall: Wuerfel, Muenze, Zahl, Entscheidung -- im Original geschrieben", () => {
  const null0 = () => 0, fast1 = () => 0.999;
  assert.match(zufallAntwort("Würfel!", "de", null0).text, /\*\*1\*\*/);
  assert.match(zufallAntwort("wirf zwei Würfel", "de", fast1).text, /\*\*6\*\* \+ \*\*6\*\* = \*\*12\*\*/);
  assert.match(zufallAntwort("Wirf eine Münze", "de", null0).text, /Kopf/);
  assert.match(zufallAntwort("Zufallszahl zwischen 10 und 20", "de", fast1).text, /\*\*20\*\*/);
  assert.match(zufallAntwort("Soll ich Pizza oder Pasta essen?", "de", null0).text, /\*\*Pizza\*\*/);
  assert.equal(zufallAntwort("Was ist ein Würfel?"), null);
  assert.equal(zufallAntwort("Wombats machen würfelförmigen Kot"), null);
});

test("Weltzeit, Sonne und Uebersetzen ueber nachgestellte Dienste", async () => {
  const { holen, anfragen } = attrappe({
    "geocoding-api": { results: [{ name: "New York", admin1: "New York", country: "USA",
      latitude: 40.7, longitude: -74, timezone: "America/New_York" }] },
    "api.open-meteo.com": { daily: { time: ["2026-10-25", "2026-10-26"],
      sunrise: ["2026-10-25T07:20", "2026-10-26T07:21"],
      sunset: ["2026-10-25T18:05", "2026-10-26T18:03"] } },
    "mymemory": { responseStatus: 200, responseData: { translatedText: "dog" } },
  });
  const zeit = await festeAntwort("Wie spät ist es in New York?", { holen, jetzt: JETZT });
  assert.equal(zeit.art, "weltzeit");
  assert.match(zeit.text, /\*\*06:00 Uhr\*\*/);
  const sonne = await festeAntwort("Wann geht morgen die Sonne unter in New York?",
    { holen, jetzt: JETZT });
  assert.equal(sonne.art, "sonne");
  assert.match(sonne.text, /Sonnenuntergang um \*\*18:03 Uhr\*\*/);
  const wort = await festeAntwort("Was heißt Hund auf Englisch?", { holen, jetzt: JETZT });
  assert.equal(wort.art, "uebersetzen");
  assert.match(wort.text, /„Hund“ heißt auf Englisch: \*\*dog\*\*/);
  assert.ok(anfragen.some((x) => x.includes("langpair=de%7Cen")));
  const weg = await festeAntwort("Wie spät ist es in Tokio?",
    { holen: async () => new Response("", { status: 503 }), jetzt: JETZT });
  assert.match(weg.text, /antwortet gerade nicht/);
});

test("Uebersetzen: Fehlermeldungen des Dienstes werden nicht als Uebersetzung gezeigt", async () => {
  const { holen } = attrappe({ "mymemory": { responseStatus: 200,
    responseData: { translatedText: "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS" } } });
  const a = await festeAntwort("übersetze Haus ins Französische", { holen, jetzt: JETZT });
  assert.match(a.text, /klappt gerade nicht/);
});

test("Gespraech: Frage ankuendigen, Hilfe, Fakten, Mut, Essen, Lachen, ja/nein", () => {
  assert.match(plauderei("Ich hab mal eine Frage"), /los|frag/i);
  assert.match(plauderei("kannst du mir helfen?"), /Worum geht's/);
  assert.match(plauderei("Erzähl mir einen Fun Fact"), /^Wusstest du schon\?/);
  assert.match(plauderei("motivier mich"), /^💪/);
  assert.match(plauderei("Was soll ich heute kochen?"), /\*\*/);
  assert.match(plauderei("hahaha"), /Lachen/);
  assert.match(plauderei("nein"), /Alles klar/);
  assert.equal(plauderei("Was ist ein Fakt?"), "");
});

test("Folgefragen: Pronomen, 'und ...?', Wetter, nichts erfinden", () => {
  assert.equal(folgefrageAufloesen("Wie alt ist er?", u("Wer ist Olaf Scholz?")),
    "Wie alt ist Olaf Scholz");
  assert.equal(folgefrageAufloesen("und morgen?", u("Wie wird das Wetter in München?")),
    "Wetter morgen in München");
  assert.equal(folgefrageAufloesen("und in Berlin?", u("Wetter morgen in Hamburg")),
    "Wetter morgen in Berlin");
  assert.equal(folgefrageAufloesen("und übermorgen?", u("Wetter in Rom", "und morgen?")),
    "Wetter übermorgen in Rom");
  assert.equal(folgefrageAufloesen("und Frankreich?", u("Was ist die Hauptstadt von Deutschland?")),
    "Was ist die Hauptstadt von Frankreich");
  assert.equal(folgefrageAufloesen("Wie alt ist er?", u("hallo")), "Wie alt ist er?");
  assert.equal(folgefrageAufloesen("Was ist ein Hund?", u("Wer ist Olaf Scholz?")),
    "Was ist ein Hund?");
  assert.equal(folgefrageAufloesen("Wie alt ist er?", []), "Wie alt ist er?");
  // "$&" aus der Eingabe ist Text, kein Ersetzungsmuster
  assert.equal(folgefrageAufloesen("Wie alt ist er?", u("Wer ist $& $1?")), "Wie alt ist $& $1");
  assert.equal(folgefrageAufloesen("und $&?", u("Was ist die Hauptstadt von Deutschland?")),
    "Was ist die Hauptstadt von $&");
  assert.equal(folgefrageAufloesen("Wie alt ist er?", [{ role: "assistant", content: "Wer ist X?" }]),
    "Wie alt ist er?");
});

test("Wikipedia: nur passende Artikel, sonst die andere Sprache, sonst ehrlich", async () => {
  assert.equal(passtZu("Eiffelturm")("Eiffelturm"), true);
  assert.equal(passtZu("Eifelturm")("Eiffelturm"), true);
  assert.equal(passtZu("Quaxelbrummer")("Brummkreisel"), false);
  const wiki = (sprache, titel, text) => ({
    [`${sprache}.wikipedia.org/w/rest.php`]: { pages: [{ key: titel, title: titel }] },
    [`${sprache}.wikipedia.org/api/rest_v1/page/summary`]: { type: "standard", title: titel,
      extract: text, content_urls: { desktop: { page: `https://${sprache}.wikipedia.org/wiki/x` } } },
  });
  const anders = attrappe({ ...wiki("de", "Brummkreisel", "Ein Brummkreisel ist ein Spielzeug."),
    ...wiki("en", "Quaxelbrummer", "A Quaxelbrummer is a test animal.") });
  const a = await beantworte("Was ist ein Quaxelbrummer?", { holen: anders.holen, jetzt: JETZT });
  assert.match(a.text, /test animal/);
  assert.match(a.text, /englischen Wikipedia/);
  const nah = attrappe(wiki("de", "Brummkreisel", "Ein Brummkreisel ist ein Spielzeug."));
  const b = await beantworte("Was ist ein Quaxelbrummer?", { holen: nah.holen, jetzt: JETZT });
  assert.match(b.text, /^Genau zu „Quaxelbrummer“ finde ich nichts/);
});

test("Folgefrage im ganzen Weg: beantworte nutzt den Verlauf", async () => {
  const { holen, anfragen } = attrappe({
    "search/page": { pages: [{ key: "Olaf_Scholz", title: "Olaf Scholz" }] },
    "summary/Olaf": { type: "standard", title: "Olaf Scholz",
      extract: "Olaf Scholz (* 14. Juni 1958 in Osnabrück) ist ein deutscher Politiker.",
      content_urls: { desktop: { page: "https://de.wikipedia.org/wiki/Olaf_Scholz" } } },
  });
  const a = await beantworte("Wo wurde er geboren?", { holen, jetzt: JETZT,
    verlauf: u("Wer ist Olaf Scholz?") });
  assert.match(a.text, /Osnabrück/);
  assert.ok(anfragen[0].includes("Olaf"), anfragen[0]);
});
