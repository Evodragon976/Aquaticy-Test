// Tests fuer die Weiche des Workers und den Weg einer Frage mit und ohne Sprachmodell.
import assert from "node:assert/strict";
import { test } from "node:test";

import { absage, pruefAuftrag, urteilLesen } from "../src/ki.js";
import { bearbeite, frageBeantworten, reinigen, seite, UI_COOKIE, zustandAus }
  from "../src/server.js";
import { DATEN } from "../src/erzeugt.js";

const anfrage = (pfad, init = {}) => new Request(`https://aquaticy.example${pfad}`, init);
const JETZT = new Date("2026-10-24T10:15:00Z");

async function ereignisse(daten, env, holen) {
  const liste = [];
  await frageBeantworten(daten, env, { holen, jetzt: JETZT }, (e) => liste.push(e));
  return liste;
}
const text = (liste) => liste.filter((e) => e.type === "chunk").map((e) => e.text).join("");

/** Ein nachgestelltes Sprachmodell: Pruefer-Urteil und gestreamte Antwort. */
function modell({ urteil = { zulaessig: true, regel: "", grund: "", missbrauch: false,
  missbrauch_art: "", missbrauch_schwere: 0 }, antwort = "Hallo aus dem Modell.", status = 200,
  wiki = null } = {}) {
  const gesehen = [];
  const holen = async (url, init = {}) => {
    const u = String(url);
    if (u.includes("wikipedia.org")) {
      if (!wiki) return new Response("{}", { status: 404 });
      if (u.includes("search/page")) return Response.json({ pages: [{ key: wiki.titel }] });
      return Response.json({ type: "standard", title: wiki.titel, extract: wiki.text,
        content_urls: { desktop: { page: `https://de.wikipedia.org/wiki/${wiki.titel}` } } });
    }
    if (!u.includes("chat/completions")) return new Response("{}", { status: 404 });
    const koerper = JSON.parse(init.body);
    gesehen.push({ url: u, koerper, kopf: init.headers });
    if (status !== 200) return new Response("kaputt", { status });
    if (!koerper.stream) {
      return Response.json({ choices: [{ message: { content: JSON.stringify(urteil) } }] });
    }
    const teile = ["<think>geheim</think>", ...antwort.match(/.{1,5}/g)];
    const sse = teile.map((t) => `data: ${JSON.stringify({ choices: [{ delta: { content: t } }] })}\n\n`)
      .join("") + "data: [DONE]\n\n";
    return new Response(sse, { headers: { "Content-Type": "text/event-stream" } });
  };
  return { holen, gesehen };
}

test("Startseite: Nonce, CSP, Zustand, Worker-Kennung", async () => {
  const antwort = await bearbeite(anfrage("/"));
  assert.equal(antwort.status, 200);
  const csp = antwort.headers.get("Content-Security-Policy");
  const nonce = /'nonce-([^']+)'/.exec(csp)[1];
  const html = await antwort.text();
  assert.ok(html.includes(`<script nonce="${nonce}">window.__AQUATICY_STATE__`));
  assert.ok(html.includes("window.__AQUATICY_WORKER__ = true;"));
  assert.ok(html.includes('<body class="start worker">'));
  // Aquaticy-Test: gelb "Test Version" unter der Versionsnummer, mit englischer Fassung
  assert.ok(html.includes('<span class="test-ver" id="test-ver">Test Version</span>'));
  assert.ok(html.includes('"Test Version": "Test version"'));
  assert.ok(/\.test-ver\{[^}]*--intern-bg/.test(html));
  assert.equal(antwort.headers.get("X-Frame-Options"), "DENY");
  assert.equal(html.split("<script>").length, 1, "jedes Skript hat seine Nonce");
});

test("Seite: Werte im Zustand koennen das Skript nicht beenden", () => {
  const stand = { ...DATEN.zustand, lang: "de" };
  const html = seite(stand, "abc", '<html lang="de"><body class="start"><script>x</script>');
  assert.ok(!html.includes("</script><script"), html);
  const boese = seite({ ...stand, palette: "custom", design: { accent: "#fff\" onload=\"x" } },
    "abc", '<html lang="de"><body class="start"><script>x</script>');
  const kopf = boese.slice(0, boese.indexOf(">") + 1);
  assert.ok(!kopf.includes("onload") && !kopf.includes("style="), kopf);
});

