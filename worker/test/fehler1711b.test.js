// 17.1.1 (Teil 2): Würfel, Münzen und große Zahlen im Worker. Ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { festeAntwort } from "../src/antworten.js";

const JETZT = new Date("2026-11-25T09:30:00Z");
const frag = async (text, sprache = "de") =>
  (await festeAntwort(text, { holen: async () => { throw new Error("kein Netz"); }, jetzt: JETZT, sprache }))?.text;

test("Würfle zweimal und Roll a die twice würfeln zweimal", async () => {
  assert.match(await frag("Würfle zweimal"), /^🎲 \*\*[1-6]\*\* \+ \*\*[1-6]\*\* = \*\*\d+\*\*$/);
  assert.match(await frag("Würfle 3 mal"), /^🎲 (\*\*[1-6]\*\* \+ ){2}\*\*[1-6]\*\* = \*\*\d+\*\*$/);
  assert.match(await frag("Roll a die twice", "en"), /^🎲 \*\*[1-6]\*\* \+ \*\*[1-6]\*\* = \*\*\d+\*\*$/);
});

test("mehrere Münzen", async () => {
  assert.match(await frag("Wirf zwei Münzen"), /^🪙 \*\*(Kopf|Zahl)\*\*, \*\*(Kopf|Zahl)\*\*$/);
  assert.match(await frag("Flip two coins", "en"), /^🪙 \*\*(Heads|Tails)\*\*, \*\*(Heads|Tails)\*\*$/);
  assert.match(await frag("Wirf eine Münze"), /^🪙 \*\*(Kopf|Zahl)\*\*!$/);
});

test("große Ergebnisse ohne erfundene Stellen", async () => {
  assert.match(await frag("1,5 * 10^30"), /\*\*1,5 · 10³⁰\*\*/);
  assert.match(await frag("What is 10^30 / 3?", "en"), /\*\*3\.333333 · 10²⁹\*\*/);
  assert.match(await frag("2^100"), /\*\*1\.267\.650\.600\.228\.229\.401\.496\.703\.205\.376\*\*/);
});
