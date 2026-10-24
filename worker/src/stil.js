// Antworten, die wie ein Gespraech klingen -- ohne Sprachmodell.
//
// Zwei Dinge machen den Unterschied: Erstens steht die eigentliche Antwort vorne (der
// Satz aus einer Quelle, der am besten zur Frage passt), zweitens wechseln Einstieg und
// Abschluss, damit nicht jede Antwort gleich klingt.

import { falten } from "./sprache.js";

const zuletzt = new Map();

/** Eine zufaellige Formulierung -- nicht zweimal hintereinander dieselbe. */
export function eine(liste, schluessel, zufall = Math.random) {
  const vorher = zuletzt.get(schluessel);
  const auswahl = liste.length > 1 ? liste.filter((t) => t !== vorher) : liste;
  const wahl = auswahl[Math.floor(zufall() * auswahl.length)] ?? liste[0];
  zuletzt.set(schluessel, wahl);
  return wahl;
}

export const sp = (sprache, de, en) => (sprache === "en" ? en : de);

export const ABSCHLUSS = {
  de: ["Willst du mehr dazu wissen? Frag einfach weiter.",
    "Wenn du magst, schlage ich noch mehr dazu nach.",
    "Frag gern nach, wenn etwas unklar ist.",
    "Soll ich noch etwas Bestimmtes dazu heraussuchen?", ""],
  en: ["Want to know more? Just keep asking.", "If you like, I can look up more about it.",
    "Feel free to ask if anything is unclear.", ""],
};

export const EINSTIEG = {
  de: ["", "", "Gute Frage! ", "Klar, gern: ", "Kurz erklärt: "],
  en: ["", "", "Good question! ", "Sure: ", "In short: "],
};

// -- Saetze finden und gewichten ----------------------------------------------
const ABKUERZUNGEN = /\b(?:z|u|d|o|s|v|bzw|ca|etc|evtl|ggf|inkl|max|min|Nr|St|Dr|Prof|Mio|Mrd|bzw|vgl|usw|Jh|Jhd|Chr|n|engl|frz|lat|griech|geb|gest|Mr|Mrs|Ms|vs|e\.g|i\.e)\.\s*$/i;