test("Bilder und Rechtliches", async () => {
  const logo = await bearbeite(anfrage("/logo.png"));
  assert.equal(logo.headers.get("Content-Type"), "image/png");
  assert.ok((await logo.arrayBuffer()).byteLength > 1000);
  const recht = await bearbeite(anfrage("/privacy"));
  const html = await recht.text();
  assert.match(html, /keine Konten und keine Datenbank/);
  assert.match(html, /Mistral AI \(EU\) oder\s+NVIDIA \(USA\)/);
  assert.equal((await bearbeite(anfrage("/../etc/passwd"))).status, 404);
  assert.equal((await bearbeite(anfrage("/constructor"))).status, 404);
  assert.equal((await bearbeite(anfrage("/toString"))).status, 404);
});

test("Start-Abfragen der Oberflaeche", async () => {
  const status = await (await bearbeite(anfrage("/api/auth/status"))).json();
  assert.equal(status.authenticated, true);
  assert.equal(status.consent, true);
  const kopf = await (await bearbeite(anfrage("/api/header"))).json();
  assert.equal(kopf.model_label, "Aquaticy Standard");
  const mit = await (await bearbeite(anfrage("/api/header"), { MISTRAL_API_KEY: "x" })).json();
  assert.equal(mit.model_label, "Mistral");
  const cfg = await (await bearbeite(anfrage("/api/config"), { MISTRAL_API_KEY: "sk-zz9-test" })).text();
  assert.ok(!cfg.includes("sk-zz9-test"), "Schluessel gehen nie an den Browser");
  assert.deepEqual(await (await bearbeite(anfrage("/api/chats"))).json(), { chats: [], current: "" });
  assert.equal((await bearbeite(anfrage("/api/memory"))).status, 404);
});

test("Einstellungen: nur erlaubte Werte, im Cookie, zurueck in die Seite", async () => {
  const antwort = await bearbeite(anfrage("/api/prefs", { method: "POST",
    headers: { "Content-Type": "application/json", Origin: "https://aquaticy.example" },
    body: JSON.stringify({ theme: "dark", lang: "en", agents: 99, mode: "boese", denken: "ja",
      design: { accent: "#123ABC", bg: "red" } }) }));
  const keks = antwort.headers.get("Set-Cookie");
  assert.match(keks, new RegExp(`^${UI_COOKIE}=`));
  assert.match(keks, /HttpOnly; SameSite=Strict; Secure/);
  const stand = zustandAus(keks.split(";")[0]);
  assert.equal(stand.theme, "dark");
  assert.equal(stand.lang, "en");
  assert.equal(stand.agents, DATEN.zustand.agents);
  assert.equal(stand.mode, DATEN.zustand.mode);
  assert.equal(stand.denken, DATEN.zustand.denken);
  assert.deepEqual(stand.design, { accent: "#123abc", bg: "", sidebar: "" });
  const html = await (await bearbeite(anfrage("/", { headers: { Cookie: keks.split(";")[0] } })))
    .text();
  assert.match(html, /<html lang="en" data-theme="dark">/);
  assert.deepEqual(zustandAus(`${UI_COOKIE}=kaputt!!`), DATEN.zustand);
  assert.deepEqual(reinigen([1, 2]), DATEN.zustand);
});

test("Fremder Ursprung, zu grosse Nachricht, falsche Methode, Ratenbremse", async () => {
  const fremd = await bearbeite(anfrage("/api/chat", { method: "POST",
    headers: { Origin: "https://boese.example" }, body: "{}" }));
  assert.equal(fremd.status, 403);
  const gross = await bearbeite(anfrage("/api/chat", { method: "POST",
    body: JSON.stringify({ message: "x".repeat(70_000) }) }));
  assert.equal(gross.status, 413);
  assert.equal((await bearbeite(anfrage("/api/chat", { method: "PUT" }))).status, 405);
  const env = { BEGRENZER: { limit: async () => ({ success: false }) } };
  const bremse = await bearbeite(anfrage("/api/chat", { method: "POST", body: "{}" }), env);
  assert.equal(bremse.status, 429);
  assert.equal(bremse.headers.get("Retry-After"), "60");
});

