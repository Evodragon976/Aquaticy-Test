// Oeffentliche Dienste ohne Schluessel: Wetter, Nachrichten, Kurse, Feiertage, Wikipedia.
//
// Dieselben Quellen wie die Add-ons der App (aquaticy/addons.py). Die Adressen stehen
// fest im Code bzw. kommen aus erzeugt.js -- vom Nutzer kommt nur der Suchbegriff, nie
// ein Ziel. Antworten werden am Rand von Cloudflare kurz zwischengespeichert, damit ein
// voller Chat nicht jede Minute dieselbe Seite abruft (Tagesschau: hoechstens 60 je Stunde).

import { DATEN } from "./erzeugt.js";

const Q = DATEN.quellen;
export const KENNUNG = `Aquaticy-Worker/${DATEN.version} `
  + "(+https://github.com/Evodragon976/Aquaticy-Test)";

/** Ein JSON-Abruf mit Zeitlimit. Fehler werden zu `null`, nie zu einer Ausnahme. */
export async function holeJson(url, { sekunden = 8, cache = 300, holen = fetch } = {}) {
  try {
    const antwort = await holen(url, {
      headers: { "User-Agent": KENNUNG, "Accept": "application/json" },
      signal: AbortSignal.timeout(sekunden * 1000),
      cf: { cacheTtl: cache, cacheEverything: true },
    });
    if (!antwort.ok) return null;
    const daten = await antwort.json();
    return daten && typeof daten === "object" ? daten : null;
  } catch {
    return null;
  }
}

function adresse(basis, werte) {
  const url = new URL(basis);
  for (const [name, wert] of Object.entries(werte)) {
    if (wert !== undefined && wert !== null && wert !== "") url.searchParams.set(name, wert);
  }
  return url.toString();
}

const kurz = (text, n) => {
  const t = String(text || "").replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
};

// -- Wetter -------------------------------------------------------------------
export function wetterlage(code, sprache = "de") {
  const de = DATEN.wetterlage[String(code)] || "unbekannt";
  return sprache === "en" ? (WETTER_EN[String(code)] || "unknown") : de;
}

const WETTER_EN = {
  0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog",
  48: "freezing fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
  56: "light freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain",
  65: "heavy rain", 66: "light freezing rain", 67: "freezing rain", 71: "light snow",
  73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers", 81: "showers",
  82: "heavy showers", 85: "light snow showers", 86: "snow showers", 95: "thunderstorm",
  96: "thunderstorm with hail", 99: "heavy thunderstorm with hail",
};

export async function ort(name, sprache = "de", holen = fetch) {
  const daten = await holeJson(adresse(Q.geo, {
    name: kurz(name, 120), count: 1, language: sprache, format: "json",
  }), { cache: 86400, holen });
  if (!daten) return { fehler: true };    // Dienst weg -- etwas anderes als "gibt es nicht"
  const treffer = daten.results?.[0];
  if (!treffer || typeof treffer.latitude !== "number") return null;
  return {
    name: [treffer.name, treffer.admin1, treffer.country].filter(Boolean).join(", "),
    breite: treffer.latitude, laenge: treffer.longitude,
  };
}

export async function wetter(platz, holen = fetch) {
  const daten = await holeJson(adresse(Q.wetter, {
    latitude: platz.breite, longitude: platz.laenge,
    current: "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
    daily: "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    timezone: "auto", forecast_days: 7,
  }), { cache: 600, holen });
  if (!daten?.current) return null;
  const t = daten.daily || {};
  const tage = (t.time || []).map((datum, i) => ({
    datum, code: t.weather_code?.[i], max: t.temperature_2m_max?.[i],
    min: t.temperature_2m_min?.[i], regen: t.precipitation_probability_max?.[i],
  }));
  return {
    jetzt: {
      temperatur: daten.current.temperature_2m, gefuehlt: daten.current.apparent_temperature,
      code: daten.current.weather_code, wind: daten.current.wind_speed_10m,
    },
    tage,
  };
}

// -- Nachrichten --------------------------------------------------------------
export const RESSORTS = ["inland", "ausland", "wirtschaft", "sport", "wissen", "investigativ"];

export async function nachrichten({ thema = "", suche = "", menge = 5 } = {}, holen = fetch) {
  const url = suche
    ? adresse(`${Q.tagesschau}/search/`, { searchText: kurz(suche, 120), pageSize: menge })
    : adresse(`${Q.tagesschau}/news/`, { ressort: RESSORTS.includes(thema) ? thema : "" });
  const daten = await holeJson(url, { cache: 300, holen });
  if (!daten) return null;
  const roh = (suche ? daten.searchResults : daten.news) || [];
  return roh.filter((e) => e && typeof e === "object" && e.title).slice(0, menge).map((e) => ({
    titel: kurz(e.title, 200), anriss: kurz(e.firstSentence, 300),
    link: sichererLink(e.shareURL || e.detailsweb),
  }));
}

