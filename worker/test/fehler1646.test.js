// 16.4.6: Fehler, die im Worker gefunden und behoben wurden -- ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { datumAntwort } from "../src/mehr.js";

const JETZT = new Date("2026-11-19T13:30:00Z");

test("Wochentag gesetzlicher Feiertage", () => {
  const tag = (f) => datumAntwort(f, "de", JETZT)?.text || "";
  assert.equal(tag("Welcher Wochentag ist Ostermontag?"), "Der 29. März 2027 ist ein **Montag**.");
  assert.equal(tag("Welcher Tag ist der Tag der Arbeit?"), "Der 1. Mai 2027 ist ein **Samstag**.");
  assert.equal(tag("Welcher Wochentag ist Karfreitag 2027?"), "Der 26. März 2027 ist ein **Freitag**.");
  assert.match(tag("Wie viele Tage bis Pfingstmontag?"), /\*\*179 Tage\*\*/);
});

test("Englischer Countdown in Wochen", () => {
  const a = datumAntwort("How many weeks until Christmas?", "en", JETZT)?.text || "";
  assert.match(a, /^\*\*36 days\*\* to go until Christmas Day – about 5 weeks/);
});