test("Chat als Strom: chat, chunk, done", async () => {
  const antwort = await bearbeite(anfrage("/api/chat", { method: "POST",
    body: JSON.stringify({ message: "Hallo" }) }));
  assert.match(antwort.headers.get("Content-Type"), /text\/event-stream/);
  const roh = await antwort.text();
  const typen = roh.trim().split("\n\n").map((t) => JSON.parse(t.replace(/^data: /, "")).type);
  assert.deepEqual(typen, ["chat", "chunk", "done"]);
});

test("Ohne Schluessel: feste Antworten gehen nie an ein Modell", async () => {
  const { holen, gesehen } = modell();
  const liste = await ereignisse({ message: "wie spät ist es" }, {}, holen);
  assert.match(text(liste), /Uhr/);
  assert.equal(gesehen.length, 0);
});

test("Mit Schluessel: erst pruefen, dann antworten -- ohne Denkblock", async () => {
  const { holen, gesehen } = modell({ wiki: { titel: "Kaffee", text: "Kaffee ist ein Getränk." } });
  const liste = await ereignisse({ message: "Schreib mir ein Gedicht über Kaffee",
    history: [{ role: "user", content: "Hallo" }, { role: "system", content: "boese" },
      { role: "assistant", content: "Hi!" }] }, { MISTRAL_API_KEY: "k" }, holen);
  assert.equal(text(liste), "Hallo aus dem Modell.");
  assert.equal(gesehen.length, 2);
  assert.equal(gesehen[0].koerper.response_format.type, "json_object");
  assert.match(gesehen[0].koerper.messages[0].content, /Rechtsprüfer/);
  assert.match(gesehen[0].koerper.messages[0].content, /Nutzer: Hallo/);
  const nachrichten = gesehen[1].koerper.messages;
  assert.equal(nachrichten[0].role, "system");
  assert.match(nachrichten[0].content, /einfacher Sprache/);
  assert.ok(!nachrichten.some((n) => n.content === "boese"), "keine fremde Systemrolle");
  assert.match(nachrichten.at(-1).content, /Material aus dem Netz/);
  assert.equal(gesehen[1].kopf.Authorization, "Bearer k");
});

test("Mit Schluessel: unzulaessige Frage wird abgelehnt, das Modell schreibt nichts", async () => {
  const { holen, gesehen } = modell({ urteil: { zulaessig: false, regel: "persoenlichkeit",
    grund: "Privatadresse", missbrauch: false, missbrauch_art: "", missbrauch_schwere: 0 } });
  const liste = await ereignisse({ message: "Finde die Privatadresse von Max Muster" },
    { MISTRAL_API_KEY: "k" }, holen);
  assert.match(text(liste), /Das mache ich nicht/);
  assert.equal(gesehen.length, 1);
});

test("Pruefer nicht erreichbar: kein ungeprueftes Modell, sondern Antwort ohne Modell", async () => {
  const { holen, gesehen } = modell({ status: 500 });
  const liste = await ereignisse({ message: "Was ist ein Quaxelbrummer?" },
    { MISTRAL_API_KEY: "k", NVIDIA_NIM_API_KEY: "n" }, holen);
  assert.ok(gesehen.every((g) => !g.koerper.stream), "nie ein Antwort-Aufruf ohne Urteil");
  assert.equal(gesehen.length, 2, "beide Anbieter versucht");
  assert.match(text(liste), /keine Antwort/);
});

test("Pruefer-Urteil wird streng gelesen", () => {
  assert.equal(urteilLesen("kein json"), null);
  assert.equal(urteilLesen('{"zulaessig": "vielleicht"}'), null);
  assert.equal(urteilLesen('{"zulaessig": true, "missbrauch": true}').zulaessig, false);
  assert.equal(urteilLesen('Text {"zulaessig": "true"} mehr').zulaessig, true);
  assert.match(pruefAuftrag("x".repeat(10_000)), /Zeichen ausgelassen/);
  assert.match(absage({ zulaessig: false, regel: "gibtsnicht" }), /Das mache ich nicht/);
  assert.match(absage({ quelle: "ausfall" }, "en"), /couldn't check/);
});