/** Text in Saetze teilen -- ohne an "z. B.", "u. a." oder "1." zu zerbrechen. */
export function saetze(text) {
  const teile = String(text || "").replace(/\s+/g, " ").trim().split(/(?<=[.!?])\s+(?=[A-ZÄÖÜ„"(0-9])/);
  const ergebnis = [];
  for (const teil of teile) {
    const vorher = ergebnis.at(-1);
    if (vorher && (ABKUERZUNGEN.test(vorher) || /\b\d{1,2}\.$/.test(vorher) || vorher.length < 20)) {
      ergebnis[ergebnis.length - 1] = `${vorher} ${teil}`;
    } else {
      ergebnis.push(teil);
    }
  }
  return ergebnis.filter((s) => s.length > 1);
}

const FUELLWOERTER = new Set(("der die das ein eine einer eines einem einen und oder aber ist sind "
  + "war waren wird werden wurde wurden hat haben hatte von vom zu zum zur im in an am auf aus "
  + "bei mit nach fuer ueber unter um als wie was wer wo wann warum welche welcher welches es "
  + "sich nicht auch noch nur so sehr mehr man den dem des dass ich du mir mich dir dich sie er "
  + "wir ihr the a an and or of to in on at for is are was were be by with as it this that "
  + "what who where when why how which do does did can mir bitte mal eigentlich denn erklaer "
  + "erklaere erzaehl sag viel viele").split(" "));

// Woerter, die in Frage und Quelle oft verschieden heissen ("gebaut" -> "errichtet").
const VERWANDT = [
  ["gebaut", "errichtet", "erbaut", "baute", "konstruiert", "built", "constructed"],
  ["erfunden", "erfand", "entwickelt", "entwickelte", "invented", "developed"],
  ["gegruendet", "gruendete", "gruendung", "founded"],
  ["geboren", "geburt", "born"],
  ["gestorben", "starb", "tod", "died", "death"],
  ["hoch", "hoehe", "height", "tall", "high"],
  ["alt", "alter", "age", "old"],
  ["gross", "groesse", "flaeche", "size", "area", "big"],
  ["lang", "laenge", "length", "long"],
  ["einwohner", "bevoelkerung", "population", "inhabitants"],
  ["schwer", "gewicht", "masse", "weight"],
  ["tief", "tiefe", "depth", "deep"],
  ["entfernt", "entfernung", "distance", "far"],
];

export function inhaltsWoerter(text) {
  return (falten(text).match(/[\p{L}\p{N}]+/gu) || [])
    .filter((w) => w.length > 2 && !FUELLWOERTER.has(w));
}

const MENGENFRAGE = /\b(?:wie\s+(?:hoch|gross|groß|alt|lang|schwer|tief|weit|breit|viele?|schnell|teuer)|wann|welches\s+jahr|how\s+(?:tall|high|big|old|long|many|much|far|fast)|when)\b/i;
const ORTSFRAGE = /\b(?:wo|where)\b/i;

/** Der Satz, der eine Frage am besten beantwortet -- mit seiner Punktzahl. */
export function besterSatz(liste, frage, thema = "") {
  const fragWoerter = inhaltsWoerter(frage);
  const themaWoerter = new Set(inhaltsWoerter(thema));
  const nachMenge = MENGENFRAGE.test(falten(frage)) || MENGENFRAGE.test(frage);
  const nachOrt = ORTSFRAGE.test(frage);
  const nachPerson = /\b(?:wer|who)\b/i.test(frage);
  let beste = { satz: "", punkte: 0, stelle: -1 };
  liste.forEach((satz, stelle) => {
    const w = inhaltsWoerter(satz);
    let punkte = 0;
    for (const f of fragWoerter) {
      if (themaWoerter.has(f)) continue;     // das Thema steht ohnehin fast ueberall
      const gruppe = VERWANDT.find((g) => g.includes(f)) || [f];
      const staemme = gruppe.map((x) => (x.length <= 4 ? x : x.slice(0, Math.max(4, x.length - 2))));
      if (w.some((x) => staemme.some((st) => (st.length <= 4 ? x === st : x.startsWith(st))))) {
        punkte += 2;
      }
    }
    if (nachPerson && /\b(?:von|durch|by)\s+\p{Lu}\p{L}+\s+\p{Lu}/u.test(satz)) punkte += 1;
    if (nachMenge && /\d/.test(satz)) punkte += 1.5;
    if (nachMenge && /\b(?:meter|metern|m|km|kilometer|jahre?n?|einwohner|prozent|tonnen|kg|grad|euro|dollar|feet|ft|years?|inhabitants|people)\b/i.test(satz)) punkte += 1;
    if (nachOrt && /\b(?:in|im|liegt|located|lies)\b/i.test(satz)) punkte += 0.5;
    punkte -= stelle * 0.01;                  // bei Gleichstand der fruehere Satz
    if (satz.length > 400) punkte -= 1;
    if (punkte > beste.punkte) beste = { satz, punkte, stelle };
  });
  return beste;
}

/** Die wichtigsten *n* Saetze eines Textes in ihrer Reihenfolge (fuer Webseiten). */
export function kernSaetze(text, frage = "", n = 3) {
  const liste = saetze(text).filter((s) => s.length >= 40 && s.length <= 500);
  if (liste.length <= n) return liste;
  const haeufig = new Map();
  for (const s of liste) {
    for (const w of new Set(inhaltsWoerter(s))) haeufig.set(w, (haeufig.get(w) || 0) + 1);
  }
  const fragWoerter = new Set(inhaltsWoerter(frage));
  const bewertet = liste.map((s, i) => {
    const w = inhaltsWoerter(s);
    const dichte = w.reduce((n2, x) => n2 + Math.min(haeufig.get(x) || 0, 5), 0) / (w.length + 3);
    const frage2 = w.filter((x) => fragWoerter.has(x)).length * 2;
    return { s, i, punkte: dichte + frage2 + (i < 3 ? 1.5 - i * 0.5 : 0) };
  });
  return bewertet.sort((a, b) => b.punkte - a.punkte).slice(0, n).sort((a, b) => a.i - b.i)
    .map((x) => x.s);
}
