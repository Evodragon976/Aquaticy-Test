// Text glaetten und Tippfehler verzeihen -- ohne Modell, ohne Woerterbuch-Download.
//
// Die Idee: Aquaticy kennt die Woerter, auf die es reagiert (aus den festen Antworten
// und den Stichwoertern der Dienste). Ein unbekanntes Wort, das einem bekannten sehr
// aehnlich ist ("hallp", "wetetr", "nachrichen"), wird als dieses gelesen. Namen und
// Themen bleiben, wie sie sind: verglichen wird nur mit dem eigenen Wortschatz, und
// nur bei kleinem Abstand.

const UMLAUTE = { "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss" };

/** Kleinschreibung, Umlaute als ae/oe/ue, langgezogene Buchstaben gekuerzt. */
export function falten(text) {
  return String(text || "")
    .toLowerCase()
    .normalize("NFC")
    .replace(/[’`´]/g, "'")
    // "hallooo", "heyyy", "danke schööön": drei und mehr gleiche Buchstaben -> einer
    .replace(/(\p{L})\1{2,}/gu, "$1")
    .replace(/[äöüß]/g, (z) => UMLAUTE[z]);
}

/** Die Woerter eines Textes (Buchstaben und Ziffern). */
export function woerter(text) {
  return falten(text).match(/[\p{L}\p{N}']+/gu) || [];
}

/** Abstand nach Damerau-Levenshtein: Vertauschen zaehlt als ein Fehler ("hlalo"). */
export function abstand(a, b, grenze = 3) {
  if (a === b) return 0;
  if (Math.abs(a.length - b.length) > grenze) return grenze + 1;
  const zeilen = [];
  for (let i = 0; i <= a.length; i++) {
    zeilen.push(new Array(b.length + 1).fill(0));
    zeilen[i][0] = i;
  }
  for (let j = 0; j <= b.length; j++) zeilen[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    let kleinste = Infinity;
    for (let j = 1; j <= b.length; j++) {
      const kosten = a[i - 1] === b[j - 1] ? 0 : 1;
      let wert = Math.min(zeilen[i - 1][j] + 1, zeilen[i][j - 1] + 1,
        zeilen[i - 1][j - 1] + kosten);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        wert = Math.min(wert, zeilen[i - 2][j - 2] + 1);
      }
      zeilen[i][j] = wert;
      kleinste = Math.min(kleinste, wert);
    }
    if (kleinste > grenze) return grenze + 1;
  }
  return zeilen[a.length][b.length];
}

/** Wie viele Fehler ein Wort dieser Laenge haben darf. Kurze Woerter: keiner. */
export function erlaubteFehler(laenge) {
  if (laenge <= 3) return 0;
  if (laenge <= 7) return 1;
  return 2;
}

export class Wortschatz {
  constructor(liste = []) {
    this.woerter = new Set();
    for (const wort of liste) this.dazu(wort);
  }

  dazu(wort) {
    const w = falten(wort).trim();
    if (w && /^[\p{L}\p{N}']+$/u.test(w)) this.woerter.add(w);
  }

  /** Die bekannten Woerter, die *wort* gemeint haben duerfte (alle gleich nah) -- oder [wort]. */
  kandidaten(wort) {
    if (this.woerter.has(wort) || /\d/.test(wort)) return [wort];
    const grenze = erlaubteFehler(wort.length);
    if (!grenze) return [wort];
    let beste = [], bester = grenze + 1;
    for (const kandidat of this.woerter) {
      if (Math.abs(kandidat.length - wort.length) > grenze) continue;
      // Der erste Buchstabe stimmt fast immer -- das haelt Fehltreffer klein.
      if (kandidat[0] !== wort[0] && grenze < 2) continue;
      const d = abstand(wort, kandidat, grenze);
      if (d > grenze) continue;
      if (d < bester) {
        beste = [kandidat]; bester = d;
      } else if (d === bester) {
        beste.push(kandidat);
      }
    }
    return beste.length ? beste.sort() : [wort];
  }

  /** Das bekannte Wort, das *wort* gemeint haben duerfte. Bei Gleichstand: nicht raten. */
  bestes(wort) {
    const liste = this.kandidaten(wort);
    return liste.length === 1 ? liste[0] : wort;
  }

  /** Zusammengeschriebenes trennen: "wiegehts" -> "wie gehts". */
  trennen(wort) {
    if (wort.length < 6 || this.woerter.has(wort)) return null;
    for (let i = 2; i <= wort.length - 2; i++) {
      const links = wort.slice(0, i), rechts = wort.slice(i);
      if (this.woerter.has(links) && this.woerter.has(rechts)) return `${links} ${rechts}`;
    }
    return null;
  }

  /** Der ganze Text mit verbesserten Woertern, gefaltet und mit einfachen Leerzeichen. */
  verbessern(text) {
    return woerter(text)
      .map((w) => this.trennen(w) || this.bestes(w))
      .join(" ");
  }

  /** Alle Lesarten bei Gleichstand ("gehst" -> "gehts" oder "geht"), hoechstens *max*. */
  varianten(text, max = 8) {
    let ergebnis = [""];
    for (const w of woerter(text)) {
      const getrennt = this.trennen(w);
      const liste = getrennt ? [getrennt] : this.kandidaten(w);
      const neu = [];
      for (const vorn of ergebnis) {
        for (const k of liste) {
          if (neu.length < max) neu.push(vorn ? `${vorn} ${k}` : k);
        }
      }
      ergebnis = neu;
    }
    return ergebnis.filter(Boolean);
  }
}

/** Ein Muster aus Python fuer JavaScript: nur die Umlaute falten, Escapes bleiben. */
export function musterFalten(quelle) {
  return String(quelle).replace(/[äöüßÄÖÜ]/g, (z) => UMLAUTE[z.toLowerCase()]);
}

/** Woerter aus einem regulaeren Ausdruck holen: die festen Buchstabenfolgen darin. */
export function woerterAusMuster(quelle) {
  return musterFalten(quelle)
    .toLowerCase()
    // Escapes wie \s, \b, \d sind keine Woerter
    .replace(/\\[a-z]/g, " ")
    .match(/[a-z]{2,}/g) || [];
}
