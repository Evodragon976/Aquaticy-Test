// Tests fuer den Abruf von Webseiten: Regeln wie netguard.py, robots.txt, Grenzen.
import assert from "node:assert/strict";
import { test } from "node:test";

import { adressProblem, htmlLesen, ipv4Oeffentlich, ipv6Oeffentlich, robotsErlaubt,
  robotsRegeln, seiteAbrufen, zielProblem } from "../src/abruf.js";
import { adresseIn, webseiteAntwort } from "../src/antworten.js";
import { besterSatz, kernSaetze, saetze } from "../src/stil.js";

/** Ein nachgestelltes Netz: DNS, robots.txt und Seiten je Adresse. */
function netz({ dns = {}, seiten = {} } = {}) {
  const anfragen = [];
  const holen = async (url) => {
    const u = new URL(String(url));
    anfragen.push(u.toString());
    if (u.hostname === "cloudflare-dns.com") {
      const name = u.searchParams.get("name"), typ = u.searchParams.get("type");
      const ips = (dns[name] || []).filter((ip) => (typ === "A") === !ip.includes(":"));
      return Response.json({ Answer: ips.map((data) => ({ type: typ === "A" ? 1 : 28, data })) });
    }
    const seite = seiten[u.toString()];
    if (!seite) return new Response("nicht da", { status: 404 });
    return new Response(seite.body ?? "", { status: seite.status ?? 200,
      headers: { "Content-Type": seite.typ ?? "text/html; charset=utf-8", ...(seite.kopf || {}) } });
  };
  return { holen, anfragen };
}

test("IP-Adressen: nur oeffentliche", () => {
  for (const ip of ["10.0.0.1", "127.0.0.1", "169.254.169.254", "172.16.5.4", "192.168.1.1",
    "100.64.0.1", "0.0.0.0", "224.0.0.1", "255.255.255.255", "192.0.2.1"]) {
    assert.equal(ipv4Oeffentlich(ip), false, ip);
  }
  assert.equal(ipv4Oeffentlich("93.184.216.34"), true);
  assert.equal(ipv6Oeffentlich("2606:4700::1111"), true);
  for (const ip of ["::1", "fe80::1", "fc00::1", "::ffff:10.0.0.1", "2001:db8::1", "2002:a00::1"]) {
    assert.equal(ipv6Oeffentlich(ip), false, ip);
  }
});

test("Adressen: nur http(s), keine internen Namen, keine Tricks", () => {
  assert.equal(adressProblem("https://example.org/seite"), "");
  for (const url of ["ftp://example.org", "file:///etc/passwd", "http://localhost/",
    "http://127.0.0.1/", "http://10.1.2.3/", "http://[::1]/", "http://router.local/",
    "http://metadata.google.internal/", "http://2130706433/", "http://0x7f.1/",
    "https://user:pw@example.org/", "https://example.org:8443/", "http://intranet/",
    "kein url"]) {
    assert.notEqual(adressProblem(url), "", url);
  }
});

test("DNS: jede aufgeloeste Adresse muss oeffentlich sein", async () => {
  const { holen } = netz({ dns: { "gut.de": ["93.184.216.34"], "boese.de": ["93.184.216.34",
    "10.0.0.5"], "leer.de": [] } });
  assert.equal(await zielProblem("https://gut.de/", holen), "");
  assert.match(await zielProblem("https://boese.de/", holen), /eigenen Netz/);
  assert.match(await zielProblem("https://leer.de/", holen), /gibt es nicht/);
});

test("robots.txt: laengste Regel gewinnt, eigene Gruppe vor *", () => {
  const regeln = robotsRegeln("User-agent: *\nDisallow: /privat\nAllow: /privat/offen\n");
  assert.equal(robotsErlaubt(regeln, "/"), true);
  assert.equal(robotsErlaubt(regeln, "/privat/x"), false);
  assert.equal(robotsErlaubt(regeln, "/privat/offen/y"), true);
  const alles = robotsRegeln("User-agent: *\nDisallow: /\n");
  assert.equal(robotsErlaubt(alles, "/irgendwas"), false);
  const eigen = robotsRegeln("User-agent: *\nDisallow: /\n\nUser-agent: Aquaticy\nAllow: /\n");
  assert.equal(robotsErlaubt(eigen, "/x"), true);
  const muster = robotsRegeln("User-agent: *\nDisallow: /*.pdf$\n");
  assert.equal(robotsErlaubt(muster, "/a/b.pdf"), false);
  assert.equal(robotsErlaubt(muster, "/a/b.pdf?x"), true);
});

