// Antworten ohne Sprachmodell: feste Antworten, Rechnen, Zeit, Wetter, Kurse, Feiertage,
// Nachrichten und Wissen aus Wikipedia -- auch bei Tippfehlern.
//
// Reihenfolge: erst das, was sofort und sicher geht (Hallo, Danke, 3 * 4, Uhrzeit), dann
// die Dienste mit Live-Daten, dann Wikipedia. Jede Frage bekommt eine Antwort: findet
// sich nichts, sagt Aquaticy das ehrlich und nennt, wobei es helfen kann.

import { DATEN } from "./erzeugt.js";
import * as dienste from "./dienste.js";
import { erlaubteFehler, abstand, falten, musterFalten, woerter, woerterAusMuster,
  Wortschatz } from "./sprache.js";
import { ABSCHLUSS, EINSTIEG, besterSatz, eine, kernSaetze, saetze } from "./stil.js";
import { seiteAbrufen } from "./abruf.js";

// -- Feste Antworten ----------------------------------------------------------
// Was die App kann, kann diese Fassung nur zum Teil. Diese Arten bekommen deshalb
// eigene Antworten -- die aus smalltalk.py sprechen von Websuche und Code-Modus.
const EIGENE = {
  faehigkeiten: [
    "Ich beantworte deine Fragen: Wissen aus Wikipedia, Wetter, Nachrichten, Wechselkurse, "
      + "Feiertage, Rechnen, Datum und Uhrzeit. Frag einfach drauflos.",
    "Frag mich etwas! Ich schlage nach, rechne, sage dir das Wetter oder die neuesten "
      + "Nachrichten.",
    "Ich kenne mich aus mit Wissen, Wetter, Nachrichten, Kursen, Feiertagen und Zahlen. "
      + "Tippfehler sind kein Problem.",
  ],
  identitaet: [
    "Ich bin Aquaticy, ein KI-Assistent von Jonas. Wobei kann ich dir helfen?",
    "Ich heiße Aquaticy! Ich beantworte Fragen und schlage für dich nach.",
    "Aquaticy — so heiße ich. Frag mich etwas, ich suche dir die Antwort.",
  ],
  fremde_ki: [
    "Nein, ich bin Aquaticy — eine KI von Jonas.",
    "Ich bin Aquaticy, nicht der Assistent, den du meinst. Was möchtest du wissen?",
  ],
};

const EN = {
  schoepfer: ["Jonas built me. I'm Aquaticy, your AI assistant.",
    "My developer is Jonas. He created Aquaticy so you get answers with real sources."],
  fremde_ki: ["No, I'm Aquaticy — an AI made by Jonas.",
    "I'm Aquaticy, not the assistant you mean. What would you like to know?"],
  identitaet: ["I'm Aquaticy, an AI assistant made by Jonas. How can I help?",
    "My name is Aquaticy! I answer questions and look things up for you."],
  mensch: ["I'm not a human but an AI — Aquaticy, made by Jonas.",
    "No, I'm an artificial intelligence. My name is Aquaticy."],
  faehigkeiten: ["I answer your questions: knowledge from Wikipedia, weather, news, exchange "
    + "rates, public holidays, maths, date and time. Just ask.",
  "Ask me something! I look things up, calculate, and tell you the weather or the latest news."],
  wie_gehts: ["I'm doing well, thanks! How about you?",
    "All good here — ready for your questions. How are you?"],
  morgen: ["Good morning! What can I do for you today?", "Morning! How can I help?"],
  abend: ["Good evening! What would you like to know?", "Evening! How can I help?"],
  begruessung: ["Hello! How can I help you?", "Hi! What would you like to know?",
    "Hey! Ask me anything."],
  danke: ["You're welcome!", "Happy to help!", "Anytime — just ask if you need more."],
  gute_nacht: ["Good night! Sleep well.", "Sleep well — see you soon!"],
  abschied: ["Bye! See you soon.", "Take care!", "See you next time!"],
  lob: ["Thank you, that's kind!", "Thanks! Happy to help."],
  entschuldigung: ["No problem at all!", "All good — no worries."],
  wer_bin_ich: ["I don't know who you are — and I don't store anything about you."],
  alter: ["I don't have a birthday like you do — I'm a computer program."],
  herkunft: ["I live on the internet — on Cloudflare servers, to be exact."],
  sprachen: ["I speak German and English."],
  gefuehle: ["I don't have feelings, but I'm glad to help you."],
  lieblings: ["As an AI I have no favourites — but blue fits my name."],
  langeweile: ["How about a fun fact? Ask me about any topic, and I'll look it up."],
  test: ["Everything works! I'm here and ready.", "Pong! All good. What would you like to know?"],
  zustimmung: ["Great! Anything else?", "Alright. What's next?", "Okay! Just ask if you need more."],
};

// Englische Nachrichten, die smalltalk.py nicht kennt -- dieselben Arten.
const EN_MUSTER = {
  schoepfer: "who\\s+(?:made|built|created|programmed|developed)\\s+you|who\\s+is\\s+your\\s+"
    + "(?:creator|developer|maker)",
  identitaet: "who\\s+are\\s+you|what\\s+(?:is|'s)\\s+your\\s+name|what\\s+are\\s+you",
  mensch: "are\\s+you\\s+(?:a\\s+)?(?:human|bot|robot|machine|ai|real|person)",
  faehigkeiten: "what\\s+can\\s+you\\s+do|how\\s+can\\s+you\\s+help(?:\\s+me)?|help",
  wie_gehts: "how\\s+are\\s+you(?:\\s+doing)?(?:\\s+today)?|how(?:'s|\\s+is)\\s+it\\s+going|"
    + "what'?s\\s+up|wassup|how\\s+do\\s+you\\s+do",
  morgen: "good\\s+morning|morning",
  abend: "good\\s+evening|evening",
  begruessung: "hello(?:\\s+there)?|hi(?:\\s+there)?|hey(?:\\s+there)?|howdy|greetings|"
    + "good\\s+(?:day|afternoon)",
  danke: "thanks?(?:\\s+you)?(?:\\s+(?:so\\s+much|very\\s+much|a\\s+lot))?|thx|ty|cheers|"
    + "many\\s+thanks",
  gute_nacht: "good\\s+night|nighty?\\s+night|sleep\\s+well",
  abschied: "goodbye|good\\s+bye|bye(?:\\s+bye)?|see\\s+(?:you|ya)(?:\\s+(?:later|soon))?|"
    + "take\\s+care|later",
  lob: "you(?:'re|\\s+are)\\s+(?:great|awesome|amazing|the\\s+best|smart|cool|nice)|"
    + "good\\s+(?:job|bot)|well\\s+done|i\\s+love\\s+you",
  entschuldigung: "sorry|my\\s+bad|oops|apologies",
  wer_bin_ich: "who\\s+am\\s+i|do\\s+you\\s+know\\s+me",
  alter: "how\\s+old\\s+are\\s+you|when\\s+were\\s+you\\s+born",
  herkunft: "where\\s+(?:are\\s+you\\s+from|do\\s+you\\s+live)",
  gefuehle: "do\\s+you\\s+have\\s+feelings|are\\s+you\\s+(?:happy|sad|tired|lonely)",
  langeweile: "i(?:'m|\\s+am)\\s+bored|bored",
  zustimmung: "ok(?:ay)?|alright|got\\s+it|nice|great|cool|perfect|sure|understood",
};

function verbund(muster) {
  return new RegExp(`^(?:${musterFalten(muster)})$`, "i");
}

const ARTEN = DATEN.smalltalk.map((art) => ({
  name: art.name,
  muster: verbund(art.muster),
  en: EN_MUSTER[art.name] ? verbund(EN_MUSTER[art.name]) : null,
  antworten: EIGENE[art.name] || art.antworten,
  nichtBeiOffenerFrage: art.nicht_bei_offener_frage,
}));

