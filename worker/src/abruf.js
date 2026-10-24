// Webseiten abrufen -- mit denselben Regeln wie aquaticy/netguard.py.
//
// * nur http und https, Standard-Ports, keine Zugangsdaten in der Adresse;
// * kein Ziel im eigenen oder einem privaten Netz: Namen wie localhost/.local fallen weg,
//   IP-Adressen muessen oeffentlich sein, und jeder Name wird ueber DNS-over-HTTPS
//   aufgeloest -- JEDE Adresse muss oeffentlich sein (Schutz vor SSRF);
// * geprueft wird vor jedem Schritt, also auch vor jeder Weiterleitung (hoechstens 3);
// * robots.txt gilt;
// * gelesen wird hoechstens MAX_BYTES, dann wird abgebrochen.
//
// Aus dem Worker heraus sind interne Netze ohnehin nicht erreichbar (er laeuft bei
// Cloudflare, nicht im Heimnetz). Die Pruefung bleibt trotzdem: falls jemand den Code
// anderswo laufen laesst, und damit Metadaten-Dienste und Cloudflare-interne Namen nie
// zum Ziel werden.

import { KENNUNG } from "./dienste.js";

export const MAX_BYTES = 1_500_000;
const DOH = "https://cloudflare-dns.com/dns-query";
const VERBOTENE_ENDEN = [".local", ".localhost", ".internal", ".intranet", ".lan", ".home",
  ".home.arpa", ".corp", ".onion", ".test", ".invalid", ".example"];

/** Ist diese IPv4-Adresse oeffentlich? */
export function ipv4Oeffentlich(ip) {
  const teile = ip.split(".").map(Number);
  if (teile.length !== 4 || teile.some((t) => !Number.isInteger(t) || t < 0 || t > 255)) {
    return false;
  }
  const [a, b] = teile;
  if (a === 0 || a === 10 || a === 127 || a >= 224) return false;           // dieses Netz, privat, Loopback, Multicast/reserviert
  if (a === 169 && b === 254) return false;                                  // Link-Local, Metadaten-Dienst
  if (a === 172 && b >= 16 && b <= 31) return false;                         // privat
  if (a === 192 && b === 168) return false;                                  // privat
  if (a === 100 && b >= 64 && b <= 127) return false;                        // CGNAT, Tailscale
  if (a === 192 && b === 0 && (teile[2] === 0 || teile[2] === 2)) return false; // IETF, Doku
  if (a === 198 && (b === 18 || b === 19)) return false;                     // Benchmark
  if (a === 198 && b === 51 && teile[2] === 100) return false;               // Doku
  if (a === 203 && b === 0 && teile[2] === 113) return false;                // Doku
  return true;
}

/** Ist diese IPv6-Adresse oeffentlich? Nur globale Unicast-Adressen (2000::/3). */
export function ipv6Oeffentlich(ip) {
  const t = ip.toLowerCase().replace(/^\[|\]$/g, "");
  // IPv4 in IPv6 verpackt (::ffff:10.0.0.1 usw.): sicherheitshalber nie
  if (t.includes(".")) return false;
  if (!/^[0-9a-f:]+$/.test(t)) return false;
  const erstes = parseInt(t.split(":")[0] || "0", 16);
  if (!(erstes >= 0x2000 && erstes <= 0x3fff)) return false;
  if (t.startsWith("2001:db8") || t.startsWith("2001:0db8")) return false;   // Doku
  if (/^2002:/.test(t)) return false;                                        // 6to4 (verpackt IPv4)
  if (/^2001:0{0,4}:/.test(t)) return false;                                 // Teredo
  return true;
}

/** Warum diese Adresse nicht abgerufen wird -- "" wenn sie (vor DNS) in Ordnung ist. */
export function adressProblem(roh) {
  let url;
  try {
    url = new URL(String(roh || "").trim());
  } catch {
    return "Die Adresse ist ungültig.";
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return "Nur http- und https-Adressen werden abgerufen.";
  }
  if (url.username || url.password) return "Adressen mit Zugangsdaten rufe ich nicht ab.";
  if (url.port && !["80", "443"].includes(url.port)) return "Nur die üblichen Ports 80 und 443.";
  const host = url.hostname.toLowerCase().replace(/\.$/, "");
  if (!host || !host.includes(".")) return "Die Adresse hat keinen öffentlichen Namen.";
  if (host === "localhost" || VERBOTENE_ENDEN.some((e) => host.endsWith(e))) {
    return "Adressen im eigenen Netz rufe ich nicht ab.";
  }
  if (host.startsWith("[")) {
    return ipv6Oeffentlich(host) ? "" : "Adressen im eigenen Netz rufe ich nicht ab.";
  }
  if (/^[\d.]+$/.test(host)) {
    return ipv4Oeffentlich(host) ? "" : "Adressen im eigenen Netz rufe ich nicht ab.";
  }
  // Zahlen in anderer Schreibweise (0x7f.1, 2130706433) sind keine echten Namen
  if (/^(?:0x[0-9a-f]+|\d+)(?:\.(?:0x[0-9a-f]+|\d+))*$/i.test(host)) {
    return "Die Adresse ist ungültig.";
  }
  return "";
}

