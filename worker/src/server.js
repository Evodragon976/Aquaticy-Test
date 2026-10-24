// Die Weiche des Workers: Seite, Rechtliches und /api/... -- ohne Datenbank, ohne Konten.
//
// Was die Python-App auf dem eigenen Rechner kann (virtual machine, Heimnetz, Konten,
// Gedaechtnis, Auftraege), braucht Speicher und Prozesse -- das gibt es hier nicht. Der
// Worker beantwortet Fragen: feste Antworten, Live-Dienste und Wikipedia (antworten.js),
// mit Schluessel auch ein Sprachmodell (ki.js). Gespeichert wird nichts; der Verlauf des
// Chats lebt nur in der geoeffneten Seite, die Einstellungen der Oberflaeche in einem
// Cookie im eigenen Browser.

import SEITE from "../../aquaticy/webui.html";
import APPLE from "../../aquaticy/static/apple-touch-icon.png";
import ICON32 from "../../aquaticy/static/favicon-32.png";
import ICON64 from "../../aquaticy/static/favicon-64.png";
import LOGO from "../../aquaticy/static/logo.png";
import { DATEN } from "./erzeugt.js";
import { festeAntwort, nichtsGefunden, webseiteAntwort, wissenSuchen } from "./antworten.js";
import { absage, anbieter, antworte, pruefe } from "./ki.js";
import { RECHTLICHES } from "./rechtliches.js";

export const UI_COOKIE = "aquaticy_ui";
// Feste Bilder wie web.STATIC_FILES -- nur diese Namen, kein Pfad aus der Anfrage.
const BILDER = { "/favicon.ico": ICON32, "/favicon-32.png": ICON32, "/favicon-64.png": ICON64,
  "/apple-touch-icon.png": APPLE, "/logo.png": LOGO };
const MAX_KOERPER = 64 * 1024;
const MAX_FRAGE = 8000;
const MAX_VERLAUF = 10;

// -- Antworten an den Browser ---------------------------------------------------
function kopfzeilen(art, nonce = "") {
  const skripte = nonce ? `'self' 'nonce-${nonce}'` : "'none'";
  return {
    "Content-Type": art,
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(self), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=31536000",
    "Content-Security-Policy": `default-src 'self'; script-src ${skripte}; `
      + "script-src-attr 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
      + "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
      + "form-action 'self'",
  };
}

export function json(daten, status = 200, extra = {}) {
  return new Response(JSON.stringify(daten), {
    status, headers: { ...kopfzeilen("application/json; charset=utf-8"), ...extra },
  });
}

const fehlt = () => json({ error: "Das gibt es in dieser Fassung von Aquaticy nicht.",
  error_en: "This isn't available in this version of Aquaticy." }, 404);

// Beispielfragen, die diese Fassung wirklich beantworten kann (die der App fragen nach
// Heimnetz, Cafés in der Naehe oder Flugpreisen).
const VORSCHLAEGE = {
  de: ["Wie wird das Wetter am Wochenende?", "Was sind die neuesten Nachrichten?",
    "Was ist ein schwarzes Loch?", "Wann ist Ostern?", "100 Euro in Dollar",
    "Wer war Marie Curie?", "Was sind 15 % von 240?", "Wie hoch ist die Zugspitze?",
    "Nachrichten über Sport", "Welcher Tag ist heute?", "Wie funktioniert eine Wärmepumpe?",
    "Wann ist der nächste Feiertag?"],
  en: ["What's the weather like this weekend?", "What's the latest news?",
    "What is a black hole?", "When is Easter?", "100 euros in dollars", "Who was Marie Curie?",
    "What is 15 % of 240?", "How tall is Mount Everest?", "What day is it today?",
    "How does a heat pump work?"],
};
const TEXTE = { ...DATEN.texte,
  suggestions: { normal: VORSCHLAEGE.de, pro: VORSCHLAEGE.de, code: VORSCHLAEGE.de },
  suggestions_en: { normal: VORSCHLAEGE.en, pro: VORSCHLAEGE.en, code: VORSCHLAEGE.en } };