const ANREDE = new RegExp(musterFalten(DATEN.anrede), "i");

// -- Stichwoerter der Dienste -------------------------------------------------
const STICH = {
  wetter: ["wetter", "regen", "regnet", "regnen", "schnee", "schneit", "gewitter", "vorhersage",
    "wettervorhersage", "temperatur", "temperaturen", "sonnig", "bewoelkt", "weather", "rain",
    "raining", "snow", "forecast", "temperature", "sunny"],
  zeit: ["uhrzeit", "spaet", "uhr", "datum", "wochentag", "time", "date", "kalenderwoche"],
  nachrichten: ["nachrichten", "news", "neuigkeiten", "schlagzeilen", "tagesschau", "headlines",
    "meldungen", "aktuelles"],
  feiertage: ["feiertag", "feiertage", "feiertagen", "holiday", "holidays", "ostern",
    "weihnachten", "pfingsten", "karfreitag", "ostermontag", "pfingstmontag", "himmelfahrt",
    "fronleichnam", "neujahr", "reformationstag", "allerheiligen", "christmas", "easter",
    "einheit", "buss", "bettag"],
  kurse: ["kurs", "wechselkurs", "umrechnen", "exchange", "rate", "waehrung", "currency"],
};

// Echte Woerter, die einem Stichwort aehneln, aber etwas anderes meinen.
const KEIN_TIPPFEHLER = new Set(["wetten", "wette", "vetter", "kurz", "kurze", "kurzem",
  "kuss", "kurse", "uhren", "date", "datei", "dateien", "news", "regel", "regeln", "rat",
  "rate", "raten", "regal", "neuen", "neues", "time", "times", "seen"]);

const FRAGEWOERTER = ["was", "wer", "wie", "wo", "wann", "warum", "wieso", "weshalb", "welche",
  "welcher", "welches", "woher", "wohin", "wieviel", "wieviele", "viel", "viele", "ist", "sind",
  "war", "waren", "hat", "haben", "kann", "kannst", "gibt", "es", "heute", "morgen",
  "uebermorgen", "in", "der", "die", "das", "den", "dem", "ein", "eine", "einen", "mir", "mich",
  "bitte", "und", "oder", "von", "fuer", "zu", "nach", "mit", "bei", "aus", "ueber", "what",
  "who", "how", "where", "when", "why", "which", "is", "are", "the", "a", "an", "of", "for",
  "to", "in", "on", "at", "me", "please", "today", "tomorrow", "erklaere", "erklaer", "sag",
  "zeig", "nenn", "neueste", "neuesten", "letzte", "aktuelle", "aktuellen", "naechste",
  "naechster", "naechsten", "wird", "werden", "wetter", "regnet"];

const WORTSCHATZ = new Wortschatz([
  ...DATEN.smalltalk.flatMap((art) => woerterAusMuster(art.muster)),
  ...Object.values(EN_MUSTER).flatMap(woerterAusMuster),
  ...Object.values(STICH).flat(),
  ...FRAGEWOERTER,
]);
for (const wort of KEIN_TIPPFEHLER) WORTSCHATZ.dazu(wort);

/** Wie smalltalk.normalisieren: gefaltet, ohne Satzzeichen an den Enden, ohne Anrede. */
export function normalisieren(text) {
  let t = falten(text).split(/\s+/).filter(Boolean).join(" ");
  const raender = /^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu;
  t = t.replace(raender, "");
  t = t.replace(ANREDE, "").trim();
  return t.replace(raender, "");
}

/** Die Art einer einfachen Nachricht -- erst wie geschrieben, dann mit Tippfehlern. */
export function artVon(text, { frageOffen = false } = {}) {
  const kern = normalisieren(text);
  if (!kern || kern.length > 80) return null;
  const versuche = [kern];
  const alt = kern.split(" ");
  // Wie viele Woerter umgedeutet werden ("wiegehts" -> "wie gehts" zaehlt als eines)
  const geaendert = alt.filter((w) => WORTSCHATZ.varianten(w).some((v) => v !== w)).length;
  // Mehr als die Haelfte umgedeutet (bei einem Wort: mehr als das eine)? Dann ist das
  // keine Plauderei mehr, sondern geraten.
  if (geaendert && geaendert <= Math.max(1, Math.floor(alt.length / 2))) {
    for (const variante of WORTSCHATZ.varianten(kern)) {
      const neu = normalisieren(variante);
      if (neu !== kern) versuche.push(neu);
    }
  }
  for (const versuch of versuche) {
    for (const art of ARTEN) {
      if (art.nichtBeiOffenerFrage && frageOffen) continue;
      if (art.muster.test(versuch) || (art.en && art.en.test(versuch))) return art;
    }
  }
  return null;
}

const zuletzt = new Map();

/** Eine zufaellige Antwort -- nie dieselbe wie beim letzten Mal (je Worker-Instanz). */
export function waehle(liste, schluessel, zufall = Math.random) {
  const vorher = zuletzt.get(schluessel);
  const auswahl = liste.length > 1 ? liste.filter((a) => a !== vorher) : liste;
  const antwort = auswahl[Math.floor(zufall() * auswahl.length)] || liste[0];
  zuletzt.set(schluessel, antwort);
  return antwort;
}

// Was smalltalk.py nicht kennt, ein Gespraech aber oft hat: Witze und wie es einem geht.
const WITZE = {
  de: ["Was macht ein Pirat am Computer? Er drückt die Enter-Taste. 🏴‍☠️",
    "Warum können Geister so schlecht lügen? Weil man durch sie hindurchsieht.",
    "Treffen sich zwei Magneten. Sagt der eine: „Was soll ich heute bloß anziehen?“",
    "Wie nennt man einen Bumerang, der nicht zurückkommt? Stock.",
    "Was ist rot und schlecht für die Zähne? Ein Ziegelstein.",
    "Warum gehen Ameisen nicht in die Kirche? Sie sind in Sekten."],
  en: ["Why don't skeletons fight each other? They don't have the guts.",
    "What do you call a fake noodle? An impasta.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I told my computer a joke about UDP. I'm not sure it got it."],
};
const BEFINDEN = [
  [/muede|erschoepft|tired|exhausted/, ["Dann gönn dir eine Pause – ein Glas Wasser und kurz "
    + "frische Luft wirken oft Wunder. Kann ich dir noch schnell bei etwas helfen?",
  "Then take a break – a glass of water and some fresh air often help. Anything I can quickly do for you?"]],
  [/traurig|einsam|sad|lonely/, ["Das tut mir leid. Magst du erzählen, was los ist? Wenn es "
    + "dir richtig schlecht geht, hilft die Telefonseelsorge rund um die Uhr: 0800 111 0 111.",
  "I'm sorry to hear that. Want to talk about it? If you're really struggling, please reach "
    + "out to someone you trust or a local helpline."]],
  [/gestresst|stress|stressed/, ["Stress ist anstrengend. Atme einmal tief durch und nimm dir "
    + "eine Sache nach der anderen vor. Womit fangen wir an?",
  "Stress is exhausting. Take a deep breath and tackle one thing at a time. Where do we start?"]],
  [/hungrig|hunger|hungry/, ["Dann wird's Zeit für was Leckeres! Frag mich ruhig nach einem "
    + "Rezept, zum Beispiel: *Was ist Kaiserschmarrn?*", "Time for something tasty! Ask me about "
    + "a dish, for example: *What is pad thai?*"]],
  [/gluecklich|froh|gut\s+drauf|happy|great/, ["Das freut mich! Was hat dir den Tag schön gemacht?",
    "That's great to hear! What made your day?"]],
  [/krank|erkaeltet|sick|ill/, ["Gute Besserung! Ruh dich aus und trink genug. Wenn es nicht "
    + "besser wird, frag lieber einen Arzt.", "Get well soon! Rest and drink enough. If it doesn't "
    + "get better, please see a doctor."]],
];

