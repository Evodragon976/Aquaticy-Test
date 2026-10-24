// Tests fuer das Antwortsystem ohne Modell -- ohne Netz, mit nachgestellten Diensten.
import assert from "node:assert/strict";
import { test } from "node:test";

import { artVon, beantworte, festeAntwort, kw, ortAus, plauderei, rechenAusdruck, rechne,
  themaAus, waehrungenIn } from "../src/antworten.js";
import { abstand, falten, Wortschatz } from "../src/sprache.js";

/** Ein nachgestelltes fetch: Antworten je Adresse, jede Anfrage wird mitgeschrieben. */
export function attrappe(antworten) {
  const anfragen = [];
  const holen = async (url) => {
    anfragen.push(String(url));
    for (const [teil, daten] of Object.entries(antworten)) {
      if (String(url).includes(teil)) {
        return new Response(JSON.stringify(daten), { status: 200,
          headers: { "Content-Type": "application/json" } });
      }
    }
    return new Response("{}", { status: 404 });
  };
  return { holen, anfragen };
}

const JETZT = new Date("2026-10-24T10:15:00Z");

test("Tippfehler: Abstand mit Vertauschen", () => {
  assert.equal(abstand("hallo", "hlalo"), 1);
  assert.equal(abstand("wetter", "wetetr"), 1);
  assert.equal(abstand("nachrichten", "nachrichen"), 1);
  assert.equal(abstand("abc", "xyz", 1), 2);
});

test("Falten: Umlaute, langgezogene Buchstaben, Kleinschreibung", () => {
  assert.equal(falten("Hallooo SCHÖÖÖN Straße"), "hallo schoen strasse");
});

test("Wortschatz verbessert nur nahe Woerter und raet nicht bei Gleichstand", () => {
  const w = new Wortschatz(["hallo", "danke", "wetter", "wie", "gehts"]);
  assert.equal(w.verbessern("hallp"), "hallo");
  assert.equal(w.verbessern("dnake"), "danke");
  assert.equal(w.verbessern("wiegehts"), "wie gehts");
  assert.equal(w.verbessern("berlin"), "berlin");
  assert.equal(w.verbessern("ok"), "ok");
});

test("Feste Antworten: wie geschrieben und mit Tippfehlern", () => {
  for (const text of ["Hallo", "hallo!!", "Hallooo", "hallp", "Halo", "Hey Aquaticy",
    "danke", "Dnake schön", "Vielen Dank!", "wie gehts?", "wie gehst dir", "wiegehts",
    "Gute Nacht", "Tschüss", "tschuss", "wer hat dich gebaut", "wer hat dich gebaut?",
    "Was kannst du?", "was kanst du", "Guten Morgen", "guten mrogen"]) {
    assert.ok(artVon(text), `keine Art fuer: ${text}`);
    assert.ok(plauderei(text), `keine Antwort fuer: ${text}`);
  }
});

test("Feste Antworten: echte Fragen bleiben echte Fragen", () => {
  for (const text of ["Hallo, welche Cafés in Köln haben WLAN?", "Paris", "Was ist ein Hund?",
    "Wetter in Berlin", "Mars", "Wie hoch ist der Eiffelturm"]) {
    assert.equal(artVon(text), null, text);
  }
});

test("Feste Antworten auf Englisch", () => {
  assert.match(plauderei("hello", { sprache: "en" }), /\w/);
  assert.match(plauderei("thanks a lot", { sprache: "en" }), /\w/);
  assert.match(plauderei("who made you", { sprache: "en" }), /Jonas/);
  assert.match(plauderei("helo", { sprache: "en" }), /\w/);
});

test("Zustimmung zaehlt nicht, wenn Aquaticy gerade gefragt hat", () => {
  assert.ok(artVon("ok"));
  assert.equal(artVon("ok", { frageOffen: true }), null);
});

test("Nie zweimal hintereinander dieselbe Antwort", () => {
  let vorher = "";
  for (let i = 0; i < 20; i++) {
    const jetzt = plauderei("hallo");
    assert.notEqual(jetzt, vorher);
    vorher = jetzt;
  }
});

