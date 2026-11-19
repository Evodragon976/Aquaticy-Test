// 16.4.5: Fehler, die im Worker gefunden und behoben wurden -- ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { festeAntwort, rechneGanz } from "../src/antworten.js";
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