function gespraech(text, sprache, zufall) {
  // Erst wie geschrieben, dann mit verbesserten Tippfehlern
  for (const kern of new Set([normalisieren(text), normalisieren(WORTSCHATZ.verbessern(text))])) {
    if (/^(?:(?:erzaehl|erzaehle|sag|kennst\s+du)\s+(?:mir\s+)?(?:mal\s+)?(?:einen|nen|'nen)?\s*witz|witz|noch\s+(?:einen|ein)\s+witz|(?:tell\s+me\s+)?a\s+joke|joke|another\s+one)\b/.test(kern)) {
      return { art: "witz", text: waehle(WITZE[sprache], `witz:${sprache}`, zufall) };
    }
    const m = /^(?:ich\s+bin|mir\s+ist|bin|i\s+am|i'm|im)\s+(?:so\s+|sehr\s+|total\s+|echt\s+|voll\s+|ziemlich\s+)?(.{2,30})$/.exec(kern);
    const treffer = m && BEFINDEN.find(([muster]) => muster.test(m[1]));
    if (treffer) return { art: "befinden", text: treffer[1][sprache === "en" ? 1 : 0] };
  }
  return null;
}

export function plauderei(text, { sprache = "de", frageOffen = false, zufall } = {}) {
  const art = artVon(text, { frageOffen });
  if (!art) return gespraech(text, sprache, zufall)?.text || "";
  const liste = sprache === "en" ? (EN[art.name] || art.antworten) : art.antworten;
  return waehle(liste, `${sprache}:${art.name}`, zufall);
}

// -- Hilfen -------------------------------------------------------------------
/** Kommt eines der Stichwoerter vor -- genau oder mit einem kleinen Tippfehler? */
export function enthaelt(liste, stichwoerter) {
  for (const wort of liste) {
    if (stichwoerter.includes(wort)) return wort;
  }
  for (const wort of liste) {
    if (KEIN_TIPPFEHLER.has(wort) || /\d/.test(wort)) continue;
    const grenze = erlaubteFehler(wort.length);
    if (!grenze) continue;
    for (const stich of stichwoerter) {
      if (stich.length < 5 || stich[0] !== wort[0]) continue;
      if (abstand(wort, stich, grenze) <= grenze) return stich;
    }
  }
  return "";
}

const zahl = (wert, sprache = "de", stellen = 2) => Number(wert).toLocaleString(
  sprache === "en" ? "en-GB" : "de-DE", { maximumFractionDigits: stellen });

const sp = (sprache, de, en) => (sprache === "en" ? en : de);

// -- Rechnen ------------------------------------------------------------------
const RECHEN_VORN = /^(?:was\s+(?:ist|ergibt|gibt|sind|macht)|wie\s*viel\s+(?:ist|sind|ergibt|macht|gibt)|rechne(?:\s+mal)?(?:\s+aus)?|berechne(?:\s+mir)?|ausrechnen|what(?:'s|\s+is)|calculate|compute|how\s+much\s+is)\s+/;

/** Ein Rechenausdruck aus normalem Text -- oder "" wenn es keiner ist. */
export function rechenAusdruck(text) {
  let t = falten(text).trim().replace(/[?!=]+\s*$/, "").trim();
  t = t.replace(RECHEN_VORN, "");
  // "15 % von 80": eigenes Zeichen, damit die Antwort es wieder so zeigen kann
  t = t.replace(/(\d+(?:[.,]\d+)?)\s*(?:%|prozent|percent)\s*(?:von|of)\s*(\d+(?:[.,]\d+)?)/g,
    "$1%$2");
  t = t.replace(/(?:quadrat)?wurzel\s+(?:aus|von)\s+(\d+(?:[.,]\d+)?)|square\s+root\s+of\s+(\d+(?:[.,]\d+)?)|sqrt\s*\(?\s*(\d+(?:[.,]\d+)?)\s*\)?|√\s*(\d+(?:[.,]\d+)?)/g,
    (_, a, b, c, d) => `sqrt(${a || b || c || d})`);
  t = t
    .replace(/\bgeteilt\s+durch\b|\bdurch\b|\bdivided\s+by\b|÷|\s:\s/g, "/")
    .replace(/\bmal\b|\btimes\b|\bmultipliziert\s+mit\b|×|\bx\b/g, "*")
    .replace(/\bplus\b|\bund\b/g, "+")
    .replace(/\bminus\b|\bweniger\b/g, "-")
    .replace(/\bhoch\b|\bto\s+the\s+power\s+of\b|\*\*/g, "^");
  // Dezimalkomma: "3,5" -> "3.5"; Tausenderpunkte ("1.000") nur ohne weitere Stellen
  t = t.replace(/(\d)\.(\d{3})(?!\d)/g, "$1$2").replace(/(\d),(\d)/g, "$1.$2");
  t = t.replace(/\s+/g, "");
  if (!/^[\d.+\-*/^()%sqrt]+$/.test(t) || !/\d/.test(t)) return "";
  if (!/[+\-*/^%]|sqrt/.test(t.replace(/^-/, ""))) return "";
  return t;
}

/** Rechnet einen Ausdruck aus + - * / ^ ( ) und sqrt() -- ohne eval. */
export function rechne(ausdruck) {
  let i = 0;
  const s = ausdruck;
  const fehler = () => { throw new Error("kein Ausdruck"); };
  function zahlLesen() {
    const m = /^\d+(?:\.\d+)?|^\.\d+/.exec(s.slice(i));
    if (!m) fehler();
    i += m[0].length;
    return Number(m[0]);
  }
  function faktor() {
    if (s[i] === "-") { i++; return -faktor(); }
    if (s[i] === "+") { i++; return faktor(); }
    if (s.startsWith("sqrt", i)) {
      i += 4;
      const w = faktor();
      if (w < 0) fehler();
      return Math.sqrt(w);
    }
    if (s[i] === "(") {
      i++;
      const w = summe();
      if (s[i] !== ")") fehler();
      i++;
      return w;
    }
    return zahlLesen();
  }
  function potenz() {
    const basis = faktor();
    if (s[i] === "^") { i++; return basis ** potenz(); }
    return basis;
  }
  function produkt() {
    let w = potenz();
    while (s[i] === "*" || s[i] === "/" || s[i] === "%") {
      const op = s[i++];
      const r = potenz();
      if (op === "/" && r === 0) throw new Error("durch null");
      w = op === "*" ? w * r : op === "/" ? w / r : (w / 100) * r;
    }
    return w;
  }
  function summe() {
    let w = produkt();
    while (s[i] === "+" || s[i] === "-") {
      const op = s[i++];
      const r = produkt();
      w = op === "+" ? w + r : w - r;
    }
    return w;
  }
  if (s.length > 200) fehler();
  const ergebnis = summe();
  if (i !== s.length || !Number.isFinite(ergebnis)) fehler();
  return ergebnis;
}

function rechenAntwort(text, sprache) {
  const ausdruck = rechenAusdruck(text);
  if (!ausdruck) return null;
  try {
    const ergebnis = zahl(rechne(ausdruck), sprache, 10);
    const schoen = ausdruck.replace(/\./g, sprache === "en" ? "." : ",")
      .replace(/\*/g, " × ").replace(/\//g, " : ").replace(/\+/g, " + ")
      .replace(/(?<=\d|\))-/g, " − ").replace(/\^/g, " ^ ")
      .replace(/%/g, sp(sprache, " % von ", " % of "));
    const satz = eine(sp(sprache, ["Das ergibt", "Das macht", "Ergebnis:", "Gerechnet:"],
      ["That's", "The result is", "That makes"]), `rechnen:${sprache}`);
    return { text: `${satz} **${ergebnis}**${satz.endsWith(":") ? "" : "."}\n\n`
      + `${schoen} = **${ergebnis}**`,
      schritt: { type: "calculate", expression: ausdruck } };
  } catch (err) {
    if (String(err.message) === "durch null") {
      return { text: sp(sprache, "Durch null kann man nicht teilen – das Ergebnis gibt es nicht.",
        "You can't divide by zero – there is no result.") };
    }
    return null;
  }
}

// -- Datum und Uhrzeit --------------------------------------------------------
function zeitAntwort(w, kern, sprache, { jetzt, zeitzone }) {
  const fragtZeit = /wie\s*spaet|wie\s*viel\s+uhr|wieviel\s+uhr|uhrzeit|what\s+time|current\s+time/
    .test(kern) || (enthaelt(w, ["uhrzeit"]) && w.length <= 6);
  const fragtDatum = /welche[rns]?\s+(?:tag|datum|wochentag)|welches\s+datum|den\s+wievielten|der\s+wievielte|datum\s+(?:ist\s+)?heute|heutige[sn]?\s+datum|what\s+(?:day|date)|today'?s\s+date|welches\s+jahr|what\s+year|kalenderwoche/.test(kern)
    || (enthaelt(w, ["datum", "wochentag"]) && w.length <= 6);
  if (!fragtZeit && !fragtDatum) return null;
  const zone = zeitzone || "Europe/Berlin";
  const loc = sprache === "en" ? "en-GB" : "de-DE";
  let uhr, tag;
  try {
    uhr = jetzt.toLocaleTimeString(loc, { timeZone: zone, hour: "2-digit", minute: "2-digit" });
    tag = jetzt.toLocaleDateString(loc, { timeZone: zone, weekday: "long", day: "numeric",
      month: "long", year: "numeric" });
  } catch {
    return null;
  }
  const ort = zone.split("/").pop().replace(/_/g, " ");
  if (fragtZeit && !fragtDatum) {
    return { text: sp(sprache, `Gerade ist es **${uhr} Uhr** (Zeitzone ${ort}).`,
      `It's **${uhr}** right now (time zone ${ort}).`) };
  }
  if (/kalenderwoche/.test(kern)) {
    return { text: sp(sprache, `Wir haben **Kalenderwoche ${kw(jetzt)}**. Heute ist ${tag}.`,
      `It's **week ${kw(jetzt)}**. Today is ${tag}.`) };
  }
  return { text: sp(sprache, `Heute ist **${tag}**. Gerade ist es ${uhr} Uhr (Zeitzone ${ort}).`,
    `Today is **${tag}**. It's ${uhr} right now (time zone ${ort}).`) };
}

/** Kalenderwoche nach ISO 8601. */
export function kw(datum) {
  const d = new Date(Date.UTC(datum.getUTCFullYear(), datum.getUTCMonth(), datum.getUTCDate()));
  const tag = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - tag);
  const jahresanfang = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d - jahresanfang) / 86400000 + 1) / 7);
}

// -- Wetter -------------------------------------------------------------------
const WOCHENTAGE = ["sonntag", "montag", "dienstag", "mittwoch", "donnerstag", "freitag",
  "samstag"];
const WOCHENTAGE_EN = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday",
  "saturday"];

