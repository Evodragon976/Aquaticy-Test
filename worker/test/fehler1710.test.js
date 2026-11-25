// 17.1.0: Daten, die es nicht gibt -- vorher rechnete Date.UTC einfach weiter. Ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { festeAntwort } from "../src/antworten.js";

const JETZT = new Date("2026-11-25T11:00:00Z");
const holen = async () => new Response("{}", { status: 404 });
const frag = async (frage, sprache = "de") => (await festeAntwort(frage, { holen, jetzt: JETZT, sprache }))?.text ?? "";

test("ein Datum, das es nicht gibt, wird nicht zum naechsten Tag", async () => {
  // Vorher: "Der 1. März 2027 ist ein Montag." bzw. "Der Freitag, 1. Mai 2026 war vor 208 Tagen."
  assert.equal(await frag("Welcher Wochentag ist der 29.02.2027?"),
    "Den 29.02.2027 gibt es nicht – 2027 ist kein Schaltjahr.");
  assert.equal(await frag("Wie viele Tage bis 31.04.2026?"), "Den 31.04.2026 gibt es nicht.");
  assert.equal(await frag("Welcher Wochentag ist der 29.02.0000?"), "Den 29.02.0000 gibt es nicht.");
  assert.match(await frag("What day was 29.02.2027?", "en"), /doesn't exist – 2027 isn't a leap year/);
});

test("Jahre und Zahlenketten werden richtig gelesen", async () => {
  // "05.05.90" ist 1990 (wie in Python), nicht 2090.
  assert.match(await frag("Welcher Wochentag war der 05.05.90?"), /5\. Mai 1990 war ein \*\*Samstag\*\*/);
  // Ohne Jahr: der 29. Februar im naechsten Schaltjahr.
  assert.match(await frag("Welcher Wochentag ist der 29.02.?"), /29\. Februar 2028 ist ein \*\*Dienstag\*\*/);
  // "1.1.1" ist kein 1. Januar dieses Jahres.
  assert.doesNotMatch(await frag("Welcher Wochentag ist der 1.1.1?"), /1\. Januar 2026/);
});

test("die Kalenderwoche gehoert zum gefragten Tag und zur Zeitzone", async () => {
  // Vorher: "Wir haben Kalenderwoche 48." -- egal, nach welchem Tag gefragt war.
  assert.equal(await frag("Welche Kalenderwoche ist der 1.1.2027?"),
    "Der Freitag, 1. Januar 2027 liegt in **Kalenderwoche 53** von 2026.");
  assert.equal(await frag("Kalenderwoche 31.12.2024"),
    "Der Dienstag, 31. Dezember 2024 liegt in **Kalenderwoche 1** von 2025.");
  assert.equal(await frag("Welche Kalenderwoche ist der 29.02.2027?"),
    "Den 29.02.2027 gibt es nicht – 2027 ist kein Schaltjahr.");
  assert.match(await frag("Welche Kalenderwoche haben wir?"), /^Wir haben \*\*Kalenderwoche 48\*\*/);
  // Sonntag 23:30 UTC ist in Berlin schon Montag -- und damit Woche 49.
  const montag = await festeAntwort("Welche Kalenderwoche haben wir?",
    { holen, jetzt: new Date("2026-11-29T23:30:00Z"), sprache: "de" });
  assert.match(montag.text, /^Wir haben \*\*Kalenderwoche 49\*\*\. Heute ist Montag/);
});

test("Guten Morgen ist kein morgen", async () => {
  // Vorher: "Morgen ist Donnerstag, 26. November 2026." auf "Guten Morgen, welches Datum ist heute?"
  assert.match(await frag("Guten Morgen, welches Datum ist heute?"),
    /^Heute ist \*\*Mittwoch, 25\. November 2026\*\*/);
  assert.match(await frag("Guten Morgen, welche Kalenderwoche haben wir?"),
    /^Wir haben \*\*Kalenderwoche 48\*\*/);
  assert.match(await frag("Welches Datum ist morgen?"), /^Morgen ist \*\*Donnerstag, 26\. November 2026\*\*/);
  assert.match(await frag("Welches Datum ist heute Morgen?"), /^Heute ist \*\*Mittwoch, 25\. November 2026\*\*/);
});