// -- Zustand der Oberflaeche (nur im Cookie des Browsers) -------------------------
export function zustandAus(cookieKopf) {
  const stand = nurNormal(structuredClone(DATEN.zustand));
  const roh = (String(cookieKopf || "").split(/;\s*/).find((c) => c.startsWith(`${UI_COOKIE}=`))
    || "").slice(UI_COOKIE.length + 1);
  if (!roh) return stand;
  try {
    const text = atob(roh.replace(/-/g, "+").replace(/_/g, "/"));
    return nurNormal(reinigen(JSON.parse(new TextDecoder().decode(
      Uint8Array.from(text, (z) => z.charCodeAt(0)))), stand));
  } catch {
    return stand;
  }
}

/** Pro, Code und die virtual machine gibt es hier nicht. */
function nurNormal(stand) {
  stand.mode = "normal";
  stand.sandbox = false;
  stand.structured = false;
  return stand;
}

/** Wie uistate.clean: nur bekannte Felder mit erlaubten Werten; der Rest bleibt. */
export function reinigen(vorschlag, basis = DATEN.zustand) {
  const stand = structuredClone(basis);
  if (!vorschlag || typeof vorschlag !== "object" || Array.isArray(vorschlag)) return stand;
  for (const [name, erlaubt] of Object.entries(DATEN.felder)) {
    if (!(name in vorschlag)) continue;
    const wert = vorschlag[name];
    if (erlaubt === "bool") {
      if (typeof wert === "boolean") stand[name] = wert;
    } else if (erlaubt === "design") {
      if (wert && typeof wert === "object") {
        const design = {};
        for (const k of DATEN.design_schluessel) {
          const farbe = String(wert[k] || "").trim().toLowerCase();
          design[k] = /^#[0-9a-f]{6}$/.test(farbe) ? farbe : "";
        }
        stand[name] = design;
      }
    } else if (Array.isArray(erlaubt)) {
      if (erlaubt.includes(wert)) stand[name] = wert;
    } else if (Number.isInteger(wert) && wert >= erlaubt.von && wert <= erlaubt.bis) {
      stand[name] = wert;
    }
  }
  return stand;
}

function zustandCookie(stand, sicher) {
  const bytes = new TextEncoder().encode(JSON.stringify(stand));
  const wert = btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_")
    .replace(/=+$/, "");
  return `${UI_COOKIE}=${wert}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict`
    + (sicher ? "; Secure" : "");
}