const ORT_STOP = new Set([...FRAGEWOERTER, ...STICH.wetter, "wie", "wird", "ist", "es",
  "das", "draussen", "gerade", "jetzt", "aktuell", "aktuelle", "aktuelles", "am", "wochenende",
  "woche", "diese", "dieser", "naechste", "naechsten", "sonntag", "montag", "dienstag",
  "mittwoch", "donnerstag", "freitag", "samstag", "warm", "kalt", "grad", "like", "will",
  "be", "it", "weekend", "week", "this", "next", "now"]);

/** Der Ort in einer Wetterfrage -- aus dem Originaltext, damit Umlaute bleiben. */
export function ortAus(text) {
  const t = String(text || "").replace(/[?!.]+\s*$/, "");
  const m = /(?:^|\s)(?:in|für|fuer|bei|um|nahe|around|for|at)\s+([\p{L}][\p{L}\p{N} .'-]{1,60})$/iu
    .exec(t.replace(/\s+(?:heute|morgen|übermorgen|uebermorgen|today|tomorrow|am\s+\p{L}+|diese\s+woche|this\s+week|next\s+week|nächste\s+woche|naechste\s+woche|am\s+wochenende|jetzt|gerade|now)\b.*$/iu, ""));
  if (m) {
    const kandidat = m[1].trim().split(/\s+/)
      .filter((w) => !ORT_STOP.has(falten(w))).join(" ");
    if (kandidat) return kandidat;
  }
  // "Wetter Berlin", "Berlin Wetter morgen": was kein bekanntes Wort ist, ist der Ort
  const rest = t.split(/\s+/).filter((w) => {
    const f = falten(w).replace(/[^\p{L}\p{N}-]/gu, "");
    return f && !ORT_STOP.has(f) && !enthaelt([f], STICH.wetter);
  });
  return rest.length && rest.length <= 3 ? rest.join(" ") : "";
}

function welcheTage(kern, heute, anzahl) {
  if (/uebermorgen|day\s+after\s+tomorrow/.test(kern)) return [2];
  if (/morgen|tomorrow/.test(kern) && !/guten\s+morgen|good\s+morning|heute\s+morgen/.test(kern)) {
    return [1];
  }
  if (/wochenende|weekend/.test(kern)) {
    const bisSa = (6 - heute + 7) % 7, bisSo = (7 - heute) % 7;
    return [bisSa, bisSo].filter((t) => t < anzahl).sort((a, b) => a - b);
  }
  if (/woche|week|vorhersage|forecast|7\s*tage|naechsten\s+tage|next\s+days/.test(kern)) {
    return [...Array(anzahl).keys()];
  }
  for (const [nr, name] of [...WOCHENTAGE.entries(), ...WOCHENTAGE_EN.entries()]) {
    if (new RegExp(`\\b${name}\\b`).test(kern)) return [(nr - heute + 7) % 7];
  }
  return [];
}

async function wetterAntwort(text, w, kern, sprache, kontext) {
  if (!enthaelt(w, STICH.wetter) && !/wie\s+(?:warm|kalt)\s+(?:ist|wird)\s+es|how\s+(?:warm|cold)\s+is\s+it/.test(kern)) {
    return null;
  }
  let name = ortAus(text);
  let naeherung = false;
  if (!name && kontext.stadt) { name = kontext.stadt; naeherung = true; }
  if (!name) {
    return { text: sp(sprache, "Für welchen Ort? Schreib zum Beispiel: **Wetter in Hamburg**.",
      "For which place? For example, write: **weather in London**.") };
  }
  const schritt = { type: "search", query: sp(sprache, `Wetter ${name}`, `weather ${name}`) };
  const platz = await dienste.ort(name, sprache, kontext.holen);
  if (platz?.fehler) {
    return { schritt, text: sp(sprache, "Der Wetterdienst antwortet gerade nicht. Versuch es "
      + "gleich noch einmal.", "The weather service isn't answering. Try again in a moment.") };
  }
  if (!platz) {
    return { schritt, text: sp(sprache,
      `Einen Ort „${name}“ finde ich nicht. Prüf die Schreibweise oder nimm eine größere Stadt.`,
      `I can't find a place called “${name}”. Check the spelling or try a bigger city.`) };
  }
  const daten = await dienste.wetter(platz, kontext.holen);
  if (!daten) {
    return { schritt, text: sp(sprache, "Der Wetterdienst antwortet gerade nicht. Versuch es "
      + "gleich noch einmal.", "The weather service isn't answering. Try again in a moment.") };
  }
  const heute = new Date(`${daten.tage[0]?.datum || ""}T12:00:00Z`).getUTCDay();
  const tage = welcheTage(kern, Number.isNaN(heute) ? 0 : heute, daten.tage.length);
  const loc = sprache === "en" ? "en-GB" : "de-DE";
  const wo = naeherung
    ? sp(sprache, `in deiner Nähe (**${platz.name}** – geschätzt aus deiner Verbindung)`,
      `near you (**${platz.name}** – estimated from your connection)`)
    : sp(sprache, `in **${platz.name}**`, `in **${platz.name}**`);
  const grad = (wert, stellen = 0) => `${zahl(wert, sprache, stellen)} °C`;
  const zeilen = [];
  const j = daten.jetzt;
  if (!tage.length) {
    let satz = sp(sprache, `Gerade ist es ${wo} **${grad(j.temperatur, 1)}**, `
      + `${dienste.wetterlage(j.code, sprache)}`, `It's **${grad(j.temperatur, 1)}** ${wo} right `
      + `now, ${dienste.wetterlage(j.code, sprache)}`);
    if (typeof j.gefuehlt === "number" && Math.abs(j.gefuehlt - j.temperatur) >= 2) {
      satz += sp(sprache, ` – gefühlt eher ${grad(j.gefuehlt)}`, ` – feels more like ${grad(j.gefuehlt)}`);
    }
    if (j.wind >= 30) {
      satz += sp(sprache, `, dazu kräftiger Wind (${zahl(j.wind, sprache, 0)} km/h)`,
        `, with strong wind (${zahl(j.wind, sprache, 0)} km/h)`);
    }
    zeilen.push(`${satz}.`);
    tage.push(0);
  } else {
    zeilen.push(eine(sp(sprache, [`So wird das Wetter ${wo}:`, `Hier ist die Vorhersage ${wo}:`],
      [`Here's the forecast ${wo}:`, `This is what the weather looks like ${wo}:`]),
    `wetter:${sprache}`));
  }
  const gewaehlt = [];
  for (const nr of tage) {
    const t = daten.tage[nr];
    if (!t) continue;
    gewaehlt.push(t);
    const name = nr === 0 ? sp(sprache, "Heute", "Today") : nr === 1 ? sp(sprache, "Morgen", "Tomorrow")
      : new Date(`${t.datum}T12:00:00Z`).toLocaleDateString(loc, { weekday: "long", day: "numeric",
        month: "numeric", timeZone: "UTC" });
    const regen = typeof t.regen === "number"
      ? sp(sprache, `, Regenrisiko ${t.regen} %`, `, ${t.regen} % chance of rain`) : "";
    zeilen.push(`- **${name}**: ${dienste.wetterlage(t.code, sprache)}, `
      + sp(sprache, `${grad(t.min)} bis ${grad(t.max)}`, `${grad(t.min)} to ${grad(t.max)}`) + regen);
  }
  const tipp = wetterTipp(gewaehlt, sprache);
  if (tipp) zeilen.push("", tipp);
  zeilen.push("", sp(sprache, "Quelle: [Open-Meteo](https://open-meteo.com) (Daten u. a. vom DWD)",
    "Source: [Open-Meteo](https://open-meteo.com)"));
  return { schritt, text: zeilen.join("\n") };
}

/** Ein kurzer Rat, wie ihn ein Mensch dazu sagen wuerde. */
export function wetterTipp(tage, sprache) {
  if (!tage.length) return "";
  const hoechst = (feld) => Math.max(...tage.map((t) => (typeof t[feld] === "number" ? t[feld] : -99)));
  const tiefst = Math.min(...tage.map((t) => (typeof t.min === "number" ? t.min : 99)));
  if (tage.some((t) => t.code >= 95)) {
    return sp(sprache, "Achtung: Es kann Gewitter geben. Bleib dann lieber drinnen.",
      "Heads up: thunderstorms are possible. Better stay inside then.");
  }
  if (tage.some((t) => [71, 73, 75, 77, 85, 86].includes(t.code)) || tiefst <= 0) {
    return sp(sprache, "Es kann glatt werden – zieh dich warm an und sei vorsichtig unterwegs.",
      "It may get icy – dress warmly and take care out there.");
  }
  if (hoechst("regen") >= 60) {
    return sp(sprache, "Nimm lieber einen Schirm mit.", "Better take an umbrella.");
  }
  if (hoechst("max") >= 28) {
    return sp(sprache, "Es wird heiß – trink genug und denk an Sonnencreme.",
      "It's going to be hot – drink enough and use sunscreen.");
  }
  if (hoechst("regen") < 20 && tage.every((t) => t.code <= 2)) {
    return sp(sprache, "Gutes Wetter, um rauszugehen!", "Great weather to get outside!");
  }
  return "";
}

// -- Waehrungen ---------------------------------------------------------------
const WAEHRUNGEN = {
  euro: "EUR", euros: "EUR", eur: "EUR", "€": "EUR", dollar: "USD", dollars: "USD",
  usd: "USD", "$": "USD", pfund: "GBP", pound: "GBP", pounds: "GBP", gbp: "GBP", "£": "GBP",
  franken: "CHF", franc: "CHF", francs: "CHF", chf: "CHF", yen: "JPY", jpy: "JPY",
  yuan: "CNY", renminbi: "CNY", cny: "CNY", zloty: "PLN", pln: "PLN", lira: "TRY",
  try: "TRY", rupie: "INR", rupien: "INR", rupee: "INR", rupees: "INR", inr: "INR",
  won: "KRW", krw: "KRW", forint: "HUF", huf: "HUF", rand: "ZAR", zar: "ZAR", real: "BRL",
  brl: "BRL", peso: "MXN", mxn: "MXN", krone: "DKK", kronen: "DKK", dkk: "DKK", sek: "SEK",
  nok: "NOK", czk: "CZK", cad: "CAD", aud: "AUD", nzd: "NZD", sgd: "SGD", hkd: "HKD",
  ron: "RON", isk: "ISK", ils: "ILS", schekel: "ILS", thb: "THB", baht: "THB",
};
const WAEHRUNGSNAME = {
  EUR: ["Euro", "euros"], USD: ["US-Dollar", "US dollars"], GBP: ["Britische Pfund",
    "British pounds"], CHF: ["Schweizer Franken", "Swiss francs"], JPY: ["Yen", "yen"],
  CNY: ["Yuan", "yuan"], PLN: ["Złoty", "złoty"], TRY: ["Türkische Lira", "Turkish lira"],
  CAD: ["Kanadische Dollar", "Canadian dollars"], AUD: ["Australische Dollar",
    "Australian dollars"], SEK: ["Schwedische Kronen", "Swedish kronor"], NOK: ["Norwegische "
    + "Kronen", "Norwegian kroner"], DKK: ["Dänische Kronen", "Danish kroner"], CZK: [
    "Tschechische Kronen", "Czech korunas"], INR: ["Indische Rupien", "Indian rupees"],
};
const ZUSATZ = [
  [/kanadische[rn]?\s+dollar|canadian\s+dollars?/, "CAD"],
  [/australische[rn]?\s+dollar|australian\s+dollars?/, "AUD"],
  [/schwedische[rn]?\s+kronen?|swedish\s+krona/, "SEK"],
  [/norwegische[rn]?\s+kronen?|norwegian\s+krone/, "NOK"],
  [/tschechische[rn]?\s+kronen?|czech\s+koruna/, "CZK"],
  [/(?:hong\s*kong|hongkong)[\s-]?dollar/, "HKD"],
];

export function waehrungenIn(kern) {
  const gefunden = [];
  let rest = kern;
  for (const [muster, code] of ZUSATZ) {
    const m = muster.exec(rest);
    if (m) {
      gefunden.push({ code, stelle: m.index });
      rest = rest.slice(0, m.index) + " ".repeat(m[0].length) + rest.slice(m.index + m[0].length);
    }
  }
  const re = /[€$£]|[\p{L}]+/gu;
  let m;
  while ((m = re.exec(rest))) {
    let wort = m[0];
    let code = WAEHRUNGEN[wort];
    if (!code && wort.length >= 5 && !KEIN_TIPPFEHLER.has(wort)) {
      const nahe = Object.keys(WAEHRUNGEN).find((name) => name.length >= 5
        && name[0] === wort[0] && abstand(wort, name, 1) <= 1);
      code = nahe ? WAEHRUNGEN[nahe] : "";
    }
    if (code && !gefunden.some((g) => g.stelle === m.index)) gefunden.push({ code, stelle: m.index });
  }
  return gefunden.sort((a, b) => a.stelle - b.stelle).map((g) => g.code);
}

async function kursAntwort(w, kern, sprache, kontext) {
  // "try" ist auch ein englisches Wort: nur als Waehrung, wenn es gross geschrieben war
  const codes = waehrungenIn(kern).filter((c, i, alle) => alle.indexOf(c) === i
    && (c !== "TRY" || /\bTRY\b|lira/i.test(kontext.original)));
  const stich = enthaelt(w, STICH.kurse);
  if (codes.length < 2 && !(codes.length === 1 && stich)) return null;
  if (codes.length >= 2 && !stich && !/\d|\bin\b|\bnach\b|\bzu\b|\bto\b|\binto\b|\bwie\s*viel/.test(kern)) {
    return null;
  }
  let [von, nach] = codes;
  if (!nach) nach = von === "EUR" ? "USD" : "EUR";
  const betragText = /(\d+(?:[.,]\d+)?)/.exec(kern.replace(/(\d)\.(\d{3})(?!\d)/g, "$1$2"));
  const betrag = betragText ? Number(betragText[1].replace(",", ".")) : 1;
  if (!(betrag > 0 && betrag < 1e12)) return null;
  const schritt = { type: "search", query: `${von} → ${nach}` };
  const daten = await dienste.kurse(von, nach, kontext.holen);
  if (!daten) {
    return { schritt, text: sp(sprache,
      `Für ${von} → ${nach} habe ich gerade keinen Kurs. Die EZB führt rund 30 Währungen.`,
      `I don't have a rate for ${von} → ${nach} right now. The ECB lists about 30 currencies.`) };
  }
  const ergebnis = betrag * daten.kurs;
  const name = (code) => (WAEHRUNGSNAME[code] ? sp(sprache, WAEHRUNGSNAME[code][0],
    WAEHRUNGSNAME[code][1]) : code);
  return { schritt, text: sp(sprache,
    `Für **${zahl(betrag, sprache)} ${name(von)}** bekommst du gerade etwa `
      + `**${zahl(ergebnis, sprache)} ${name(nach)}**.`,
    `**${zahl(betrag, sprache)} ${name(von)}** is currently about `
      + `**${zahl(ergebnis, sprache)} ${name(nach)}**.`)
    + `\n\n${zahl(betrag, sprache)} ${von} = ${zahl(ergebnis, sprache)} ${nach}`
    + sp(sprache, ` · 1 ${von} = ${zahl(daten.kurs, sprache, 4)} ${nach} (Referenzkurs der EZB, `
      + `Stand ${daten.stand}). Deine Bank rechnet meist mit einem etwas anderen Kurs.`,
    ` · 1 ${von} = ${zahl(daten.kurs, sprache, 4)} ${nach} (ECB reference rate, as of `
      + `${daten.stand}). Your bank usually uses a slightly different rate.`) };
}

// -- Feiertage ----------------------------------------------------------------
const LAENDER = { oesterreich: "AT", austria: "AT", schweiz: "CH", switzerland: "CH",
  deutschland: "DE", germany: "DE", frankreich: "FR", france: "FR", italien: "IT", italy: "IT",
  spanien: "ES", spain: "ES", niederlande: "NL", netherlands: "NL", polen: "PL", poland: "PL",
  usa: "US", amerika: "US", england: "GB", grossbritannien: "GB", uk: "GB" };

async function feiertagAntwort(w, kern, sprache, kontext) {
  const stich = enthaelt(w, STICH.feiertage);
  if (!stich) return null;
  if (stich === "einheit" && !/tag\s+der\s+(?:deutschen\s+)?einheit/.test(kern)) return null;
  if ((stich === "buss" || stich === "bettag") && !/buss-?\s*und\s+bettag/.test(kern)) return null;
  const jahrText = /\b(19[9]\d|20\d\d|2100)\b/.exec(kern);
  const jetztJahr = kontext.jetzt.getUTCFullYear();
  const jahr = jahrText ? Number(jahrText[1]) : jetztJahr;
  let land = "DE";
  for (const [name, code] of Object.entries(LAENDER)) if (w.includes(name)) land = code;
  const schritt = { type: "search", query: sp(sprache, `Feiertage ${land} ${jahr}`,
    `holidays ${land} ${jahr}`) };
  let liste = await dienste.feiertage(jahr, land, kontext.holen);
  if (!liste) {
    return { schritt, text: sp(sprache, "Die Feiertage lassen sich gerade nicht laden. Versuch es "
      + "gleich noch einmal.", "The holidays can't be loaded right now. Try again in a moment.") };
  }
  const loc = sprache === "en" ? "en-GB" : "de-DE";
  const datum = (d) => new Date(`${d}T12:00:00Z`).toLocaleDateString(loc, { weekday: "long",
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  const zeile = (f) => `**${sprache === "en" ? f.name_en : f.name}**: ${datum(f.datum)}`
    + (f.bundesweit ? "" : sp(sprache, " (nur in einigen Bundesländern)", " (only in some regions)"));
  // "Ist heute/morgen ein Feiertag?" -- ja oder nein
  const tagFrage = /ist\s+(heute|morgen|uebermorgen)\s+(?:ein\s+)?feiertag|is\s+(today|tomorrow)\s+a\s+(?:public\s+)?holiday/
    .exec(kern);
  if (tagFrage) {
    const wort = tagFrage[1] || tagFrage[2];
    const plus = { heute: 0, today: 0, morgen: 1, tomorrow: 1, uebermorgen: 2 }[wort];
    const tag = new Date(kontext.jetzt.getTime() + plus * 86400000).toISOString().slice(0, 10);
    const treffer = liste.filter((f) => f.datum === tag);
    const wann = sp(sprache, { heute: "Heute", morgen: "Morgen", uebermorgen: "Übermorgen" }[wort]
      || "Heute", wort === "tomorrow" ? "Tomorrow" : "Today");
    const text = treffer.length
      ? sp(sprache, `Ja! ${wann} ist ${zeile(treffer[0])}.`, `Yes! ${wann} is ${zeile(treffer[0])}.`)
      : sp(sprache, `Nein, ${wann.toLowerCase()} ist kein gesetzlicher Feiertag (${land}).`,
        `No, ${wann.toLowerCase()} isn't a public holiday (${land}).`);
    return { schritt, text: text + QUELLE_NAGER(sprache) };
  }
  // Ein bestimmter Feiertag? ("wann ist ostern")
  if (!["feiertag", "feiertage", "feiertagen", "holiday", "holidays"].includes(stich)) {
    const gesucht = { ostern: ["ostersonntag", "ostermontag", "easter"], easter: ["easter"],
      weihnachten: ["weihnachtstag", "christmas"], christmas: ["christmas"],
      pfingsten: ["pfingstmontag", "whit"], einheit: ["einheit", "unity"],
      buss: ["buss"], bettag: ["buss"] }[stich] || [stich];
    const heuteIso = kontext.jetzt.toISOString().slice(0, 10);
    let treffer = liste.filter((f) => gesucht.some((g) => falten(f.name).includes(g)
      || falten(f.name_en).includes(g)) && (jahrText || f.datum >= heuteIso));
    if (!treffer.length && !jahrText) {
      // Schon vorbei? Dann das naechste Jahr.
      liste = await dienste.feiertage(jahr + 1, land, kontext.holen) || [];
      treffer = liste.filter((f) => gesucht.some((g) => falten(f.name).includes(g)
        || falten(f.name_en).includes(g)));
    }
    if (treffer.length) {
      const f = treffer[0];
      const kopf = sp(sprache, `**${f.name}** ist am **${datum(f.datum)}**.`,
        `**${f.name_en}** is on **${datum(f.datum)}**.`)
        + (f.bundesweit ? "" : sp(sprache, " Das ist aber nicht in allen Bundesländern ein Feiertag.",
          " It's not a public holiday in every region, though."));
      const rest = treffer.slice(1).map((x) => `- ${zeile(x)}`);
      return { schritt, text: kopf + (rest.length ? sp(sprache, "\n\nDazu gehört auch:\n",
        "\n\nRelated:\n") + rest.join("\n") : "") + QUELLE_NAGER(sprache) };
    }
  }
  const heute = kontext.jetzt.toISOString().slice(0, 10);
  if (/naechste|kommende|next|upcoming/.test(kern) || !jahrText) {
    const kommend = liste.filter((f) => f.datum >= heute).slice(0, 5);
    if (kommend.length) {
      const [erster, ...danach] = kommend;
      return { schritt, text: sp(sprache, `Der nächste Feiertag ist ${zeile(erster)}.`,
        `The next public holiday is ${zeile(erster)}.`)
        + (danach.length ? sp(sprache, "\n\nDanach kommen:\n", "\n\nAfter that:\n")
          + danach.map((f) => `- ${zeile(f)}`).join("\n") : "") + QUELLE_NAGER(sprache) };
    }
  }
  return { schritt, text: sp(sprache, `Das sind die Feiertage ${jahr} (${land}):`,
    `These are the public holidays ${jahr} (${land}):`)
    + "\n" + liste.map((f) => `- ${zeile(f)}`).join("\n") + QUELLE_NAGER(sprache) };
}

const QUELLE_NAGER = (sprache) => sp(sprache, "\n\nQuelle: [Nager.Date](https://date.nager.at)",
  "\n\nSource: [Nager.Date](https://date.nager.at)");

// -- Nachrichten --------------------------------------------------------------
async function nachrichtenAntwort(text, w, kern, sprache, kontext) {
  const stich = enthaelt(w, STICH.nachrichten);
  const frage = /was\s+gibt(?:\s+es|'?s)\s+neues|was\s+ist\s+(?:heute\s+)?passiert|was\s+ist\s+los\s+in\s+der\s+welt|what'?s\s+(?:new|happening)/
    .test(kern);
  if (!stich && !frage) return null;
  const thema = dienste.RESSORTS.find((r) => w.includes(r)) || "";
  const m = /^(.*?(?:nachrichten|news|neuigkeiten|meldungen|schlagzeilen)\s+(?:ueber|zu|zum|zur|von|aus|about|on|from)\s+)(.{2,80})$/
    .exec(kern);
  let suche = "";
  if (m && !dienste.RESSORTS.includes(m[2].trim())) {
    // Das Thema im Original (Gross-/Kleinschreibung, Umlaute), so viele Woerter wie vorne
    const vorn = m[1].trim().split(/\s+/).length;
    suche = String(text).replace(/[?!.]+\s*$/, "").trim().split(/\s+/).slice(vorn).join(" ")
      || m[2].trim();
  }
  const schritt = { type: "search", query: `Tagesschau ${suche || thema || ""}`.trim() };
  const meldungen = await dienste.nachrichten({ thema, suche, menge: 5 }, kontext.holen);
  if (!meldungen) {
    return { schritt, text: sp(sprache, "Die Tagesschau antwortet gerade nicht. Versuch es gleich "
      + "noch einmal.", "Tagesschau isn't answering right now. Try again in a moment.") };
  }
  if (!meldungen.length) {
    return { schritt, text: sp(sprache, `Zu „${suche || thema}“ finde ich gerade keine Meldungen.`,
      `I can't find any news about “${suche || thema}” right now.`) };
  }
  const kopf = suche
    ? eine(sp(sprache, [`Zu **${suche}** habe ich diese aktuellen Meldungen gefunden:`,
      `Das gibt es gerade Neues zu **${suche}**:`], [`Here's the latest news about **${suche}**:`,
      `I found these current reports about **${suche}**:`]), `news-suche:${sprache}`)
    : eine(sp(sprache, ["Hier sind die wichtigsten Meldungen von gerade eben:",
      "Das sind die aktuellen Schlagzeilen der Tagesschau:", "Das ist gerade los:"],
    ["Here are the latest headlines (from German public broadcaster Tagesschau):",
      "This is what's happening right now (news in German, from Tagesschau):"]),
    `news:${sprache}`);
  const schluss = eine(sp(sprache, ["Soll ich zu einem Thema mehr heraussuchen? Schreib zum "
    + "Beispiel: *Nachrichten über die Bahn*.", "Willst du Meldungen zu einem bestimmten Thema? "
    + "Frag einfach: *Nachrichten zu Sport*.", ""], ["Want news on a specific topic? Ask for "
    + "example: *news about the economy*.", ""]), `news-ende:${sprache}`);
  return { schritt, text: [kopf, "", ...meldungen.map((n, i) => `${i + 1}. **${n.titel}**`
    + (n.anriss ? ` — ${n.anriss}` : "") + (n.link ? ` [${sp(sprache, "mehr", "more")}](${n.link})` : "")),
  "", sp(sprache, "Quelle: [tagesschau.de](https://www.tagesschau.de)",
    "Source: [tagesschau.de](https://www.tagesschau.de)"), ...(schluss ? ["", schluss] : [])]
    .join("\n") };
}

// -- Wissen -------------------------------------------------------------------
const WISSEN_VORN = /^(?:(?:und\s+)?(?:was|wer|wo|wann|wie|welche[rs]?|warum|wieso|weshalb)\s+(?:ist|sind|war|waren|wurde|liegt|liegen|lebt|lebte|bedeutet|heisst|macht|hat|gibt\s+es)|was\s+weisst\s+du\s+(?:ueber|von)|erzaehl(?:e)?\s+(?:mir\s+)?(?:etwas\s+|was\s+)?(?:ueber|von)|erklaer(?:e)?(?:\s+mir)?|infos?\s+(?:zu|ueber)|wie\s+(?:hoch|gross|alt|lang|schwer|tief|weit|breit)\s+(?:ist|sind|war)|wie\s+funktionier(?:t|en)|wie\s+viele\s+einwohner\s+(?:hat|haben)|was\s+versteht\s+man\s+unter|definition(?:\s+von)?|what\s+(?:is|are|was|were)|who\s+(?:is|are|was|were)|where\s+is|tell\s+me\s+about|explain|how\s+does|how\s+do)\s+/;
const ARTIKEL = /^(?:der|die|das|ein|eine|einen|den|dem|des|the|a|an)\s+/i;

/** Das Thema einer Wissensfrage, im Original geschrieben ("Was ist der Eiffelturm?"). */
export function themaAus(text) {
  const original = String(text || "").trim().replace(/[?!.]+$/, "").trim();
  const gefaltet = falten(original);
  const m = WISSEN_VORN.exec(gefaltet);
  let thema = original;
  if (m) {
    // So viele Woerter vorne abschneiden, wie der Vorspann hatte
    const anzahl = m[0].trim().split(/\s+/).length;
    thema = original.split(/\s+/).slice(anzahl).join(" ");
  }
  thema = thema.replace(ARTIKEL, "").replace(/\s+(?:eigentlich|denn|genau|so)$/i, "").trim();
  return thema || original;
}

const DETAILFRAGE = /\b(?:wie\s+(?:hoch|gross|alt|lang|schwer|tief|weit|breit|viele?|schnell|teuer)|wann|wo|wieviele?|welche[rsn]?|how\s+(?:tall|high|big|old|long|many|much|far|fast)|when|where|which)\b/;

/** Wissen aus Wikipedia, so erzaehlt, dass die eigentliche Antwort vorne steht. */
async function wissenAntwort(text, sprache, kontext) {
  const thema = themaAus(text);
  if (!/[\p{L}\p{N}]/u.test(thema)) return null;
  const schritt = { type: "search", query: `Wikipedia: ${thema}` };
  const artikel = await dienste.wikipedia(thema, sprache, kontext.holen);
  if (!artikel) return { schritt, text: "" };
  const einleitung = saetze(artikel.text);
  let kern = "";
  if (DETAILFRAGE.test(falten(text))) {
    let bester = besterSatz(einleitung, text, artikel.titel);
    if (bester.punkte < 2.5) {
      // Steht es nicht in der Einleitung, im ganzen Artikel nachsehen
      const voll = await dienste.wikipediaVolltext(artikel.titel, sprache, kontext.holen);
      const zweiter = besterSatz(saetze(voll), text, artikel.titel);
      if (zweiter.punkte > bester.punkte) bester = zweiter;
    }
    if (bester.punkte >= 1.5) kern = bester.satz;
  }
  const rest = einleitung.filter((x) => x !== kern).slice(0, kern ? 2 : 3).join(" ");
  const teile = kern
    ? [kern, "", sp(sprache, `Etwas mehr dazu: ${rest}`, `A bit more context: ${rest}`)]
    : [eine(EINSTIEG[sprache], `einstieg:${sprache}`) + rest];
  teile.push("", sp(sprache, `Quelle: [Wikipedia: ${artikel.titel}](${artikel.link})`,
    `Source: [Wikipedia: ${artikel.titel}](${artikel.link})`));
  const schluss = eine(ABSCHLUSS[sprache], `abschluss:${sprache}`);
  if (schluss) teile.push("", schluss);
  return { schritt, text: teile.join("\n"), material: `${artikel.titel}: ${artikel.text}`,
    quelle: artikel.link };
}

/** Wenn Wikipedia nichts hat: Websuche (mit Schluessel) oder DuckDuckGo-Sofortantwort. */
async function webAntwort(text, sprache, kontext) {
  const treffer = await dienste.websuche(text, kontext.braveKey, sprache, kontext.holen);
  if (treffer.length) {
    const liste = treffer.slice(0, 3).map((t) => `- **[${t.titel}](${t.link})**`
      + (t.text ? ` — ${t.text}` : ""));
    return { schritt: { type: "search", query: text.slice(0, 120) },
      text: [sp(sprache, "Im Netz habe ich dazu Folgendes gefunden:",
        "Here's what I found on the web:"), "", ...liste, "",
      sp(sprache, "Quelle: Brave Search", "Source: Brave Search")].join("\n"),
      material: treffer.map((t) => `${t.titel} (${t.link}): ${t.text}`).join("\n") };
  }
  const sofort = await dienste.sofortAntwort(themaAus(text), sprache, kontext.holen);
  if (sofort) {
    return { schritt: { type: "search", query: `DuckDuckGo: ${themaAus(text)}` },
      text: sofort.text + (sofort.link ? `\n\n${sp(sprache, "Quelle", "Source")}: `
        + `[${sofort.quelle}](${sofort.link})` : ""), material: sofort.text };
  }
  return null;
}

// -- Webseiten ----------------------------------------------------------------
export function adresseIn(text) {
  const m = /\b(https?:\/\/[^\s<>"')\]]+|www\.[^\s<>"')\]]+)/i.exec(String(text || ""));
  if (!m) return "";
  const url = m[1].replace(/[.,;:!?]+$/, "");
  return /^www\./i.test(url) ? `https://${url}` : url;
}

/** Eine Seite lesen, die in der Frage steht, und sagen, worum es geht. */
export async function webseiteAntwort(text, kontext) {
  const sprache = kontext.sprache === "en" ? "en" : "de";
  const url = adresseIn(text);
  if (!url) return null;
  const schritt = { type: "fetch", url };
  const seite = await seiteAbrufen(url, kontext.holen || fetch);
  if (seite.fehler) {
    return { schritt, url, text: sp(sprache, `Die Seite konnte ich nicht lesen: ${seite.fehler}`,
      `I couldn't read that page: ${seite.fehler}`) };
  }
  const frage = text.replace(url, " ");
  const kern = kernSaetze(seite.text, frage, 4);
  const host = new URL(seite.url).hostname;
  const teile = [sp(sprache, seite.titel ? `Auf der Seite **${seite.titel}** geht es um Folgendes:`
    : "Das steht auf der Seite:", seite.titel ? `The page **${seite.titel}** is about this:`
    : "This is what the page says:")];
  if (seite.beschreibung) teile.push("", seite.beschreibung);
  if (kern.length) teile.push("", ...kern.map((x) => `- ${x}`));
  if (!seite.beschreibung && !kern.length) {
    teile.push("", sp(sprache, "Auf der Seite steht kaum lesbarer Text.",
      "There's hardly any readable text on the page."));
  }
  teile.push("", `${sp(sprache, "Quelle", "Source")}: [${host}](${seite.url})`);
  return { schritt, url, text: teile.join("\n"), material: [seite.titel, seite.beschreibung,
    seite.text].filter(Boolean).join("\n").slice(0, 8000), quelle: seite.url };
}

export function nichtsGefunden(sprache) {
  return sp(sprache,
    "Dazu finde ich gerade keine Antwort. Versuch es mit anderen Worten.\n\n"
      + "Ich helfe dir gern bei: Wissen (Wikipedia), Wetter, Nachrichten, Wechselkursen, "
      + "Feiertagen, Rechnen, Datum und Uhrzeit.",
    "I can't find an answer to that right now. Try other words.\n\n"
      + "I'm happy to help with: knowledge (Wikipedia), weather, news, exchange rates, "
      + "public holidays, maths, date and time.");
}

/**
 * Antwort aus festen Regeln und Live-Diensten -- ohne Wikipedia und ohne Modell.
 * `null` heisst: das ist eine Wissensfrage (oder etwas fuer ein Sprachmodell).
 */
export async function festeAntwort(text, kontext) {
  const sprache = kontext.sprache === "en" ? "en" : "de";
  const k = { holen: fetch, jetzt: new Date(), ...kontext, sprache, original: String(text || "") };
  const kurz = plauderei(text, { sprache, frageOffen: k.frageOffen, zufall: k.zufall });
  if (kurz) return { text: kurz, art: "plauderei" };
  const kern = normalisieren(WORTSCHATZ.verbessern(text));
  const w = woerter(kern);
  const rechnung = rechenAntwort(text, sprache);
  if (rechnung) return { ...rechnung, art: "rechnen" };
  const zeit = zeitAntwort(w, kern, sprache, k);
  if (zeit) return { ...zeit, art: "zeit" };
  for (const [art, schritt] of [
    ["wetter", () => wetterAntwort(text, w, kern, sprache, k)],
    ["kurse", () => kursAntwort(w, kern, sprache, k)],
    ["feiertage", () => feiertagAntwort(w, kern, sprache, k)],
    ["nachrichten", () => nachrichtenAntwort(text, w, kern, sprache, k)],
  ]) {
    const antwort = await schritt();
    if (antwort) return { ...antwort, art };
  }
  return null;
}

/** Jede Frage bekommt eine Antwort: feste Regeln, Dienste, Wikipedia, sonst ein ehrliches Nein. */
export async function beantworte(text, kontext = {}) {
  const sprache = kontext.sprache === "en" ? "en" : "de";
  const seite = await webseiteAntwort(text, kontext);
  if (seite) return { ...seite, art: "webseite" };
  const fest = await festeAntwort(text, kontext);
  if (fest) return fest;
  return wissenSuchen(text, sprache, kontext);
}

/** Wikipedia, dann das Netz -- sonst ein ehrliches "nichts gefunden". */
export async function wissenSuchen(text, sprache, kontext = {}) {
  const k = { holen: fetch, ...kontext };
  const wissen = await wissenAntwort(text, sprache, k);
  if (wissen?.text) return { ...wissen, art: "wissen" };
  const netz = await webAntwort(text, sprache, k);
  if (netz) return { ...netz, art: "web" };
  return { schritt: wissen?.schritt, text: nichtsGefunden(sprache), art: "nichts" };
}