const HTML = `<!doctype html><html><head><title>Kaffee &amp; Kultur</title>
<meta name="description" content="Alles &uuml;ber Kaffee."><script>alert(1)</script>
<style>p{}</style></head><body><nav><p>Menü Menü Menü Menü Menü Menü Menü</p></nav>
<main><h1>Kaffee</h1><p>Kaffee ist ein schwarzes Getränk aus gerösteten Bohnen der Kaffeepflanze.</p>
<p>Die Kaffeepflanze stammt ursprünglich aus Äthiopien und wird heute in vielen Ländern angebaut.</p>
<p>In Deutschland trinkt jeder Mensch im Schnitt rund 160 Liter Kaffee im Jahr.</p></main>
<footer><p>Impressum Impressum Impressum Impressum Impressum</p></footer></body></html>`;

test("HTML: Titel, Beschreibung, Text ohne Skripte, Navigation und Fuss", () => {
  const seite = htmlLesen(HTML);
  assert.equal(seite.titel, "Kaffee & Kultur");
  assert.equal(seite.beschreibung, "Alles über Kaffee.");
  assert.match(seite.text, /Äthiopien/);
  assert.doesNotMatch(seite.text, /alert|Menü|Impressum/);
});

test("Seite abrufen: Erfolg, robots.txt, Weiterleitung nach innen, Paywall, Bilder", async () => {
  const { holen, anfragen } = netz({
    dns: { "kaffee.de": ["93.184.216.34"], "zu.de": ["93.184.216.34"],
      "weiter.de": ["93.184.216.34"], "innen.de": ["192.168.0.10"], "abo.de": ["93.184.216.34"],
      "bild.de": ["93.184.216.34"] },
    seiten: {
      "https://kaffee.de/robots.txt": { body: "User-agent: *\nDisallow: /geheim\n", typ: "text/plain" },
      "https://kaffee.de/artikel": { body: HTML },
      "https://zu.de/robots.txt": { body: "User-agent: *\nDisallow: /\n", typ: "text/plain" },
      "https://weiter.de/x": { status: 302, kopf: { Location: "https://innen.de/admin" } },
      "https://abo.de/text": { status: 402 },
      "https://bild.de/a.png": { body: "PNG", typ: "image/png" },
    },
  });
  const gut = await seiteAbrufen("https://kaffee.de/artikel", holen);
  assert.equal(gut.titel, "Kaffee & Kultur");
  assert.ok(anfragen.includes("https://kaffee.de/robots.txt"));
  assert.match((await seiteAbrufen("https://kaffee.de/geheim", holen)).fehler, /robots/);
  assert.match((await seiteAbrufen("https://zu.de/a", holen)).fehler, /robots/);
  assert.match((await seiteAbrufen("https://weiter.de/x", holen)).fehler, /eigenen Netz/);
  assert.ok(!anfragen.some((u) => u.startsWith("https://innen.de/admin")));
  assert.match((await seiteAbrufen("https://abo.de/text", holen)).fehler, /Abo/);
  assert.match((await seiteAbrufen("https://bild.de/a.png", holen)).fehler, /keine Textseite/);
});

test("Webseite in der Frage: Adresse finden und zusammenfassen", async () => {
  assert.equal(adresseIn("Was steht auf https://kaffee.de/artikel?"), "https://kaffee.de/artikel");
  assert.equal(adresseIn("lies www.kaffee.de/artikel."), "https://www.kaffee.de/artikel");
  assert.equal(adresseIn("keine Adresse"), "");
  const { holen } = netz({ dns: { "kaffee.de": ["93.184.216.34"] },
    seiten: { "https://kaffee.de/artikel": { body: HTML } } });
  const a = await webseiteAntwort("Fass https://kaffee.de/artikel zusammen", { holen });
  assert.equal(a.schritt.type, "fetch");
  assert.match(a.text, /Auf der Seite \*\*Kaffee & Kultur\*\* geht es um Folgendes/);
  assert.match(a.text, /Äthiopien/);
  assert.match(a.text, /Quelle: \[kaffee\.de\]/);
  assert.ok(a.material.length > 50);
  const b = await webseiteAntwort("lies http://192.168.0.1/", { holen });
  assert.match(b.text, /nicht lesen/);
  assert.equal(b.material, undefined);
});

test("Saetze: Abkuerzungen und Zahlen zerbrechen nichts", () => {
  assert.deepEqual(saetze("Er kam z. B. am 3. Mai. Dann ging er. Am Ende blieb nichts."),
    ["Er kam z. B. am 3. Mai.", "Dann ging er. Am Ende blieb nichts."]);
});

test("Bester Satz fuer eine Detailfrage", () => {
  const liste = ["Der Eiffelturm ist ein Aussichtsturm in Paris.",
    "Er wurde von Gustave Eiffel für die Weltausstellung 1889 errichtet.",
    "Mit einer Höhe von 330 Metern war er bis 1930 das höchste Bauwerk der Welt."];
  assert.equal(besterSatz(liste, "Wie hoch ist der Eiffelturm?", "Eiffelturm").satz, liste[2]);
  assert.equal(besterSatz(liste, "Wer hat den Eiffelturm gebaut?", "Eiffelturm").satz, liste[1]);
  assert.equal(kernSaetze("Kurz.", "", 3).length, 0);
});