// -- Die Seite ----------------------------------------------------------------
const attr = (wert) => String(wert).replace(/[^a-z0-9#,;: ()-]/gi, "");

/** Wie web.with_state: Zustand, Fassung und Texte gleich mit der Seite ausliefern. */
export function seite(stand, nonce, html = SEITE) {
  let attrs = "";
  if (["light", "dark"].includes(stand.theme)) attrs += ` data-theme="${stand.theme}"`;
  if (stand.palette) attrs += ` data-palette="${attr(stand.palette)}"`;
  if (stand.palette === "custom") {
    const d = stand.design || {};
    // Wie web._design_style: nur gepruefte Farben (#rrggbb), dieselben Variablen.
    const farbe = (k) => (/^#[0-9a-f]{6}$/.test(String(d[k] || "")) ? d[k] : "");
    const teile = [];
    if (farbe("accent")) teile.push(`--accent:${d.accent}`, `--accent-text:${d.accent}`);
    if (farbe("bg")) teile.push(`--bg:${d.bg}`, `--surface:${d.bg}`);
    if (farbe("sidebar")) teile.push(`--sidebar:${d.sidebar}`);
    const stil = teile.join(";");
    if (stil) attrs += ` style="${stil}"`;
  }
  if (["small", "large"].includes(stand.fontsize)) attrs += ` data-fontsize="${stand.fontsize}"`;
  const sprache = stand.lang === "en" ? "en" : "de";
  let h = html.replace('<html lang="de">', `<html lang="${sprache}"${attrs}>`);
  const koerper = ["start", "worker"];
  if (stand.mode === "code") koerper.push("code-mode");
  if (stand.mode === "pro") koerper.push("pro-mode");
  if (stand.tracing) koerper.push("tracing");
  if (stand.denken) koerper.push("denken");
  h = h.replace('<body class="start">', `<body class="${koerper.join(" ")}">`);
  const roh = (wert) => JSON.stringify(wert).replace(/</g, "\\u003c");
  const boot = `window.__AQUATICY_STATE__ = ${roh(stand)};`
    + `window.__AQUATICY_VERSION__ = ${roh(DATEN.version_label)};`
    + "window.__AQUATICY_INTERNAL__ = false;"
    + "window.__AQUATICY_WORKER__ = true;"
    + `window.__AQUATICY_TEXTS__ = ${roh(TEXTE)};`;
  return h.replace("<script>", `<script nonce="${nonce}">${boot}</script>\n`
    + `<script nonce="${nonce}">`);
}

function nonceNeu() {
  const bytes = crypto.getRandomValues(new Uint8Array(18));
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_");
}

// -- Was die Oberflaeche beim Start abfragt ---------------------------------------
function modellName(env) {
  const a = anbieter(env)[0];
  if (!a) return { id: "aquaticy-standard", label: "Aquaticy Standard" };
  return { id: `${a.name}/${a.modell}`,
    label: a.name === "mistral" ? "Mistral" : "NVIDIA Nemotron" };
}

function kopf(env, stand) {
  const m = modellName(env);
  const en = stand.lang === "en";
  return {
    model: m.id, model_label: m.label,
    status: en ? "No account · nothing stored" : "Ohne Konto · nichts gespeichert",
    status_title: en
      ? "This version runs on Cloudflare. Chats stay in this page only."
      : "Diese Fassung läuft bei Cloudflare. Chats bleiben nur in dieser Seite.",
  };
}

function konfiguration(env, stand) {
  const m = modellName(env);
  return {
    version: DATEN.version, version_label: DATEN.version_label,
    account: { email: "", username: "", plan: "normal", plan_label: "Normal", pro: false,
      ultra: false, ban: null },
    values: {}, key_name: "", search_key_name: "", env_path: "", problems: [],
    ha_connected: false, search_key_set: false, strong_model: m.id, strong_code_model: m.id,
    google: {}, legal_rules: Object.entries(DATEN.pruefer.regeln).map(([id, r]) => ({
      id, title: r.titel, basis: r.basis, text: r.text })),
    header: kopf(env, stand), providers: [], own_models: [], worker: true,
  };
}

// -- Eine Frage beantworten (als Strom wie /api/chat der App) -------------------
function verlaufAus(roh) {
  if (!Array.isArray(roh)) return [];
  return roh.filter((e) => e && (e.role === "user" || e.role === "assistant")
    && typeof e.content === "string" && e.content.trim())
    .slice(-MAX_VERLAUF)
    .map((e) => ({ role: e.role, content: e.content.slice(0, 4000) }));
}

export async function frageBeantworten(daten, env, kontext, senden) {
  const frage = String(daten.message || "").trim().slice(0, MAX_FRAGE);
  const sprache = daten.lang === "en" ? "en" : "de";
  const verlauf = verlaufAus(daten.history);
  const holen = kontext.holen || fetch;
  const k = { ...kontext, sprache, holen, braveKey: env.BRAVE_API_KEY || "" };
  senden({ type: "chat", session_id: kontext.chat || crypto.randomUUID() });
  if (!frage) {
    senden({ type: "chunk", text: sprache === "en" ? "Write me a question." : "Schreib mir eine Frage." });
    return;
  }
  // Eine Adresse in der Frage: die Seite lesen (Regeln wie netguard, robots.txt).
  const seite = await webseiteAntwort(frage, k);
  if (seite?.schritt) senden(seite.schritt);
  if (seite && !seite.material) {
    senden({ type: "chunk", text: seite.text });
    return;
  }
  const fest = seite ? null : await festeAntwort(frage, k);
  if (fest) {
    if (fest.schritt) senden(fest.schritt);
    senden({ type: "chunk", text: fest.text });
    return;
  }
  // Ohne Modell: Wikipedia und Netz. Mit Modell dienen sie als Material fuer die Antwort.
  const wissen = seite || await wissenSuchen(frage, sprache, k);
  if (!seite && wissen.schritt) senden(wissen.schritt);
  // Mit Schluessel: erst pruefen, dann das Modell antworten lassen.
  for (const a of anbieter(env)) {
    senden({ type: "planning" });
    const verlaufText = verlauf.map((e) => `${e.role === "user" ? "Nutzer" : "Aquaticy"}: `
      + e.content).join("\n");
    const urteil = await pruefe(a, frage, verlaufText, holen);
    senden({ type: "triage", decision: "chat" });
    if (urteil.quelle === "ausfall") continue;   // naechster Anbieter
    if (!urteil.zulaessig) {
      senden({ type: "guard", allowed: false, rule: urteil.regel });
      senden({ type: "chunk", text: absage(urteil, sprache) });
      return;
    }
    let geschrieben = "";
    try {
      geschrieben = await antworte(a, verlauf, frage, (text) => senden({ type: "chunk", text }),
        { sprache, holen, jetzt: kontext.jetzt, material: wissen.material || "",
          quelle: wissen.quelle || "" });
    } catch {
      geschrieben = "";
    }
    if (geschrieben.trim()) return;
    senden({ type: "fallback", source: a.name, target: "Aquaticy Standard" });
    break;
  }
  senden({ type: "chunk", text: wissen.text || nichtsGefunden(sprache) });
}

function strom(daten, env, kontext) {
  const { readable, writable } = new TransformStream();
  const schreiber = writable.getWriter();
  const enc = new TextEncoder();
  const senden = (ereignis) => schreiber.write(enc.encode(`data: ${JSON.stringify(ereignis)}\n\n`))
    .catch(() => {});
  const lauf = (async () => {
    try {
      await frageBeantworten(daten, env, kontext, senden);
    } catch {
      await senden({ type: "error", message: "Da ist etwas schiefgelaufen. Versuch es gleich "
        + "noch einmal." });
    }
    await senden({ type: "done", products: [], visuals: [] });
    await schreiber.close().catch(() => {});
  })();
  kontext.warten?.(lauf);
  return new Response(readable, { headers: { ...kopfzeilen("text/event-stream; charset=utf-8"),
    "X-Accel-Buffering": "no" } });
}

async function koerperLesen(request) {
  const laenge = Number(request.headers.get("Content-Length") || 0);
  if (laenge > MAX_KOERPER) return { zuGross: true };
  // Auch ohne Content-Length nie mehr als MAX_KOERPER in den Speicher lesen
  const teile = [];
  let menge = 0;
  const leser = request.body?.getReader();
  while (leser) {
    const { value, done } = await leser.read();
    if (done) break;
    menge += value.byteLength;
    if (menge > MAX_KOERPER) {
      await leser.cancel().catch(() => {});
      return { zuGross: true };
    }
    teile.push(value);
  }
  const bytes = new Uint8Array(menge);
  let stelle = 0;
  for (const t of teile) { bytes.set(t, stelle); stelle += t.byteLength; }
  const text = new TextDecoder().decode(bytes);
  try {
    const daten = JSON.parse(text || "{}");
    return { daten: daten && typeof daten === "object" && !Array.isArray(daten) ? daten : {} };
  } catch {
    return { daten: {} };
  }
}

function hilfe(en) {
  return en
    ? "**Just ask** – in your own words, typos are fine. For example:\n\n"
      + "- Knowledge: *What is a black hole?*, *How tall is Mount Everest?*\n"
      + "- Weather: *weather in Hamburg tomorrow*\n- News: *latest news*, *news about sport*\n"
      + "- Exchange rates: *100 euros in dollars*\n- Holidays: *When is Easter?*\n"
      + "- Maths: *15 % of 240*, *square root of 2*\n- Read a page: paste an https:// address\n\n"
      + "Commands: /help, /clear (new chat)."
    : "**Frag einfach** – in deinen Worten, Tippfehler sind kein Problem. Zum Beispiel:\n\n"
      + "- Wissen: *Was ist ein schwarzes Loch?*, *Wie hoch ist die Zugspitze?*\n"
      + "- Wetter: *Wetter morgen in Hamburg*\n- Nachrichten: *Was gibt es Neues?*, "
      + "*Nachrichten über Sport*\n- Kurse: *100 Euro in Dollar*\n"
      + "- Feiertage: *Wann ist Ostern?*\n- Rechnen: *15 % von 240*, *Wurzel aus 2*\n"
      + "- Seite lesen: eine https://-Adresse einfügen\n\nBefehle: /help, /clear (neuer Chat).";
}

// -- Weiche ---------------------------------------------------------------------
export async function bearbeite(request, env = {}, ctx = {}) {
  const url = new URL(request.url);
  const pfad = url.pathname.replace(/\/+$/, "") || "/";
  const methode = request.method;
  const sicher = url.protocol === "https:";
  const stand = zustandAus(request.headers.get("Cookie"));

  if (methode === "GET" && (pfad === "/" || pfad === "/index.html")) {
    const nonce = nonceNeu();
    return new Response(seite(stand, nonce), { headers: kopfzeilen("text/html; charset=utf-8",
      nonce) });
  }
  const bild = Object.hasOwn(BILDER, pfad) ? BILDER[pfad] : null;
  if (methode === "GET" && bild) {
    return new Response(bild, { headers: { ...kopfzeilen("image/png"),
      "Cache-Control": "public, max-age=86400" } });
  }
  const recht = Object.hasOwn(RECHTLICHES, pfad) ? RECHTLICHES[pfad] : null;
  if (methode === "GET" && recht) {
    return new Response(recht(stand.lang === "en" ? "en" : "de", DATEN.version_label),
      { headers: kopfzeilen("text/html; charset=utf-8") });
  }
  if (!pfad.startsWith("/api/")) return new Response("Nicht gefunden", { status: 404,
    headers: kopfzeilen("text/plain; charset=utf-8") });

  // Fremde Seiten duerfen nichts ausloesen (wie in der App: gleicher Ursprung).
  if (methode !== "GET") {
    const herkunft = request.headers.get("Origin");
    if (herkunft && herkunft !== url.origin) return json({ error: "Fremder Ursprung." }, 403);
  }

  if (methode === "GET") {
    switch (pfad) {
      case "/api/auth/status":
        return json({ consent: true, learning_version: "", authenticated: true,
          account: { email: "", username: "", plan: "normal" }, worker: true });
      case "/api/config": return json(konfiguration(env, stand));
      case "/api/header": return json(kopf(env, stand));
      case "/api/chats": return json({ chats: [], current: "" });
      case "/api/runstate": return json({ running: false, resume: false });
      case "/api/usage": return json({ limits: [], unlimited: true });
      case "/api/plugins": return json({ plugins: [] });
      case "/api/coworkers": return json({ coworkers: [], badge: 0 });
      case "/api/upgrades": return json({ notice: null });
      case "/api/account": return json({ account: null, worker: true });
      default: return fehlt();
    }
  }
  if (methode !== "POST") return json({ error: "Methode nicht erlaubt." }, 405);

  const { daten, zuGross } = await koerperLesen(request);
  if (zuGross) return json({ error: "Die Nachricht ist zu lang." }, 413);
  switch (pfad) {
    case "/api/chat": {
      if (env.BEGRENZER) {
        const ip = request.headers.get("CF-Connecting-IP") || "unbekannt";
        const { success } = await env.BEGRENZER.limit({ key: ip });
        if (!success) {
          return json({ error: "Zu viele Fragen in kurzer Zeit. Warte eine Minute und versuch es "
            + "dann noch einmal." }, 429, { "Retry-After": "60" });
        }
      }
      const cf = request.cf || {};
      return strom(daten, env, {
        stadt: typeof cf.city === "string" ? cf.city : "",
        zeitzone: typeof cf.timezone === "string" ? cf.timezone : "Europe/Berlin",
        jetzt: new Date(),
        warten: (p) => ctx.waitUntil?.(p),
      });
    }
    case "/api/prefs": {
      const neu = nurNormal(reinigen(daten, stand));
      return json({ ok: true, state: neu }, 200, { "Set-Cookie": zustandCookie(neu, sicher) });
    }
    case "/api/command": {
      const befehl = String(daten.line || "").trim().split(/\s+/)[0].toLowerCase();
      const en = stand.lang === "en";
      if (befehl === "/help" || befehl === "/hilfe") return json({ ok: true, text: hilfe(en) });
      if (befehl === "/clear" || befehl === "/neu") return json({ ok: true, clear: true, text: "" });
      return json({ ok: false, error: en
        ? "This command isn't available in this version. /help shows what works."
        : "Diesen Befehl gibt es in dieser Fassung nicht. /help zeigt, was geht." });
    }
    case "/api/stop":
    case "/api/clear":
    case "/api/consent":
      return json({ ok: true });
    default:
      return fehlt();
  }
}
