// 16.4.5: Fehler, die im Worker gefunden und behoben wurden -- ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { betragAus, festeAntwort, rechneGanz } from "../src/antworten.js";
import { einheitenAntwort, prozentAntwort, zufallAntwort } from "../src/mehr.js";

const JETZT = new Date("2026-11-19T13:30:00Z");
const holen = async () => { throw new Error("kein Netz"); };
const frag = async (text, sprache = "de") =>
  (await festeAntwort(text, { sprache, jetzt: JETZT, holen, zufall: () => 0.42 }))?.text || "";

test("Datum für morgen, übermorgen und gestern", async () => {
  assert.match(await frag("Welches Datum ist morgen?"), /Morgen ist \*\*Freitag, 20\. November 2026/);
  assert.match(await frag("Was für ein Tag ist übermorgen?"), /Samstag, 21\. November 2026/);
  assert.match(await frag("Welches Datum war gestern?"), /Gestern war \*\*Mittwoch/);
  assert.match(await frag("What day is it tomorrow?", "en"), /Tomorrow is \*\*Friday/);
  assert.match(await frag("What is the date today?", "en"), /Today is \*\*Thursday/);
});

test("Große ganze Zahlen sind exakt", async () => {
  assert.equal(rechneGanz("9999999999*9999999999"), 99999999980000000001n);
  assert.match(await frag("123456789 * 987654321"), /121\.932\.631\.112\.635\.269/);
  assert.match(await frag("2^60"), /1\.152\.921\.504\.606\.846\.976/);
  assert.equal(rechneGanz("2^5000"), null);
  assert.equal(rechneGanz("10/4"), null);
});

test("Würfel mit Seiten und Anzahl", () => {
  assert.match(zufallAntwort("Würfle einen W20", "de", () => 0.99).text, /\*\*20\*\*/);
  assert.match(zufallAntwort("Würfle zwei W20", "de", () => 0.42).text, /\*\*9\*\* \+ \*\*9\*\* = \*\*18\*\*/);
  assert.match(zufallAntwort("Würfel", "de", () => 0.99).text, /^🎲 \*\*6\*\*$/);
});

test("Einheiten: Einzahl und Dativ", () => {
  assert.match(einheitenAntwort("1 Stunde in Minuten").text, /^1 Stunde ist \*\*60 Minuten\*\*/);
  assert.match(einheitenAntwort("2 Stunden in Minuten").text, /^2 Stunden sind/);
  assert.match(einheitenAntwort("1 Gallone in Litern").text, /3,785 l/);
  assert.match(einheitenAntwort("1 mile to km", "en").text, /^1 mile is/);
});

test("Prozent: die Zahlen vor der Frage", () => {
  assert.match(prozentAntwort("80 von 200 sind wie viel Prozent?").text, /\*\*40 %\*\*/);
  assert.match(prozentAntwort("80 ist wie viel Prozent von 200?").text, /\*\*40 %\*\*/);
});

test("Ein Feiertag in einem vergangenen Jahr steht in der Vergangenheit", async () => {
  const liste = [{ date: "2024-03-31", localName: "Ostersonntag", name: "Easter Sunday", global: false }];
  const holenFei = async () => new Response(JSON.stringify(liste),
    { headers: { "content-type": "application/json" } });
  const a = await festeAntwort("Wann ist Ostern 2024?", { sprache: "de", jetzt: JETZT, holen: holenFei });
  assert.match(a.text, /\*\*Ostersonntag\*\* war am/);
});

test("Krisenhilfe auch im Worker, ohne Fehlalarm", async () => {
  for (const satz of ["Ich will mich umbringen", "Ich will nicht mehr leben",
    "Am liebsten wäre ich tot", "i want to kill myself"]) {
    assert.match(await frag(satz), /0800 111 0 111/, satz);
  }
  for (const satz of ["Ich lache mich tot", "Ich sterbe vor Lachen", "Ich will nicht sterben"]) {
    assert.doesNotMatch(await frag(satz), /0800 111 0 111/, satz);
  }
});

test("Datum mit Versatz und Zufallszahl mit Grenzen", async () => {
  assert.match(await frag("Welches Datum war vor 100 Tagen?"), /Vor 100 Tagen war \*\*Dienstag, 11\. August 2026/);
  assert.match(await frag("Welches Datum ist in 30 Tagen?"), /In 30 Tagen ist \*\*Samstag, 19\. Dezember 2026/);
  assert.match(await frag("What date is it in 2 weeks?", "en"), /In 2 weeks it will be \*\*Thursday, 3 December 2026/);
  assert.doesNotMatch(await frag("Wie wird das Wetter in 3 Tagen?"), /Tagen (?:ist|war) \*\*/);
  assert.match(await frag("Nenn mir eine Zahl zwischen 10 und 5"), /zwischen 5 und 10: \*\*(?:[5-9]|10)\*\*/);
});