test("Rechnen: Ausdruecke aus normalem Text", () => {
  assert.equal(rechenAusdruck("was ist 12 mal (3+4)?"), "12*(3+4)");
  assert.equal(rechenAusdruck("wie viel ist 3,5 plus 1,5"), "3.5+1.5");
  assert.equal(rechenAusdruck("15% von 80"), "15%80");
  assert.equal(rechenAusdruck("Wurzel aus 144"), "sqrt(144)");
  assert.equal(rechenAusdruck("2 hoch 10"), "2^10");
  assert.equal(rechenAusdruck("1.000 geteilt durch 8"), "1000/8");
  assert.equal(rechenAusdruck("12:30"), "");
  assert.equal(rechenAusdruck("was ist ein Hund"), "");
  assert.equal(rechenAusdruck("2026"), "");
});

test("Rechnen: Ergebnis, Vorrang, Fehler", () => {
  assert.equal(rechne("12*(3+4)"), 84);
  assert.equal(rechne("2+3*4"), 14);
  assert.equal(rechne("2^3^2"), 512);
  assert.equal(rechne("-3+5"), 2);
  assert.equal(rechne("sqrt(144)"), 12);
  assert.equal(rechne("15%80"), 12);
  assert.throws(() => rechne("1/0"));
  assert.throws(() => rechne("2+"));
  assert.throws(() => rechne("alert(1)"));
  assert.throws(() => rechne("9".repeat(300)));
});

test("Rechnen ueber festeAntwort", async () => {
  const a = await festeAntwort("was ist 12 mal 12", { jetzt: JETZT });
  assert.equal(a.art, "rechnen");
  assert.match(a.text, /\*\*144\*\*/);
  const b = await festeAntwort("15 % von 80", { jetzt: JETZT });
  assert.match(b.text, /15 % von 80 = \*\*12\*\*/);
  const c = await festeAntwort("5 durch 0", { jetzt: JETZT });
  assert.match(c.text, /null/);
});

test("Uhrzeit und Datum in der Zeitzone der Verbindung", async () => {
  const a = await festeAntwort("wie spät ist es?", { jetzt: JETZT, zeitzone: "Europe/Berlin" });
  assert.equal(a.art, "zeit");
  assert.match(a.text, /12:15/);
  const b = await festeAntwort("welcher tag ist heute", { jetzt: JETZT });
  assert.match(b.text, /Samstag, 24\. Oktober 2026/);
  const c = await festeAntwort("what time is it", { jetzt: JETZT, sprache: "en",
    zeitzone: "Europe/London" });
  assert.match(c.text, /11:15/);
  const d = await festeAntwort("welche kalenderwoche haben wir", { jetzt: JETZT });
  assert.match(d.text, /Kalenderwoche 43/);
  assert.equal(kw(new Date("2026-01-01T12:00:00Z")), 1);
});

test("Wetter: Ort aus der Frage, auch mit Tippfehler im Stichwort", async () => {
  assert.equal(ortAus("Wie wird das Wetter morgen in München?"), "München");
  assert.equal(ortAus("Wetter Berlin"), "Berlin");
  assert.equal(ortAus("wetter in bad tölz am wochenende"), "bad tölz");
  const { holen, anfragen } = attrappe({
    "geocoding-api": { results: [{ name: "München", admin1: "Bayern", country: "Deutschland",
      latitude: 48.1, longitude: 11.6 }] },
    "api.open-meteo.com": {
      current: { temperature_2m: 11.4, apparent_temperature: 9.8, weather_code: 3,
        wind_speed_10m: 12 },
      daily: { time: ["2026-10-24", "2026-10-25", "2026-10-26"], weather_code: [3, 61, 0],
        temperature_2m_max: [13, 12, 15], temperature_2m_min: [6, 7, 5],
        precipitation_probability_max: [10, 80, 0] },
    },
  });
  const a = await festeAntwort("Wie wird das Wetetr morgen in München?", { holen, jetzt: JETZT });
  assert.equal(a.art, "wetter");
  assert.match(a.text, /München, Bayern/);
  assert.match(a.text, /Morgen/);
  assert.match(a.text, /Regenrisiko 80 %/);
  assert.match(a.text, /Schirm/);
  assert.ok(anfragen.some((u) => u.includes("name=M%C3%BCnchen")), anfragen.join("\n"));
  const b = await festeAntwort("wetter", { holen, jetzt: JETZT, stadt: "München" });
  assert.match(b.text, /deiner Nähe/);
  const c = await festeAntwort("wetter", { holen, jetzt: JETZT });
  assert.match(c.text, /Für welchen Ort/);
});

