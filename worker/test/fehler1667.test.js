// 16.6.7: Nachschlagetabellen ohne Prototyp (Punkt 16 der Angriffsliste) -- ohne Netz.
import assert from "node:assert/strict";
import { test } from "node:test";

import { festeAntwort } from "../src/antworten.js";

const JETZT = new Date("2026-11-24T11:00:00Z");
const holen = async () => new Response("{}", { status: 404 });

test("constructor, toString & Co. sind keine Einheiten und keine Währungen", async () => {
  // Vorher: "undefined und km ..." bzw. "Für function Object() { [native code] } → EUR ...".
  for (const frage of ["Wie viel sind 5 constructor in km?", "Rechne 5 constructor in constructor",
    "100 constructor in EUR", "Convert 10 USD to toString", "Wie viel sind 5 km in __proto__?"]) {
    for (const sprache of ["de", "en"]) {
      const a = await festeAntwort(frage, { holen, jetzt: JETZT, sprache });
      assert.doesNotMatch(a?.text ?? "", /undefined|native code|function|\[object/, frage);
    }
  }
});
