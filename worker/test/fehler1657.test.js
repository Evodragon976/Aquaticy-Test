// 16.5.7: Fehler, die im Worker gefunden und behoben wurden -- ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { festeAntwort } from "../src/antworten.js";

const JETZT = new Date("2026-11-22T14:10:00Z");
const holen = async () => new Response("{}", { status: 404 });
const frag = async (frage) => festeAntwort(frage, { holen, jetzt: JETZT, sprache: "en" });

test("Englische Tagesfragen mit which und 's date", async () => {
  assert.equal((await frag("Which day is tomorrow?"))?.text,
    "Tomorrow is **Monday, 23 November 2026**.");
  assert.equal((await frag("What is tomorrow's date?"))?.text,
    "Tomorrow is **Monday, 23 November 2026**.");
  assert.equal((await frag("What day was yesterday?"))?.text,
    "Yesterday was **Saturday, 21 November 2026**.");
});

test("Eine Wetterfrage mit what day bekommt kein Datum", async () => {
  // Vorher: "Today is Sunday, 22 November 2026" auf "What day will it rain in Berlin?".
  for (const frage of ["What day will it rain in Berlin?", "Which day will it rain in Berlin?"]) {
    assert.equal((await frag(frage))?.art, "wetter", frage);
  }
  assert.equal(await frag("Which day is best for a trip?"), null);
});