/** Loest einen Namen per DNS-over-HTTPS auf. `null`, wenn das nicht ging. */
export async function aufloesen(host, holen = fetch) {
  const adressen = [];
  for (const typ of ["A", "AAAA"]) {
    try {
      const antwort = await holen(`${DOH}?name=${encodeURIComponent(host)}&type=${typ}`, {
        headers: { Accept: "application/dns-json" }, signal: AbortSignal.timeout(5000),
        cf: { cacheTtl: 60 },
      });
      if (!antwort.ok) return null;
      const daten = await antwort.json();
      for (const eintrag of daten?.Answer || []) {
        if (eintrag.type === 1 || eintrag.type === 28) adressen.push(String(eintrag.data));
      }
    } catch {
      return null;
    }
  }
  return adressen;
}

/** Prueft Adresse und alle aufgeloesten IPs. "" heisst: darf abgerufen werden. */
export async function zielProblem(roh, holen = fetch) {
  const problem = adressProblem(roh);
  if (problem) return problem;
  const host = new URL(roh).hostname.toLowerCase();
  if (/^[\d.]+$/.test(host) || host.startsWith("[")) return "";
  const adressen = await aufloesen(host, holen);
  if (adressen === null) return "Den Namen konnte ich gerade nicht auflösen.";
  if (!adressen.length) return "Diese Seite gibt es nicht.";
  const intern = adressen.some((ip) => (ip.includes(":") ? !ipv6Oeffentlich(ip)
    : !ipv4Oeffentlich(ip)));
  return intern ? "Adressen im eigenen Netz rufe ich nicht ab." : "";
}