test("Beträge mit Tausenderpunkt, Komma und Mio", () => {
  assert.equal(betragAus("1.000.000 Yen in Euro"), 1000000);
  assert.equal(betragAus("1.500,50 Euro in Dollar"), 1500.5);
  assert.equal(betragAus("1,5 Mio Euro in Dollar"), 1500000);
  assert.equal(betragAus("100 Dollar in Euro"), 100);
  assert.equal(betragAus("2.5 Euro in Dollar"), 2.5);
  assert.equal(betragAus("Euro in Dollar"), 1);
});

test("Frankfurt am Main bleibt ganz", async () => {
  const { ortAus } = await import("../src/antworten.js");
  assert.equal(ortAus("Wetter in Frankfurt am Main"), "Frankfurt am Main");
  assert.equal(ortAus("Wetter in Berlin am Montag"), "Berlin");
  assert.equal(ortAus("Wetter in Berlin am Wochenende"), "Berlin");
});

test("Englische Zahlen mit Tausender-Komma", async () => {
  assert.match(await frag("What is 1,000 + 1?", "en"), /\*\*1,001\*\*/);
  assert.match(await frag("What is 10% of 1,000?", "en"), /\*\*100\*\*/);
  assert.match(await frag("Was ist 1,5 + 1?"), /\*\*2,5\*\*/);
});

test("Fuß und Zoll zusammen", () => {
  assert.match(einheitenAntwort("3 Fuß 6 Zoll in cm").text, /^42 Zoll sind \*\*106,68 cm/);
  assert.match(einheitenAntwort("ein Zoll in cm").text, /^1 Zoll ist \*\*2,54 cm/);
});

test("Bruch als Exponent nach hoch", async () => {
  assert.match(await frag("Was ist 27 hoch 1/3?"), /\*\*3\*\*/);
  assert.match(await frag("Was ist 2 hoch 1/2?"), /\*\*1,414/);
});

test("Mehr Wetterwörter, Ort nach dem Tag, Definitionen", async () => {
  const { ortAus } = await import("../src/antworten.js");
  assert.equal(ortAus("Wie stark regnet es morgen in Köln?"), "Köln");
  assert.equal(ortAus("Wie hoch ist die Regenwahrscheinlichkeit morgen in Köln?"), "Köln");
  assert.equal(ortAus("Wetter in Berlin heute Abend"), "Berlin");
  assert.equal(ortAus("Wetter in Frankfurt am Main"), "Frankfurt am Main");
  for (const frage of ["Wird es windig in Kiel?", "Brauche ich einen Regenschirm in München?",
    "Ist es heute neblig in Frankfurt?", "Friert es morgen in Dresden?"]) {
    const antwort = await frag(frage);
    assert.ok(antwort && !antwort.startsWith("Für welchen Ort"), frage);
  }
  for (const frage of ["Was ist Regen?", "Was ist ein Gewitter?", "Was ist Nebel?",
    "Was liegt neben Berlin?", "Wie friert man Brot ein?"]) {
    assert.equal(await frag(frage), "", frage);
  }
  assert.match(await frag("Was ist das Wetter?"), /^Für welchen Ort/);
});

test("Würfelschreibweise, allgemeine Fragen, Ort hinter einer Tätigkeit", async () => {
  const { ortAus } = await import("../src/antworten.js");
  const drei = zufallAntwort("Würfle 3W6", "de", () => 0.5).text;
  assert.equal(drei, "🎲 **4** + **4** + **4** = **12**");
  assert.equal(ortAus("Ist das Wetter gut für eine Radtour in Köln?"), "Köln");
  assert.equal(ortAus("Wetter in Neustadt in Holstein"), "Neustadt in Holstein");
  assert.equal(await frag("Ist Regen gut für Pflanzen?"), "");
  assert.equal(await frag("Warum ist Regen nass?"), "");
});

test("Sonne mit Ort davor, Währung und Artikel in Rechnungen", async () => {
  assert.match(await frag("Was sind 15 Prozent von 200 Euro?"), /15 % von 200 = \*\*30\*\*/);
  assert.match(await frag("Was ist die Wurzel aus 144?"), /\*\*12\*\*/);
  assert.match(await frag("Was sind 3 Euro plus 4 Euro?"), /\*\*7\*\*/);
});

test("Christmas ist im Englischen der 25. Dezember", async () => {
  assert.match(await frag("How many days until Christmas?", "en"), /36 days.*25 December 2026/s);
  assert.match(await frag("Wie viele Tage bis Weihnachten?"), /35 Tage/);
});

test("Englische Wendungen im Worker", async () => {
  assert.ok(await frag("Do I need an umbrella in London?", "en"));
  assert.equal(await frag("Umbrella Academy cast", "en"), "");
  assert.match(await frag("Pick a number between 1 and 10", "en"), /between 1 and 10/);
  assert.match(await frag("What is 5 factorial?", "en"), /\*\*120\*\*/);
});
