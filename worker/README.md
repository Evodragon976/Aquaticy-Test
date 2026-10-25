# Aquaticy bei Cloudflare

Diese Fassung läuft als **Cloudflare Worker**: ohne eigenen Server, ohne Datenbank, ohne
Konten. Sie nutzt dieselbe Oberfläche wie die App (`aquaticy/webui.html`).

## Online stellen – ohne Setup

**Weg 1: Knopf.** [![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/Evodragon976/Aquaticy-Test)

**Weg 2: Repo verbinden.** Im Cloudflare-Dashboard *Workers & Pages → Create → Import a
repository* wählen und dieses Repo nehmen. Alles andere bleibt, wie es ist. Bei jedem Push
stellt Cloudflare die neue Fassung von selbst online.

**Weg 3: Kommandozeile.** Im Hauptordner des Repos:

```bash
npx wrangler deploy
```

Du brauchst dafür kein Python, kein `npm install` und kein `aquaticy setup`. Die
Einstellungen stehen in `wrangler.toml` im Hauptordner. Alles, was der Worker braucht, liegt
fertig im Repo.

## Was er kann

- **Feste Antworten** auf Hallo, Danke, Wie geht's … – auch mit Tippfehlern („hallp“,
  „wiegehts“, „dnake“).
- **Rechnen**, **Datum und Uhrzeit** (in deiner Zeitzone).
- **Wetter** (Open-Meteo), **Nachrichten** (Tagesschau, direkt in der Antwort),
  **Wechselkurse** (EZB), **Feiertage** (Nager.Date).
- **Wissen** aus Wikipedia: Die eigentliche Antwort steht vorne, bei Detailfragen
  („Wie hoch ist …?“) sucht er im ganzen Artikel nach dem passenden Satz.
- **Webseiten lesen**: eine `https://`-Adresse in die Frage schreiben. Dabei gelten dieselben
  Regeln wie in der App: nur öffentliche Adressen, `robots.txt` zählt, keine Anmeldung oder
  Bezahlschranke umgehen.
- **Prozente und Mehrwertsteuer** („200 plus 19 %“, „119 € brutto in netto“), **Einheiten**
  (Länge, Gewicht, Temperatur, Volumen, Fläche, Tempo, Zeit, Daten) und Rechnen mit
  `sin`, `cos`, `log`, `π` und Fakultät.
- **Daten**: Tage bis Weihnachten, Ostern oder einem Datum, Wochentag eines Datums,
  Tage seit einem Datum.
- **Weltzeit** („Wie spät ist es in Tokio?“) und **Sonnenauf- und -untergang**.
- **Übersetzen** kurzer Texte (MyMemory, maschinell).
- **Zum Spaß**: Würfel, Münze, Zufallszahl, „Soll ich A oder B?“, Witze, Fun Facts,
  Mutmacher und Ideen fürs Essen.
- **Folgefragen**: erst „Wer ist Olaf Scholz?“, dann „Wie alt ist er?“; nach einer
  Wetterfrage reicht „und morgen?“ oder „und in Berlin?“.
- Passt kein Wikipedia-Artikel zum Thema, sucht er in der anderen Sprache. Sonst sagt er
  ehrlich, was am nächsten kommt.
- Jede Frage bekommt eine Antwort. Findet er nichts, sagt er das ehrlich.

## Freiwillig: Schlüssel

Ohne Schlüssel antwortet Aquaticy ohne Sprachmodell. Mit Schlüssel klingt er freier und
beantwortet auch alles andere. Schlüssel kommen nie in eine Datei, sondern als Secret:

```bash
npx wrangler secret put MISTRAL_API_KEY      # Sprachmodell von Mistral (EU)
npx wrangler secret put NVIDIA_NIM_API_KEY   # oder NVIDIA (USA)
npx wrangler secret put BRAVE_API_KEY        # Websuche über Brave Search
```

Im Dashboard geht das unter *Settings → Variables and Secrets*. Mit Sprachmodell prüft
Aquaticy jede Frage zuerst gegen den Rechtsrahmen der App (Grundgesetz und BGB). Antwortet
die Prüfung nicht, schreibt das Modell nichts – dann antwortet Aquaticy ohne Modell.

## Was hier fehlt

Konten, Gedächtnis, Coworker, virtual machine, Heimnetz und Add-ons brauchen Speicher oder
einen eigenen Rechner. Dafür gibt es die App (`aquaticy web`). Der Chat lebt nur in der
geöffneten Seite. Die Einstellungen der Oberfläche liegen in einem Cookie in deinem Browser.

## Sicherheit und Grenzen

- **Webseiten** liest der Worker mit den Regeln der App (`netguard.py`): nur öffentliche
  Ziele, jeder Name wird per DNS-over-HTTPS geprüft, auch vor jeder Weiterleitung;
  höchstens 1,5 MB.
- **Oberfläche** mit derselben Content-Security-Policy (Nonce) wie die App. Schlüssel gehen
  nie an den Browser. Höchstens 20 Fragen je Minute und Verbindung, Anfragen höchstens 64 KB.
- Der Verlauf kommt aus dem Browser. Wer ihn fälscht, ändert nur den eigenen Zusammenhang;
  der Prüfer sieht ihn mit.
- Eine Seite aus der Frage wird vor der Rechtsprüfung gelesen. Das Modell schreibt aber erst
  nach einem klaren „zulässig“.
- Die Tagesschau erlaubt 60 Abrufe je Stunde. Der Worker hält Antworten dafür fünf Minuten im
  Zwischenspeicher von Cloudflare; einen gemeinsamen Zähler gibt es ohne Speicher nicht.

## Für Entwickler

- `worker/src/` – der Worker. `index.js` ist der Einstieg, `server.js` die Weiche,
  `antworten.js` das Antwortsystem, `sprache.js` die Tippfehler, `stil.js` die
  Formulierungen, `dienste.js` die Datenquellen, `abruf.js` das Lesen von Webseiten,
  `mehr.js` Prozente, Einheiten, Daten, Weltzeit, Sonne, Zufall und Übersetzen,
  `ki.js` die Sprachmodelle.
- `worker/src/erzeugt.js` kommt aus dem Python-Paket (feste Antworten, Rechtsrahmen,
  Texte). Nach Änderungen dort: `python tools/worker_bauen.py`.
- Tests: `cd worker && npm test` (ohne Netz). `python tools/pruefung.py` prüft beides mit.
- Lokal ausprobieren: `npx wrangler dev` im Hauptordner.