test("Wetter: unbekannter Ort und Dienst weg", async () => {
  const { holen } = attrappe({ "geocoding-api": { results: [] } });
  const a = await festeAntwort("Wetter in Xyzabc", { holen, jetzt: JETZT });
  assert.match(a.text, /finde ich nicht/);
});

test("Waehrungen: Namen, Codes, Tippfehler", () => {
  assert.deepEqual(waehrungenIn("100 euro in dollar"), ["EUR", "USD"]);
  assert.deepEqual(waehrungenIn("50 doller in euro"), ["USD", "EUR"]);
  assert.deepEqual(waehrungenIn("kanadische dollar in franken"), ["CAD", "CHF"]);
  assert.deepEqual(waehrungenIn("was ist ein hund"), []);
});

test("Kurse ueber festeAntwort", async () => {
  const { holen, anfragen } = attrappe({ "frankfurter": { date: "2026-10-23",
    rates: { USD: 1.1 } } });
  const a = await festeAntwort("100 Euro in Dollar", { holen, jetzt: JETZT });
  assert.equal(a.art, "kurse");
  assert.match(a.text, /Für \*\*100 Euro\*\* bekommst du gerade etwa \*\*110 US-Dollar\*\*/);
  assert.match(a.text, /100 EUR = 110 USD/);
  assert.ok(anfragen[0].includes("base=EUR") && anfragen[0].includes("symbols=USD"));
  const b = await festeAntwort("wie steht der kurs vom dollar", { holen, jetzt: JETZT });
  assert.equal(b.art, "kurse");
});

test("Feiertage: naechste, bestimmte, Jahr", async () => {
  const liste = [
    { date: "2026-04-05", localName: "Ostersonntag", name: "Easter Sunday", global: false },
    { date: "2026-04-06", localName: "Ostermontag", name: "Easter Monday", global: true },
    { date: "2026-10-03", localName: "Tag der Deutschen Einheit", name: "German Unity Day",
      global: true },
    { date: "2026-10-31", localName: "Reformationstag", name: "Reformation Day", global: false,
      counties: ["DE-BB"] },
    { date: "2026-12-25", localName: "Erster Weihnachtstag", name: "Christmas Day",
      global: true },
  ];
  const { holen, anfragen } = attrappe({ "PublicHolidays/2026/DE": liste,
    "PublicHolidays/2027/DE": [{ date: "2027-03-28", localName: "Ostersonntag",
      name: "Easter Sunday", global: true }] });
  const a = await festeAntwort("nächster Feiertag", { holen, jetzt: JETZT });
  assert.equal(a.art, "feiertage");
  assert.match(a.text, /Reformationstag/);
  assert.doesNotMatch(a.text, /Einheit/);
  const b = await festeAntwort("wann ist weihnachten", { holen, jetzt: JETZT });
  assert.match(b.text, /Erster Weihnachtstag/);
  const c = await festeAntwort("wann ist ostern", { holen, jetzt: JETZT });
  assert.match(c.text, /2027/);
  assert.ok(anfragen.some((u) => u.includes("2027")));
  const d = await festeAntwort("feiertage 2026", { holen, jetzt: JETZT });
  assert.match(d.text, /Feiertage 2026 \(DE\)/);
  const e = await festeAntwort("wie war der tag", { holen, jetzt: JETZT });
  assert.notEqual(e?.art, "feiertage");
});

test("Nachrichten: neueste, Thema, Suche, nur https-Links", async () => {
  const { holen, anfragen } = attrappe({
    "/news/": { news: [{ title: "Eins", firstSentence: "Erster Satz.",
      shareURL: "https://www.tagesschau.de/eins" }, { title: "Zwei",
      shareURL: "javascript:alert(1)" }] },
    "/search/": { searchResults: [{ title: "Treffer", shareURL: "https://x.de/t" }] },
  });
  const a = await festeAntwort("Was gibt es Neues?", { holen, jetzt: JETZT });
  assert.equal(a.art, "nachrichten");
  assert.match(a.text, /\*\*Eins\*\* — Erster Satz\. \[mehr\]\(https:\/\/www\.tagesschau\.de\/eins\)/);
  assert.doesNotMatch(a.text, /javascript/);
  await festeAntwort("Nachrichten Sport", { holen, jetzt: JETZT });
  assert.ok(anfragen.some((u) => u.includes("ressort=sport")));
  const c = await festeAntwort("nachrichen über die Bahn", { holen, jetzt: JETZT });
  assert.match(c.text, /Treffer/);
  assert.ok(anfragen.some((u) => u.includes("searchText=die+Bahn")));
});