// -- robots.txt -----------------------------------------------------------------
/** Die Regeln fuer uns aus einer robots.txt: [{erlaubt, pfad}] */
export function robotsRegeln(text) {
  const gruppen = [];
  let aktuell = null, zuletztAgent = false;
  for (const roh of String(text || "").split(/\r?\n/)) {
    const zeile = roh.replace(/#.*$/, "").trim();
    const m = /^([a-z-]+)\s*:\s*(.*)$/i.exec(zeile);
    if (!m) continue;
    const feld = m[1].toLowerCase(), wert = m[2].trim();
    if (feld === "user-agent") {
      if (!zuletztAgent) { aktuell = { agenten: [], regeln: [] }; gruppen.push(aktuell); }
      aktuell.agenten.push(wert.toLowerCase());
      zuletztAgent = true;
    } else if (aktuell && (feld === "allow" || feld === "disallow")) {
      zuletztAgent = false;
      if (wert || feld === "allow") aktuell.regeln.push({ erlaubt: feld === "allow", pfad: wert });
    } else {
      zuletztAgent = false;
    }
  }
  const eigene = gruppen.filter((g) => g.agenten.some((a) => a !== "*" && "aquaticy"
    .includes(a.replace(/[^a-z]/g, ""))));
  const passend = eigene.length ? eigene : gruppen.filter((g) => g.agenten.includes("*"));
  return passend.flatMap((g) => g.regeln);
}

function passt(pfad, muster) {
  if (!muster) return false;
  const ende = muster.endsWith("$");
  const quelle = (ende ? muster.slice(0, -1) : muster).split("*")
    .map((t) => t.replace(/[.+?^${}()|[\]\\]/g, "\\$&")).join(".*");
  return new RegExp(`^${quelle}${ende ? "$" : ""}`).test(pfad);
}

/** Darf *pfad* nach diesen Regeln gelesen werden? Laengste Regel gewinnt, Allow bei Gleichstand. */
export function robotsErlaubt(regeln, pfad) {
  let beste = null;
  for (const r of regeln) {
    if (!passt(pfad, r.pfad)) continue;
    if (!beste || r.pfad.length > beste.pfad.length
        || (r.pfad.length === beste.pfad.length && r.erlaubt)) beste = r;
  }
  return !beste || beste.erlaubt;
}

async function robotsPruefen(url, holen) {
  const ziel = new URL(url);
  try {
    const antwort = await holen(`${ziel.origin}/robots.txt`, {
      headers: { "User-Agent": KENNUNG }, redirect: "manual", signal: AbortSignal.timeout(5000),
      cf: { cacheTtl: 3600, cacheEverything: true },
    });
    if (antwort.status >= 500 || antwort.status === 401 || antwort.status === 403) return false;
    if (!antwort.ok) return true;    // keine robots.txt: alles erlaubt
    const text = (await antwort.text()).slice(0, 200_000);
    return robotsErlaubt(robotsRegeln(text), ziel.pathname + ziel.search);
  } catch {
    return false;
  }
}

// -- Abrufen ----------------------------------------------------------------------
async function begrenztLesen(antwort) {
  const leser = antwort.body?.getReader();
  if (!leser) return "";
  const teile = [];
  let menge = 0;
  for (;;) {
    const { value, done } = await leser.read();
    if (done) break;
    menge += value.byteLength;
    if (menge > MAX_BYTES) { await leser.cancel().catch(() => {}); break; }
    teile.push(value);
  }
  const alles = new Uint8Array(teile.reduce((n, t) => n + t.byteLength, 0));
  let stelle = 0;
  for (const t of teile) {
    alles.set(t, stelle);
    stelle += t.byteLength;
  }
  return new TextDecoder().decode(alles);
}

/**
 * Ruft eine oeffentliche Seite ab. Liefert {url, titel, beschreibung, text} oder
 * {fehler: "..."} -- nie eine Ausnahme.
 */
export async function seiteAbrufen(roh, holen = fetch) {
  let url = String(roh || "").trim();
  for (let schritt = 0; schritt < 4; schritt++) {
    const problem = await zielProblem(url, holen);
    if (problem) return { fehler: problem };
    if (!(await robotsPruefen(url, holen))) {
      return { fehler: "Die Seite erlaubt das Abrufen durch Programme nicht (robots.txt)." };
    }
    let antwort;
    try {
      antwort = await holen(url, {
        headers: { "User-Agent": KENNUNG, Accept: "text/html,text/plain;q=0.9" },
        redirect: "manual", signal: AbortSignal.timeout(10_000),
      });
    } catch {
      return { fehler: "Die Seite antwortet nicht." };
    }
    if ([301, 302, 303, 307, 308].includes(antwort.status)) {
      const weiter = antwort.headers.get("Location");
      if (!weiter) return { fehler: "Die Seite leitet ins Leere weiter." };
      url = new URL(weiter, url).toString();
      continue;
    }
    if (antwort.status === 401 || antwort.status === 402 || antwort.status === 403) {
      return { fehler: "Die Seite ist nur mit Anmeldung oder Abo lesbar. Das umgehe ich nicht." };
    }
    if (!antwort.ok) return { fehler: `Die Seite antwortet mit Fehler ${antwort.status}.` };
    const art = (antwort.headers.get("Content-Type") || "").toLowerCase();
    if (!/text\/html|application\/xhtml|text\/plain/.test(art)) {
      return { fehler: "Das ist keine Textseite (z. B. ein Bild oder eine Datei)." };
    }
    const roh = await begrenztLesen(antwort);
    return { url, ...(art.includes("text/plain") ? { titel: "", beschreibung: "",
      text: roh.slice(0, 50_000) } : htmlLesen(roh)) };
  }
  return { fehler: "Zu viele Weiterleitungen." };
}

// -- HTML in Text -----------------------------------------------------------------
const ENTITAETEN = { amp: "&", lt: "<", gt: ">", quot: "\"", apos: "'", nbsp: " ", auml: "ä",
  ouml: "ö", uuml: "ü", Auml: "Ä", Ouml: "Ö", Uuml: "Ü", szlig: "ß", ndash: "–", mdash: "—",
  hellip: "…", laquo: "«", raquo: "»", bdquo: "„", ldquo: "“", rdquo: "”", rsquo: "’",
  lsquo: "‘", euro: "€", copy: "©", shy: "" };

export function entschluesseln(text) {
  return String(text).replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (ganz, e) => {
    if (e[0] === "#") {
      const n = e[1].toLowerCase() === "x" ? parseInt(e.slice(2), 16) : Number(e.slice(1));
      return n > 0 && n < 0x110000 ? String.fromCodePoint(n) : "";
    }
    return Object.hasOwn(ENTITAETEN, e) ? ENTITAETEN[e] : ganz;
  });
}

const ohneTags = (html) => entschluesseln(html.replace(/<[^>]+>/g, " "))
  .replace(/\s+/g, " ").trim();

/** Titel, Beschreibung und lesbarer Text einer HTML-Seite. */
export function htmlLesen(html) {
  let h = String(html || "");
  const meta = (name) => {
    const m = new RegExp(`<meta[^>]+(?:name|property)=["']${name}["'][^>]*>`, "i").exec(h);
    const inhalt = m && /content=["']([^"']*)["']/i.exec(m[0]);
    return inhalt ? ohneTags(inhalt[1]) : "";
  };
  const titel = ohneTags((/<title[^>]*>([\s\S]*?)<\/title>/i.exec(h) || [])[1] || "")
    || meta("og:title");
  const beschreibung = meta("description") || meta("og:description");
  h = h.replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/<(script|style|noscript|svg|nav|footer|header|aside|form|template|iframe)\b[\s\S]*?<\/\1>/gi, " ");
  const kern = /<(article|main)\b[\s\S]*?<\/\1>/i.exec(h);
  if (kern) h = kern[0];
  const absaetze = [];
  for (const m of h.matchAll(/<(p|h[1-3]|li|blockquote)\b[^>]*>([\s\S]*?)<\/\1>/gi)) {
    const text = ohneTags(m[2]);
    if (text.length >= 25 || /^h/i.test(m[1])) absaetze.push(text);
  }
  const text = (absaetze.length ? absaetze.join("\n") : ohneTags(h)).slice(0, 50_000);
  return { titel: titel.slice(0, 200), beschreibung: beschreibung.slice(0, 400), text };
}