/** Nur echte https-Adressen kommen in einen Link. */
export function sichererLink(url) {
  try {
    const u = new URL(String(url || ""));
    return u.protocol === "https:" ? u.toString() : "";
  } catch {
    return "";
  }
}

// -- Kurse --------------------------------------------------------------------
export async function kurse(von, nach, holen = fetch) {
  if (!/^[A-Z]{3}$/.test(von) || !/^[A-Z]{3}$/.test(nach)) return null;
  const daten = await holeJson(adresse(Q.kurse, { base: von, symbols: nach }),
    { cache: 3600, holen });
  const kurs = daten?.rates?.[nach];
  return typeof kurs === "number" ? { kurs, stand: String(daten.date || "") } : null;
}

// -- Feiertage ----------------------------------------------------------------
export async function feiertage(jahr, land = "DE", holen = fetch) {
  if (!/^[A-Z]{2}$/.test(land) || !(jahr >= 1990 && jahr <= 2100)) return null;
  const url = Q.feiertage.replace("{jahr}", String(jahr)).replace("{land}", land);
  const daten = await holeJson(url, { cache: 86400, holen });
  if (!Array.isArray(daten)) return null;
  return daten.filter((f) => f && f.date).map((f) => ({
    datum: f.date, name: String(f.localName || f.name || ""), name_en: String(f.name || ""),
    bundesweit: f.global !== false, laender: Array.isArray(f.counties) ? f.counties : [],
  }));
}

// -- Wikipedia ----------------------------------------------------------------
export async function wikipedia(begriff, sprache = "de", holen = fetch) {
  const lang = sprache === "en" ? "en" : "de";
  const basis = Q.wikipedia.replace("{sprache}", lang);
  const suche = await holeJson(adresse(`${basis}/w/rest.php/v1/search/page`, {
    q: kurz(begriff, 200), limit: 3,
  }), { cache: 3600, holen });
  const seiten = (suche?.pages || []).filter((s) => s && (s.key || s.title));
  for (const seite of seiten.slice(0, 3)) {
    const schluessel = String(seite.key || seite.title);
    const artikel = await holeJson(
      `${basis}/api/rest_v1/page/summary/${encodeURIComponent(schluessel)}`,
      { cache: 3600, holen });
    if (!artikel || artikel.type === "disambiguation" || !artikel.extract) continue;
    return {
      titel: String(artikel.title || schluessel),
      text: kurz(artikel.extract, 1500),
      link: sichererLink(artikel.content_urls?.desktop?.page)
        || `${basis}/wiki/${encodeURIComponent(schluessel)}`,
    };
  }
  return null;
}

/** Der ganze Artikel als reiner Text (fuer Detailfragen wie "wie hoch ..."). */
export async function wikipediaVolltext(titel, sprache = "de", holen = fetch) {
  const basis = Q.wikipedia.replace("{sprache}", sprache === "en" ? "en" : "de");
  const daten = await holeJson(adresse(`${basis}/w/api.php`, {
    action: "query", prop: "extracts", explaintext: 1, exsectionformat: "plain", redirects: 1,
    format: "json", formatversion: 2, titles: kurz(titel, 250),
  }), { cache: 3600, holen });
  const text = daten?.query?.pages?.[0]?.extract;
  return typeof text === "string" ? text.slice(0, 80_000) : "";
}

/** DuckDuckGo Instant Answers: kurze Antworten und Erklaerungen (offizielle Schnittstelle). */
export async function sofortAntwort(frage, sprache = "de", holen = fetch) {
  const daten = await holeJson(adresse("https://api.duckduckgo.com/", {
    q: kurz(frage, 200), format: "json", no_html: 1, skip_disambig: 1, no_redirect: 1,
    kl: sprache === "en" ? "us-en" : "de-de",
  }), { cache: 3600, holen });
  if (!daten) return null;
  const text = kurz(daten.Answer || daten.AbstractText || daten.Definition, 1200);
  if (!text) return null;
  return { text, quelle: kurz(daten.AbstractSource || daten.DefinitionSource || "DuckDuckGo", 60),
    link: sichererLink(daten.AbstractURL || daten.DefinitionURL) };
}

/** Websuche ueber die Brave Search API -- nur mit eigenem Schluessel (BRAVE_API_KEY). */
export async function websuche(frage, schluessel, sprache = "de", holen = fetch) {
  if (!schluessel) return [];
  try {
    const antwort = await holen(adresse("https://api.search.brave.com/res/v1/web/search", {
      q: kurz(frage, 300), count: 5, search_lang: sprache === "en" ? "en" : "de",
      safesearch: "moderate", text_decorations: 0,
    }), { headers: { Accept: "application/json", "X-Subscription-Token": schluessel },
    signal: AbortSignal.timeout(8000) });
    if (!antwort.ok) return [];
    const daten = await antwort.json();
    return (daten?.web?.results || []).filter((r) => sichererLink(r.url)).slice(0, 5)
      .map((r) => ({ titel: kurz(r.title, 200), link: sichererLink(r.url),
        text: kurz(String(r.description || "").replace(/<[^>]+>/g, ""), 400) }));
  } catch {
    return [];
  }
}