test("Wissen: Thema aus der Frage", () => {
  assert.equal(themaAus("Was ist der Eiffelturm?"), "Eiffelturm");
  assert.equal(themaAus("wer war Marie Curie"), "Marie Curie");
  assert.equal(themaAus("Erklär mir Photosynthese"), "Photosynthese");
  assert.equal(themaAus("Wie hoch ist die Zugspitze?"), "Zugspitze");
  assert.equal(themaAus("Tell me about the Moon"), "Moon");
  assert.equal(themaAus("Schwarzes Loch"), "Schwarzes Loch");
});

test("Wissen: Wikipedia, Begriffsklaerung wird uebersprungen", async () => {
  const { holen, anfragen } = attrappe({
    "search/page": { pages: [{ key: "Bank" }, { key: "Bank_(Sitzmöbel)" }] },
    "summary/Bank_": { type: "standard", title: "Bank (Sitzmöbel)", extract: "Eine Bank ...",
      content_urls: { desktop: { page: "https://de.wikipedia.org/wiki/Bank_(Sitzm%C3%B6bel)" } } },
    "summary/Bank": { type: "disambiguation", title: "Bank", extract: "Bank steht für ..." },
  });
  const a = await beantworte("Was ist eine Bank?", { holen, jetzt: JETZT });
  assert.equal(a.art, "wissen");
  assert.match(a.text, /Bank \(Sitzmöbel\)/);
  assert.match(a.text, /Quelle: \[Wikipedia/);
  assert.ok(anfragen[0].startsWith("https://de.wikipedia.org/"));
});

test("Jede Frage bekommt eine Antwort -- auch ohne Treffer und ohne Netz", async () => {
  const holen = async () => { throw new TypeError("kein Netz"); };
  for (const frage of ["Was ist ein Quaxelbrummer?", "Wetter in Berlin", "Was gibt es Neues?",
    "100 Euro in Dollar", "Wann ist Ostern?", "", "???"]) {
    const a = await beantworte(frage, { holen, jetzt: JETZT });
    assert.ok(a.text && a.text.length > 10, `leer bei: ${frage}`);
  }
});

test("Gespraech: Witze, Befinden, 'was gibt's neues'", async () => {
  // Jeder Witz, nicht nur einer: alle Zufallswerte durchgehen
  for (const z of [0, 0.3, 0.6, 0.99]) {
    assert.ok(plauderei("erzähl mir einen Witz", { zufall: () => z }).length > 20);
    assert.ok(plauderei("tell me a joke", { sprache: "en", zufall: () => z }).length > 20);
  }
  assert.match(plauderei("ich bin so müde"), /Pause/);
  assert.match(plauderei("mir ist traurig"), /0800 111 0 111/);
  assert.equal(plauderei("ich bin Lehrer"), "");
  const { holen } = attrappe({ "/news/": { news: [{ title: "Eins" }] } });
  const a = await festeAntwort("was gibt's neues?", { holen, jetzt: JETZT });
  assert.equal(a.art, "nachrichten");
});

test("Feiertag heute/morgen: ja oder nein", async () => {
  const { holen } = attrappe({ "PublicHolidays/2026/DE": [{ date: "2026-10-25",
    localName: "Testtag", name: "Test Day", global: true }] });
  const ja = await festeAntwort("ist morgen ein feiertag?", { holen, jetzt: JETZT });
  assert.match(ja.text, /^Ja! Morgen ist \*\*Testtag\*\*/);
  const nein = await festeAntwort("ist heute ein feiertag", { holen, jetzt: JETZT });
  assert.match(nein.text, /^Nein, heute ist kein gesetzlicher Feiertag/);
});

test("Wetterdienst weg ist nicht dasselbe wie ein unbekannter Ort", async () => {
  const holen = async () => new Response("kaputt", { status: 503 });
  const a = await festeAntwort("Wetter in Köln", { holen, jetzt: JETZT });
  assert.match(a.text, /antwortet gerade nicht/);
});
