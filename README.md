# Aquaticy AI 16.1.3

**Aquaticy** recherchiert für dich. Du fragst, Aquaticy sucht im Web, liest die passenden
Seiten und fasst zusammen. Zu jeder Angabe steht die Quelle. Es läuft im Terminal, im Browser,
auf dem Handy und auf Vercel.

```
$ aquaticy

> Finde mir gute Cafés in Mönchengladbach mit WLAN

  [Suche] cafés mönchengladbach
  [Suche] café mönchengladbach wlan arbeiten
  [Lese]  4 Seiten...

  Ich habe 6 Cafés gefunden, die passen:

  1. Café Nordwand — Hindenburgstr. 12
     WLAN steht auf der Website, Steckdosen an den Fensterplätzen.
     Quelle: die Seite des Cafés
  ...

> davon nur die, die sonntags offen haben
```

> **Cloudflare-Fassung:** Dieses Repo läuft auch als Cloudflare Worker – ohne Server,
> ohne Datenbank und ohne Setup. Repo im Cloudflare-Dashboard verbinden oder
> `npx wrangler deploy` ausführen, fertig. Mehr in [`worker/README.md`](worker/README.md).
>
> [![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/Evodragon976/Aquaticy-Test)
>
> **Vercel-Fassung:** Auf Vercel läuft hier die ganze Oberfläche, siehe [Vercel](#vercel).

---

## Neu in 16.1.3

Nur in Aquaticy-Test, für Vercel.

- **Speicher-Verbund:** Sind Postgres-Datenbanken mit dem Projekt verbunden (Neon, Supabase),
  arbeiten sie zusammen und teilen sich die Aufgaben: Die erste hält die Konten, die dritte
  ist der Cache, alle anderen halten die Profile der Konten. Jeder Teil liegt zusätzlich als
  Spiegel auf einer zweiten Datenbank.
- **Nur Geändertes wird gespeichert.** Bisher ging nach jeder Änderung der ganze Datenordner
  als ein Paket in den Blob-Speicher. Jetzt geht nur der Teil hoch, der sich geändert hat.
- **Weniger Arbeitsspeicher je Instanz:** Ein Profil wird erst geladen, wenn sein Konto eine
  Anfrage stellt.
- **Mehrere Instanzen:** Vor jeder Anfrage holt eine Instanz, was eine andere geändert hat.
- **Gemeinsamer Cache:** Bilder der Vorschau und die Abrufe von Aquaticy Standard (Wetter,
  Orte, Wikipedia, Kurse, Nachrichten) liegen eine Zeit lang im Cache. Die nächste Antwort
  kommt dann schneller.
- **Übernahme:** Beim ersten Start holt Aquaticy den Stand einmal aus dem Blob-Speicher und
  verteilt ihn auf die Datenbanken. Alles bleibt verschlüsselt.

Einrichtung und Grenzen stehen unter [Vercel](#vercel).

## Neu in 16.0.3

Fehler behoben und Aquaticy Standard ausgebaut, nur in Aquaticy-Test.

- **Wetter versteht mehr:** „Wie wird das Wochenende?“ geht jetzt auch ohne das Wort „Wetter“.
  Mehrere Orte auf einmal gehen auch: „Wetter in Erkelenz und in Köln“. „Bei mir“ und „hier“
  meinen deinen Wohnort.
- **Orte richtig geschrieben:** „Frankfurt am Main“ und „München“ gehen so an den Wetterdienst,
  wie du sie schreibst. Antwortet der Dienst nicht, sagt Aquaticy das – und nicht mehr „Ort
  nicht gefunden“.
- **Rückfrage nach dem Ort:** „Keine Ahnung“ oder „egal“ gilt nicht mehr als Ortsname.
- **Wenn es dir nicht gut geht:** „Mir geht es nicht gut“ und ähnliche Sätze bekommen Zuspruch
  und die Nummer der Telefonseelsorge.
- **Neu:** Wurzeln, „Ist morgen ein Feiertag?“, Muttertag, Advent, Halloween und
  Zeitumstellung, Primzahlen, Schaltjahre, römische Zahlen, Binär und Hex, Durchschnitt,
  Sternzeichen, Buchstaben zählen, rückwärts schreiben, buchstabieren, „Pizza oder Pasta?“,
  Ideen zum Kochen, Zitate, Rätsel und Zungenbrecher.
- **Aufgeräumt:** Die README, der Datenschutztext und die Oberfläche nennen keine entfernten
  Teile mehr. Die Links zum Installieren und die Updateprüfung zeigen jetzt auf Aquaticy-Test.

## Neu in 16.0.2

Aquaticy Standard ist schlauer geworden, nur in Aquaticy-Test.

- **Kleines Gedächtnis im Gespräch:** Fragt Aquaticy Standard „Für welchen Ort?“, reicht als
  Antwort einfach „Erkelenz“. Danach weiß es den Ort auch bei „und morgen?“ oder
  „was soll ich anziehen?“.
- **Antwortet wie ein Mensch:** ganze Sätze, ein Tipp und eine Idee, was du als Nächstes fragen
  kannst.
- **Neue Fragen:** Was soll ich anziehen? Brauche ich einen Schirm? Wird es sonnig? Wetter am
  Wochenende und für die nächsten Tage, Uhrzeit in anderen Städten, Feiertage, Mondphase,
  Alter, BMI, Trinkgeld, sichere Passwörter, Witze, Fakten und ein offenes Ohr, wenn es dir
  nicht gut geht.
- **Freundlichere Texte:** zum Beispiel bei „Bevor es losgeht“, bei der Anmeldung und bei Fehlern.
- **Entfernt:** öffentliche Webcams und Satellitenbilder, die Einstellungen unter
  „Helfer & Grenzen“ und das Gemeinsame Lernen samt 48-Stunden-Recherchecache. Was dort
  gespeichert war, löscht Aquaticy beim nächsten Start.

## Neu in 16.0.1

Aufgeräumt und Fehler behoben, nur in Aquaticy-Test.

- **Anmelden mit Nutzername:** Im Kontensystem geht die Anmeldung jetzt auch mit dem
  Nutzernamen, nicht nur mit der E-Mail-Adresse. So kommen auch Konten aus der Zeit des
  Einzelkontos wieder rein. Fehlversuche zählen für Name und E-Mail gemeinsam.
- **Secure Pro auf Vercel:** Der Chat war im Kontensystem gesperrt. Jetzt kann ihn jedes Konto
  nutzen.
- **Befehle im Chat:** Die Vorschläge für `/wetter`, `/github`, `/code-review` … fehlten auf
  Vercel. Sie sind wieder da.
- **Kleiner:** Alles, was es seit 16.0.0 nicht mehr gibt, ist auch aus dem Code raus:
  virtual machine, Messenger, Server-Verbund, Auto-Upgrading, Coworker, Heimnetz, Home Assistant,
  Lager, eigene Domain und das Docker-Abbild. Das sind über 30 Module weniger.
- **GitHub** liest nur noch. Ändern brauchte die virtual machine.

## Neu in 16.0.0

Diese Fassung gibt es nur in Aquaticy-Test. Sie ist für Vercel gebaut.

- **Aquaticy Standard:** Das neue voreingestellte Modell antwortet ohne Sprachmodell und ohne
  Schlüssel. Es rechnet, rechnet um (Prozente, Mehrwertsteuer, Einheiten) und kennt Datum und
  Uhrzeit. Es holt Wetter, Wechselkurse, Nachrichten und Wissen aus Wikipedia, jeweils mit Quelle.
  Was du ihm sagst („ich wohne in Bremen“), merkt es sich und nutzt es, zum Beispiel beim Wetter.
- **Hinweis auf API-Schlüssel:** Wer nur Aquaticy Standard hat, sieht beim ersten Anmelden und
  danach ab und zu einen Hinweis mit dem Weg zu den Add-ons. Dort führt ein Link direkt zur
  Schlüssel-Seite von Mistral oder NVIDIA. Die Knöpfe „Mit Google/Apple/Microsoft“ sind weg.
- **Konten:** Kontensystem ohne Code. Das erste Konto bekommt Ultra, jedes weitere Pro ohne
  Token-Grenze. API-Schlüssel liegen nur im eigenen Konto.
- **Secure Pro** beantwortet nur noch Fragen zu Sicherheit. Es sucht in keinem Netz.
- **Speicher:** höchstens 20 MB je Konto.
- **Gelöscht:** virtual machine, WhatsApp und Signal, Server-Verbund, Auto-Upgrading,
  Zuhause & Netz (Home Assistant, Lager, Heimnetz), Auslastung und Mitlesen. Das Paket für
  Vercel ist ohne neonize, Pillow und zxing-cpp kleiner.
- **Google** bleibt nur für Gmail und Google Kalender.

Alle früheren Änderungen: [CHANGELOG.md](CHANGELOG.md).

## Inhalt

- [Was Aquaticy kann](#was-aquaticy-kann)
- [Quickstart](#quickstart)
- [Installation im Detail](#installation-im-detail)
- [Benutzung im Terminal](#benutzung-im-terminal)
- [Die Weboberfläche](#die-weboberfläche)
- [Konten: Normal, Pro und Ultra](#konten-normal-pro-und-ultra)
- [Add-ons](#add-ons)
- [Speicher](#speicher)
- [Gmail und Kalender](#gmail-und-kalender)
- [Sicherheit, Rechts-Leitplanken und Ai-guard](#sicherheit-rechts-leitplanken-und-ai-guard)
- [Modelle und Anbieter](#modelle-und-anbieter)
- [Suche](#suche)
- [Konfiguration](#konfiguration)
- [Konten verwalten (Betreiber)](#konten-verwalten-betreiber)
- [Entwicklung](#entwicklung)
- [Lizenz](#lizenz)

---

## Was Aquaticy kann

**Recherche**
- Sucht im Web, liest die Seiten und nennt zu jeder Angabe die Quelle.
- Versteht Nachfragen wie „nur die mit 4+ Sternen“.
- Fragt nach, wenn etwas Wichtiges fehlt – Budget, Ort oder was genau gemeint ist.
- **Nachrichten:** „Was gibt's Neues?“ bringt die aktuellen Meldungen selbst, mit Quelle und
  Uhrzeit.
- **Karte:** findet kleine Läden, Werkstätten und Praxen über OpenStreetMap, auch ohne Website.
- **Strukturieren:** zerlegt große Fragen und schickt für jeden Teil einen Helfer los. Im
  Pro-Modus bis zu 50 gleichzeitig.
- **Gegenprüfen:** sucht Ergebnisse auf anderen Seiten nach.
- **Bilder:** Foto anhängen – Aquaticy erkennt, was darauf ist, und sucht danach.
- Geht auch ohne Websuche. Dann antwortet Aquaticy aus eigenem Wissen und sagt, wo es veraltet
  sein kann.
- „Hallo“, „Danke“ oder „Wer bist du?“ beantwortet Aquaticy sofort, ohne Modell.

**Arbeitsweisen** (links in der Seitenleiste, unter dem Logo)
- **Normal:** ein Gespräch. Gesucht wird, wenn es nötig ist.
- **Pro:** für große Fragen. Das stärkste Modell, bis zu 50 Helfer. Dauert länger, ist genauer.
- **Code:** schreibt und erklärt Code. Ausgeführt wird er nicht.

**Oberfläche**
- Terminal, Browser und Handy, jeweils passend aufgebaut.
- **Design:** Hell, Dunkel oder wie das System. Standard (grün), Schlicht oder eigene Farben.
  Auto-Scroll beim Schreiben an oder aus.
- **Spracheingabe:** 🎤 neben dem Senden-Knopf. Sprechen, und das Gesagte geht als Frage los.
- **Sprache:** Deutsch oder Englisch.
- Chats durchsuchen, umbenennen und exportieren (HTML, Markdown, CSV).

**Extras**
- **Add-ons:** **NVIDIA NIM** und **Mistral** (die einzigen Modelle mit API-Schlüssel), GitHub,
  Wetter, RSS-Feeds, Tagesschau, Wikipedia, Währungsrechner, Feiertage. Dazu die Plugins **Code-Review** und **Security-Review**. Die Dienste
  und Plugins haben im Chat einen Befehl: `/code-review`, `/github`, `/wetter` …
- **Speicher:** merkt sich, was länger gilt. Verschlüsselt und jederzeit einsehbar.
- **Gmail und Kalender:** lesen, Termine anlegen, Entwürfe schreiben. Verschickt wird nichts.
- **Eigene Dienste zuerst:** Fragst du nach deinen Mails oder Terminen, sieht Aquaticy dort nach und sucht nicht im Internet. Ist der Dienst nicht
  verbunden, sagt es dir, wo du ihn verbindest.
- **KI-Bilder** und **automatische Modellwahl**.

**Stabil im Betrieb**
- Port belegt? Aquaticy nimmt den nächsten freien.
- Absturz? Automatischer Neustart, höchstens fünfmal in zehn Minuten.
- Anbieter streikt? Das schnelle Modell desselben Anbieters springt ein.
- Verbindung kurz weg? Die Seite holt die laufende Antwort zurück.
- Fehler erscheinen als verständlicher Satz, nie als technischer Fehlertext.

---

## Quickstart

```bash
# 1. Installieren
git clone --branch Aquaticy-ai --single-branch https://github.com/Evodragon976/Aquaticy-Test.git
cd Aquaticy-Test
uv tool install --force --reinstall .
aquaticy --version            # 16.1.3

# 2. Ollama automatisch prüfen/einrichten, dann Modell und Suche
aquaticy setup

# 3. Loslegen – im Terminal …
aquaticy

# … oder im Browser
aquaticy web
```

**Du brauchst:** Python 3.11 oder neuer und [uv](https://docs.astral.sh/uv/).

**Mindest-Hardware:**

| Betrieb | CPU | RAM | Speicher |
|---|---|---|---|
| Modell in der Cloud (Mistral, NVIDIA NIM) | 1 Kern | 1 GB | 1 GB |
| + Seiten mit echtem Browser | 2 Kerne | 2 GB | 2 GB |
| Lokales Modell mit Ollama | 4 Kerne | 8 GB (GPU empfohlen) | 10 GB |

`aquaticy setup` fragt:

| Was | Woher | Pflicht? |
|---|---|---|
| Ollama | Vorhandene Installation verwenden, sonst installieren; laufende Dienste bleiben unverändert | für lokale Modelle; Cloudbetrieb mit `--no-ollama` |
| KI-Anbieter | Mistral oder NVIDIA NIM (den Schlüssel verknüpfst du danach in der Weboberfläche unter Add-ons) · oder lokal mit [Ollama](https://ollama.com), ohne Schlüssel | ja |
| Suchmaschine | nichts – die offene Suche braucht keinen Schlüssel | nein |

Aquaticy testet alles, bevor es speichert. Die Einstellungen liegen in
`~/.config/aquaticy/.env` und sind nur für dich lesbar.

Schon zu Beginn von `aquaticy setup` wird Ollama gesucht und bei Bedarf installiert.
Installationsschritte werden angezeigt und bestätigt; `aquaticy setup --yes`
bestätigt diese Schritte vorab und wählt bei lokalen Modellen die Empfehlung.
Die Fragen zu Anbieter, Suche und allgemeinen Einstellungen bleiben interaktiv.
`aquaticy setup --no-ollama` erhält die Einrichtung für reinen Cloudbetrieb.
Der Python-Paketmanager selbst startet keine Installation mit Verwalterrechten.

Eine einzelne Frage ohne Chat:

```bash
aquaticy "welche Bahnstrecken in NRW sind gerade gesperrt?"
```

**Aktualisieren** (im Repo-Ordner):

```bash
cd ~/Aquaticy-Test
git switch Aquaticy-ai
git pull --ff-only origin Aquaticy-ai
uv tool install --force --reinstall .
aquaticy --version
```

`git pull` allein reicht nicht. Erst der `uv`-Befehl installiert die neue Fassung. Mit dem
[ZIP-Download](https://github.com/Evodragon976/Aquaticy-Test/archive/refs/heads/Aquaticy-ai.zip)
lädst du das ZIP neu und führst `uv tool install --force --reinstall .` im entpackten Ordner aus.

---

## Installation im Detail

### Linux und macOS

Wie im Quickstart. Zum Entwickeln:

```bash
uv venv && uv pip install -c constraints.txt -e ".[browser,dev]"
uv run aquaticy
```

### Windows (PowerShell)

```powershell
# uv installieren, falls es fehlt
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

git clone --branch Aquaticy-ai `
  https://github.com/Evodragon976/Aquaticy-Test.git
cd Aquaticy-Test
uv tool install --force --reinstall .
uv tool update-shell        # danach PowerShell neu öffnen

aquaticy install-model      # holt Ollama per winget und lädt die Modelle
```

- Ohne winget: Installer von [ollama.com/download](https://ollama.com/download) laden, dann
  `aquaticy install-model` erneut starten.
- Pfade in Anführungszeichen: `aquaticy --image "C:\Users\du\Bilder\foto.jpg"`
- Pfeiltasten-Verlauf im Chat: `pip install pyreadline3`

### Ganz ohne Schlüssel: lokales Modell

```bash
aquaticy install-model
```

Der Befehl sucht Ollama, installiert es bei Bedarf und startet es, falls es noch nicht läuft.
Downloads werden vorher bestätigt. Er schlägt ein Modell vor, das
zu Arbeitsspeicher und Grafikkarte passt, lädt es und testet, ob es Werkzeuge bedienen kann.
Bei fehlgeschlagener Prüfung warnt Aquaticy; die Übernahme erfordert eine ausdrückliche
Bestätigung oder `--yes`. Auf Wunsch kommt ein Bildmodell dazu.

```bash
aquaticy install-model --model qwen2.5:14b                    # nur Text
aquaticy install-model --vision-model llava:7b                # Text + Bild
aquaticy install-model --vision-only --vision-model llava:7b  # nur Bild nachrüsten
aquaticy install-model --yes                                  # ohne Rückfragen
```

**Ein Modell für alles** (Suche und Bilder):

| Modell | ca. Größe | ab VRAM |
|---|---|---|
| `qwen3-vl:4b` | 3,3 GB | 6 GB |
| `gemma4:e4b` | 3,5 GB | 6 GB |
| `qwen3-vl:8b` | 6,1 GB | 12 GB |
| `gemma4:12b` | 6,6 GB | 10 GB |
| `gemma4:26b` | 16,0 GB | 24 GB |

**Nur Recherche:** `qwen2.5:3b`, `qwen2.5:7b`, `llama3.1:8b`, `qwen3:8b`, `qwen2.5:14b`.
**Nur Bilder:** `moondream`, `gemma3:4b`, `llava:7b`, `minicpm-v`, `gemma3:12b`.

> Das Kürzel muss `ollama_chat/` heißen, nicht `ollama/`. Nur so kommen Werkzeuge durch.
> `aquaticy install-model` schreibt es richtig.

Wird der Grafikspeicher knapp (`model runner has unexpectedly stopped`), bietet Aquaticy ein
kleineres Modell an. Von Hand: `ollama ps`, `ollama stop <modell>`.

### Vercel

In diesem Repo (Aquaticy-Test) läuft auf Vercel **die ganze Oberfläche**: Anmeldung, Chats,
Pro und Code, Gedächtnis, Notizen und die Modellwahl (`aquaticy/vercel.py`, eingetragen in
`pyproject.toml` unter `[tool.vercel]`). Es gelten dieselben Sicherheitsregeln wie in der App.

**So richtest du es ein.** Trag bei Vercel unter *Settings → Environment Variables* ein:

| Name | Wofür |
|---|---|
| `AQUATICY_VERCEL_SECRET` | Schlüssel für die Sicherung, mindestens 32 Zeichen. Gut aufheben: Ohne ihn lässt sich die Sicherung nicht mehr öffnen. |
| `BLOB_STORE_ID` | Kommt von selbst, wenn du deinen **privaten** Blob-Speicher mit dem Projekt verbindest (*Storage → Connect*). Aquaticy meldet sich dann wie das Blob-SDK über OIDC an. Ältere Speicher liefern stattdessen `BLOB_READ_WRITE_TOKEN`; ein eigenes Token geht als `AQUATICY_BLOB_TOKEN`. |

**Konten.** Hier läuft das Kontensystem, ohne Code. Das **erste Konto bekommt Ultra**, das
bist du. **Jedes weitere bekommt Pro**, ohne Token-Grenze. Was in der App aus Sicherheitsgründen
an Ultra hängt, bleibt bei dir: die Rechts-Leitplanken abschalten, eigene Adressen für Modell
oder Suche, und nie vom Missbrauchsschutz gesperrt werden. Leg dein Konto also als Erstes an.

**Schlüssel nur im eigenen Konto.** Jedes Konto trägt seinen API-Schlüssel selbst ein: unter
*Add-ons → NVIDIA NIM* oder *Mistral*. Dort führt ein Link direkt zur Seite des Anbieters, auf
der du den Schlüssel bekommst. Der Schlüssel liegt verschlüsselt nur in deinem Konto. Andere
Konten sehen und nutzen ihn nicht. Schlüssel, die bei Vercel stehen, nimmt Aquaticy beim Start
heraus. Solange der Vercel-Login als Schutz an ist (*Settings → Deployment Protection*), kommen
nur Mitglieder deines Vercel-Teams auf die Seite.

**Modelle.** Voreingestellt ist **Aquaticy Standard**: Es antwortet ohne Sprachmodell und ohne
Schlüssel. Mit eigenem Schlüssel wählst du unter *Modelle und Verbindungen → Modell* jedes Modell
von Mistral oder NVIDIA NIM, zum Beispiel Gemma 4 (`nvidia_nim/google/gemma-4-31b-it`). NVIDIA
bietet Gemma 4 mit 2 Milliarden Parametern (E2B) nicht als Online-Dienst an. Das kleinste Gemma
dort ist `nvidia_nim/google/gemma-3n-e2b-it`.

**Deine Daten und Redeploys.** Eine Vercel-Funktion hat keine bleibende Festplatte. Deshalb packt
Aquaticy nach jeder Änderung den ganzen Datenordner zusammen: Konten, Chats, Gedächtnis,
Einstellungen und Schlüssel. Es verschlüsselt das Paket mit `AQUATICY_VERCEL_SECRET` und legt
es in deinem **privaten Blob-Speicher** ab. Startet eine Funktion neu, holt Aquaticy das Paket
zurück. Ein Redeploy, ein neuer Push oder ein Kaltstart ändert daran nichts, denn der
Blob-Speicher gehört zum Projekt, nicht zum Deployment.

Zwei Dinge musst du dafür beachten:

- Lass `AQUATICY_VERCEL_SECRET` gleich. Mit einem anderen Schlüssel lässt sich die Sicherung
  nicht mehr öffnen. Aquaticy startet dann nicht, statt deine Daten zu überschreiben.
- Lass den Blob-Speicher mit dem Projekt verbunden. Ohne ihn speichert Aquaticy nichts, und
  beim nächsten Kaltstart ist alles weg.

**Speicher-Verbund mit Neon und Supabase (seit 16.1.3).** Verbindest du Postgres-Datenbanken
mit dem Projekt (*Storage* im Vercel-Dashboard), nutzt Aquaticy sie statt des einen Pakets im
Blob-Speicher. Es erkennt sie an den Variablen `POSTGRES_URL`, `STORAGE_POSTGRES_URL`,
`STORAGE2_POSTGRES_URL` und so weiter. Die Reihenfolge legt die Aufgaben fest:

| Datenbank | Aufgabe |
|---|---|
| 1. (ohne Präfix) | Konten, Anmeldungen, Einstellungen |
| 2. und alle ab der 4. | Profile: Chats, Gedächtnis und Dateien je Konto |
| 3. | Cache mit Ablaufzeit: Bilder, Wetter, Wikipedia |

- Mit einer Datenbank macht sie alles. Mit zweien hält die zweite Profile und Cache.
- Jeder Teil liegt zusätzlich als Spiegel auf einer zweiten Datenbank. Fällt eine aus, liest
  Aquaticy vom Spiegel.
- Alles ist mit `AQUATICY_VERCEL_SECRET` verschlüsselt. Die Tabellen liegen im Schema
  `aquaticy`. Die Daten-API von Supabase zeigt dieses Schema nicht.
- Beim ersten Start übernimmt Aquaticy den Stand aus dem Blob-Speicher. Danach schreibt es
  nicht mehr dorthin. Der Blob-Speicher bleibt als alter Stand liegen.
- `AQUATICY_VERBUND=0` schaltet den Verbund ab. Aquaticy nimmt dann wieder den Stand aus dem
  Blob-Speicher. Was seit der Übernahme dazukam, fehlt dort.
- Grenze: Die Konten-Datenbank ist eine Einheit. Schreiben zwei Instanzen sie in derselben
  Sekunde, gewinnt die spätere.
- Die Datenbanken speichern nur. Ein Sprachmodell läuft dort nicht.

**Was auf Vercel fehlt.** Lokale Modelle. Das braucht einen Rechner mit Ollama. Virtual
machine, WhatsApp und Signal, Server-Verbund, Auto-Upgrading, Coworker und Zuhause & Netz gibt
es in Aquaticy-Test gar nicht mehr (seit 16.0.0 und 16.0.1). Puffert
Vercel die Antwort, kommt sie erst am Stück. Eine Antwort darf höchstens so lange dauern, wie
Vercel eine Funktion laufen lässt. Ohne verbundene Datenbank gilt: Laufen mehrere Instanzen
gleichzeitig, gewinnt die zuletzt gespeicherte Sicherung. Global Config (früher Edge Config)
nutzt Aquaticy nicht: Die App kann dort nicht schreiben.

Den Cloudflare-Worker (`worker/`, `wrangler.toml`) gibt es weiterhin, siehe
[worker/README.md](worker/README.md).

### Seiten mit echtem Browser laden

Für Seiten, die ihren Inhalt erst per JavaScript laden:

```bash
aquaticy install-browser
```

---

## Benutzung im Terminal

### Slash-Befehle

| Befehl | Wirkung |
|---|---|
| `/max <frage>` | im Pro-Modus mit allen Helfern recherchieren |
| `/location <ort>` | Ortsfilter setzen (ohne Ort: aufheben) |
| `/model <name>` | Modell wechseln, z. B. `mistral/mistral-large-latest` |
| `/image <pfad>` | Bild beschreiben lassen und damit weitersuchen |
| `/export html\|md\|csv` | Recherche dieser Sitzung speichern |
| `/history` | frühere Recherchen |
| `/notes` | Merkzettel |
| `/notes delete <nr>` / `/notes clear` | eine oder alle Notizen löschen |
| `/clear` | Gespräch neu beginnen |
| `/memory` / `/forget` | Langzeitspeicher zeigen oder leeren |
| `/uploads` / `/uploads clear` | hochgeladene Dateien zeigen oder löschen |
| `/help` | Übersicht |
| `/<plugin> <text>` | ein eingeschaltetes Plugin nutzen, z. B. `/code-review`, `/github` |
| `/quit` / `/exit` / `/q` | beenden (auch <kbd>Strg</kbd>+<kbd>D</kbd>) |

### Optionen

```bash
aquaticy --location "Mönchengladbach" --lang de   # Ortsfilter
aquaticy --model mistral/mistral-large-latest     # Modell für diese Sitzung
aquaticy --image foto.jpg                         # Bild als Ausgangspunkt
aquaticy --max-calls 30                           # mehr Suchen je Frage
aquaticy --no-stream                              # Antwort am Stück
aquaticy --download-images                        # Bilder beim Export mitspeichern
```

### Alle Befehle

```bash
aquaticy setup                  # Ersteinrichtung
aquaticy config                 # aktive Einstellungen prüfen
aquaticy web                    # Weboberfläche starten
aquaticy web --lan              # auch im Heimnetz und über Tailscale
aquaticy search "cafés köln"    # nur suchen, ohne KI
aquaticy fetch https://…        # nur eine Seite lesen, ohne KI
aquaticy history                # frühere Recherchen
aquaticy export html -n 3       # letzte 3 Recherchen exportieren
aquaticy notes                  # Merkzettel (--delete N löscht)
aquaticy cache                  # Zwischenspeicher (--clear leert ihn)
aquaticy install-model          # lokales Modell einrichten
aquaticy install-browser        # echter Browser für schwierige Seiten
aquaticy account                # dein Konto (ohne Kontensystem): anlegen, Passwort neu setzen
aquaticy google                 # Gmail und Kalender verbinden (--aendern: auch schreiben)
aquaticy list                   # Konten mit Kürzel (#…), Geräten, Nutzung, Ai-guard
aquaticy remove "name"          # Konto samt Daten löschen (--yes ohne Rückfrage)
aquaticy ban "name"             # Konto, IP-Adresse oder Kürzel ("#1a2b3c4d") sperren
aquaticy unban "name"           # wieder freigeben
aquaticy aiguard "Satz"         # wie Ai-guard einen Satz einstuft (sperrt niemanden)
aquaticy pro-code               # Code für neue Pro-Konten
aquaticy ultra-code             # Code für neue Ultra-Konten
aquaticy version
```

---

## Die Weboberfläche

```bash
aquaticy web
```

`aquaticy web` läuft nur auf diesem Rechner. `aquaticy web --lan` öffnet es auch fürs
Heimnetz und für Tailscale.

Beim Start stehen alle Adressen im Terminal.

**Chat.** Links unter dem Logo Normal, Pro und Code, darunter die letzten Chats
(durchsuchbar). In der Mitte das Gespräch, unten die Eingabe: 📎 Anhängen, die Modellauswahl,
🎤 Mikrofon und Senden. Während einer Recherche kannst du in einen anderen Chat wechseln. Die
Recherche läuft weiter. Auf dem Handy liegt die Seitenleiste hinter ☰, Fenster füllen den
ganzen Bildschirm.

**Code-Chats für sich (seit 13.0.0 Luna).** Ein Chat ist entweder ein Code-Chat oder ein
Chat für Normal und Pro – wie bei Claude. Ein Klick auf **Code** zeigt links nur die
Code-Chats und beginnt einen neuen Code-Chat. Normal und Pro zeigen die anderen Chats; jeder
trägt ein Schild „Normal“ oder „Pro“. Zwischen Normal und Pro wechselst du im selben Chat.
Zwischen Code und Normal/Pro nicht: Dafür beginnt ein neuer Chat. Öffnest du einen Chat aus
der Liste, stellt sich der Modus darauf ein. Auch der Server mischt nichts: Eine Code-Frage in
einem Normal-Chat (oder umgekehrt) lehnt er ab.

**Spracheingabe.** Tipp auf 🎤 und sprich. Sobald du aufhörst, geht das Gesagte als Frage los;
nochmal tippen beendet das Zuhören, Esc bricht ab. Die Sprache erkennt dein Browser, nicht
Aquaticy: Die meisten Browser schicken die Aufnahme dafür an ihren Hersteller (Chrome: Google,
Edge: Microsoft, Safari: Apple); kann er es auf dem Gerät, nutzt Aquaticy das. Aquaticy bekommt
nur den erkannten Text. Vor der ersten Nutzung steht dieser Hinweis da. Geht nur über https oder
auf dem eigenen Rechner (localhost), nicht in Firefox.

**Weg und wieder da.** Eine Anfrage läuft auf dem Server, nicht im Browser. Du kannst die App
verlassen, das Handy sperren oder den Tab schließen. Kommst du zurück, hängt sich die Seite
wieder an. Ist die Antwort inzwischen fertig, öffnet sich ihr Chat mit der ganzen Antwort,
auch nach Stunden (bis zu einer Woche, solange der Server läuft). Abgebrochen wird nur mit
Stopp oder beim Wechsel in einen anderen Chat.

**Nachfragen statt raten.** Fehlt etwas, ohne das Aquaticy raten müsste (der Ort bei etwas
Örtlichem, der Zeitraum, das Budget, welches von mehreren gleichnamigen Dingen gemeint ist),
fragt es in einem Fenster nach. Im Denken- und Pro-Modus geschieht das vor der Recherche:
erst die Frage, dann suchen die Agenten mit deiner Antwort.

**Was du im Chat klärst, gilt im Chat.** Fragt Aquaticy nach (etwa nach dem Ort) und du
antwortest im Fenster, merkt es sich die Antwort für alle weiteren Fragen in diesem Chat,
auch nach dem Wiederöffnen. Ein neuer Chat beginnt ohne sie.

**Gezielte Fragen bekommen die gezielte Antwort.** Fragst du nach einer bestimmten Angabe
(welche Filme laufen, Speisekarte, Öffnungszeiten, Abfahrten, Preise, Konzerte), sucht
Aquaticy genau diese Angabe auf den Seiten der Orte. Nur Namen und Bewertungen reichen nicht:
Fehlt die Angabe und wurde keine Seite gelesen, geht die Antwort einmal zurück.

**Während Aquaticy arbeitet,** stehen nur wenige Zeilen da („Denken“, „Websuche“ …). Ein Klick
zeigt, was darin passiert ist. Fehler und Sperren bleiben sichtbar. „↻ Erneut versuchen“ stellt
die Frage noch einmal.

**Modellauswahl** (gleich nach 📎 Anhängen):
- **Modelle:** Aquaticy Standard (ohne Sprachmodell), Mistral, NVIDIA NIM und lokale Modelle.
  Es steht nur da, was wirklich antwortet: ein Cloud-Modell nur mit
  Schlüssel, ein lokales nur, wenn es in Ollama installiert ist. Die Liste fragt Ollama bei jedem
  Öffnen neu; `aquaticy web` zeigt beim Start, welche Modelle Ollama hat, und startet Ollama,
  wenn das eingestellte Modell lokal ist.
- **Kontextfenster** (nur lokale Modelle): Ein Regler unter der Liste stellt ein, wie viel vom
  Gespräch das Modell auf einmal überblickt. Daneben steht, wie viel Arbeitsspeicher das kostet.
  Bei bekanntem Aufbau begrenzt Aquaticy ein eingestelltes Fenster auf höchstens 5 GB
  Kontextspeicher. Fehlen Modellangaben, gilt höchstens der Standard von 16.384 Tokens;
  der tatsächliche Speicherbedarf ist dann unbekannt. Der Expertenwert `0` überlässt das
  Fenster weiterhin Ollama und unterliegt dieser Begrenzung nicht. Die Auswahl zeigt das
  ausdrücklich als „Ollama-Standard“. Modellgewichte kommen zum Kontextspeicher hinzu.
- **Modelle und Verbindungen:** Die Modellauswahl gibt es ausschließlich im Chat. Über den
  gleichnamigen Knopf im Modellmenü richtest du Haupt-, Vision-, Helfer- und Code-Modell
  sowie die eigene Modelladresse ein. Anbieter-Schlüssel bleiben im jeweiligen Add-on.
- **⚡ Aufwand:** Denktiefe Low, Medium oder High und die Zahl der Helfer (Normal und Code
  1–12, Pro 1–50).
- **⚙ Weitere Einstellungen:** Websuche, Denken, Strukturieren, Gegenprüfen.

**Einstellungen** speichern sich selbst. Schalter sofort, Textfelder beim Verlassen. Was nur
Ultra darf, trägt ein 🔒.
- **Konto:** Name, E-Mail, Kontotyp, Nutzung, Abmelden. **Sicherheit** mit deinen Geräten,
  Passwort ändern, überall sonst abmelden. **Daten und Konto löschen**.
- Dazu: Speicher, Nutzung, Gmail & Kalender, Secure Pro, Suche, Ort & Sprache,
  **Dev settings** (Ultra).

**Auf dem Handy** wird die Kopfzeile nach dem Senden mit einer kurzen Animation kompakter.
„Infos“ klappt Ortsfilter und Chat-Status wieder auf. Seitenleiste, Einstellungen und neuer
Chat bleiben erreichbar; die Tasten behalten ihre mindestens 44 Pixel große Trefferfläche.
Ein neuer Chat zeigt die volle Kopfzeile. Bei reduzierter Bewegung entfällt die Animation.

**Design** (links unten): Hell, Dunkel oder wie das System. Standard, Schlicht oder eigene
Farben. Dazu Schriftgröße, **Auto-Scroll** (an: der Chat läuft beim Schreiben mit, aus: er
bleibt stehen, wo du liest) und Sprache. Das gilt auf jedem Gerät.

**Merkzettel:** was Aquaticy über dich weiß. Jede Zeile lässt sich löschen.

---


## Konten: Normal, Pro und Ultra

**Standard: ein Konto (seit 13.0.0 Luna).** Ohne Kontensystem gibt es auf deinem Rechner genau
ein Konto: deins, mit allen Rechten (Ultra). Du meldest dich mit **Nutzername und Passwort**
an – so kommt niemand sonst an deine Chats, auch nicht im Heimnetz. Eine E-Mail-Adresse
brauchst du nicht.

- **Anlegen:** am Ende von `aquaticy setup` im Terminal, mit `aquaticy account` oder beim
  ersten Öffnen im Browser. Im Browser brauchst du dafür den **Einrichtungscode**. Er steht im
  Terminal, in dem `aquaticy web` läuft, solange es noch kein Konto gibt. So kann niemand
  anderes im Netz dein Konto zuerst anlegen.
- **Passwort vergessen:** `aquaticy account` am Rechner setzt Nutzername und Passwort neu und
  meldet alle Geräte ab.
- **Kontensystem für mehrere Nutzer:** In `aquaticy setup` einschalten (Frage „Kontensystem
  für mehrere Nutzer einschalten?“, Standard: nein) oder `aquaticy setup --accounts`. Dann gilt
  alles unten: Registrieren mit E-Mail, Normal, Pro und Ultra. Gespeichert ist das als
  `AQUATICY_ACCOUNTS=true` in der `.env`.
- **Umstieg von früher:** Gab es schon mehrere Konten und das Kontensystem ist aus, gilt das
  älteste Ultra-Konto (sonst das älteste Konto, es wird Ultra). Ein anderes wählst du mit
  `aquaticy account --use NAME`. Die anderen Konten bleiben gespeichert, können sich aber
  nicht anmelden, bis das Kontensystem wieder an ist. Im Terminal steht beim Start, welches
  Konto gilt und wie viele andere es gibt. Löschst du das eine Konto, rückt kein anderes
  nach: Ein neues legst du mit dem Einrichtungscode oder `aquaticy account` an.

**Mit Kontensystem.** Wer die Weboberfläche öffnet, legt zuerst ein Konto an. Jedes Konto hat
eigene Chats, Einstellungen, Speicher und Schlüssel.

**Gleichzeitige Chats mit Ollama.** Verschiedene Konten können gleichzeitig Fragen stellen
und Antworten empfangen; im Test sind es zehn Konten mit zehn offenen Antwortstreams.
Ein Stopp gilt nur für den ausgewählten Chat. Weitere Fragen im selben Chat warten auf
dessen laufende Antwort. Bei 32 laufenden oder wartenden Anfragen in einem Chat kommt
eine Meldung statt weiterer Hintergrundarbeit. Andere Chats bleiben nutzbar.

Seit **12.9.9 Terra** ändern Setup und Modellinstallation keine laufenden Ollama-Dienste.
Die Frage zum Einrichten des Parallelbetriebs entfällt. Ein laufender Dienst wird weiterverwendet.
Wenn Aquaticy einen eigenen Ollama-Prozess startet, bleiben dessen lokale Adresse und
Parallelverarbeitung erhalten. Zusätzliche Anfragen warten in Ollamas Warteschlange.
Die tatsächliche Rechenleistung hängt von Modell, RAM und GPU ab.
Entfernte Modellserver werden nicht umkonfiguriert.

Schlägt Installation oder Start fehl, meldet Setup den Fehler und lädt kein Modell herunter.

| | Normal | Pro | Ultra |
|---|---|---|---|
| Recherche, Chat, Code-Modus, Add-ons | ✔ | ✔ | ✔ |
| Nutzung je 5-Stunden-Sitzung | 300.000 Token | 533.333 Token | unbegrenzt |
| Nutzung je Woche | 2 Mio. Token | 4 Mio. Token | unbegrenzt |
| Eigene Adressen für Modell und Suche | – | – | ✔ |
| Rechts-Leitplanken abschaltbar (nur fürs eigene Konto) | – | – | ✔ |
| Ai-guard | sperrt | sperrt | warnt nur |
| Code zum Anlegen | – | 9 Zeichen | 14 Zeichen |

**Codes.** Beim ersten Start zeigt Aquaticy zwei geheime Codes im Terminal: den **Pro-Code**
(9 Zeichen) und den **Ultra-Code** (14 Zeichen). Später zeigen `aquaticy pro-code` und
`aquaticy ultra-code` sie wieder. Vorgeben kannst du sie mit `AQUATICY_PRO_CODE` und
`AQUATICY_ULTRA_CODE`.

**Nutzung.** Die Sitzung beginnt mit deiner ersten Nachricht und dauert fünf Stunden. Die Woche
beginnt zur Uhrzeit deiner Kontoerstellung. Beides steht in Prozent unter *Einstellungen →
Nutzung*. Gezählt wird auf dem Server. Wer Chats löscht, löscht nicht seinen Verbrauch.
Anfragen mit **eigenen Schlüsseln** zählen nicht.

**Mehrfachkonten.** Zwei Menschen im selben Haushalt teilen sich eine Adresse. Das allein
sperrt nicht. Aquaticy zählt Punkte gegen jedes vorhandene Konto. Ab **3 Punkten** gibt es kein
neues Konto.

| Anhaltspunkt | Punkte |
|---|---|
| dasselbe Gerät (zufällige Kennung im Cookie `aquaticy_device`) | 3 |
| gleiche Hardware **und** gleicher Browser | 1,5 |
| gleiche Hardware | 1 |
| gleicher Browser | 0,5 |
| dieselbe IP-Adresse (beim Anlegen oder zuletzt) | 1 |
| sehr ähnliche E-Mail-Adresse (`max.muster@…` / `maxmuster7@…`) | 1 |

Je Konto speichert Aquaticy höchstens 20 Geräte. Die Kennung nur als Hash, Hardware und Browser
verschlüsselt. Der Betreiber sieht nur die Zahl der Geräte und ein Kürzel der Adresse
(„#1a2b3c4d“). Kein Canvas- oder Audio-Fingerabdruck.

**Verschlüsselung.** Chats, Uploads, Bilder, IP-Adressen, Geräte und E-Mail-Adressen liegen
mit AES-256-GCM verschlüsselt. Jedes Konto hat einen eigenen Schlüssel, abgeleitet aus
`data.key`. Passwörter: Argon2id (64 MiB, 3 Durchläufe) mit Salz und geheimem Serverwert
(`auth.key`). Sichere `data.key` und `auth.key` nie zusammen mit den Daten. Ohne sie sind die
Daten nicht mehr lesbar. Der Server braucht den Schlüssel, um mit Chats zu arbeiten. Geschützt
ist gegen gestohlene Datenbanken und Sicherungen und gegen andere Konten.

---

## Add-ons

*Im Chat unter Modelle und Verbindungen → Add-ons oder unter Einstellungen → Add-ons.* Jedes Add-on lässt sich
installieren, an- und ausschalten und entfernen. Anbieter und Schlüssel verwaltest du im jeweiligen Add-on. Anmelden musst du dich selbst –
Aquaticy kennt keine Passwörter. Unter **Rechte** stellst du ein, was Aquaticy damit darf.

### KI-Modelle: NVIDIA NIM und Mistral

Die beiden stehen ganz oben unter Add-ons. Sie sind der **einzige Ort** in Aquaticy, an dem
sich ein API-Schlüssel eintragen lässt. In vier Schritten:

1. **„Installieren“** beim Add-on NVIDIA NIM oder Mistral.
2. **„Schlüssel bei … holen“** öffnet die Seite des Anbieters, auf der es den Schlüssel gibt.
   Dort meldest du dich selbst an.
3. Einen **API-Schlüssel erstellen** und kopieren.
4. In Aquaticy **„Einfügen“** oder einfügen und **„Verknüpfen“**.

Aquaticy fragt den Anbieter, ob der Schlüssel stimmt, und speichert ihn erst dann. Danach liest
es aus, welche **Modelle** dein Konto hat; sie stehen in der Modellauswahl. Nennt der Anbieter
seine Grenzen, stehen die **freien Tokens** dabei. Der Schlüssel liegt verschlüsselt in deinem
Konto, geht nur an den Anbieter und nie zurück an den Browser. **Deinstallieren** löscht ihn.

Claude, ChatGPT, Gemini und andere Anbieter in der Cloud ruft Aquaticy nicht auf. Alles
andere läuft auf dem Server: Ollama, LM Studio, vLLM oder llama.cpp.

**AI Council** (*Dev settings*): Sind NVIDIA NIM und Mistral verknüpft, arbeiten die Modelle
zusammen. Eines löst die Aufgabe, das andere prüft auf Fehler. Aquaticy ist der **Richter**: Es
nimmt die Lösung an oder schickt sie zurück, bis zu drei Runden.

### Programme und Dienste

| Add-on | Was es kann | Anmeldung |
|---|---|---|
| 🐙 GitHub | Repos, Issues, Pull Requests und Dateien lesen (nie schreiben) | Token |
| 🌦️ Wetter | Wetter und 7-Tage-Vorhersage (Open-Meteo) | keine |
| 📰 RSS-Feeds | deine eigenen Nachrichtenquellen zusammenfassen | Feed-Adressen |
| 🗞️ Tagesschau | Meldungen nach Thema oder als Suche | keine |
| 📚 Wikipedia | Begriffe nachschlagen, mit Link (Deutsch/Englisch) | keine |
| 💱 Währungsrechner | Tageskurse der EZB für gut 30 Währungen | keine |
| 📅 Feiertage | gesetzliche Feiertage weltweit, auch je Bundesland | keine |
| 🔍 Code-Review | prüft Code auf typische Fehler, gerade bei KI-Code | keine |
| 🛡️ Security-Review | sucht Sicherheitslücken nach OWASP und zeigt die Lösung | keine |

Die Tagesschau ist nur für den privaten Gebrauch. Aquaticy hält die erlaubten 60
Abrufe pro Stunde ein.

### Plugins im Chat

Tipp `/` im Chat. Aquaticy zeigt die Befehle deiner Plugins zum Auswählen. Ein Befehl gilt für
genau eine Nachricht: `/wetter Bremen` nimmt das Wetter-Add-on, `/github offene Pull Requests
in besitzer/repo` das GitHub-Add-on.

**Code-Review** und **Security-Review** sind Wissen, kein Dienst. Hinter den Befehl kommt, was
geprüft werden soll: eingefügter Code, eine Datei oder ein GitHub-Repo (mit GitHub-Add-on).
Geprüft wird im Code-Modus mit dem stärksten Modell. Die Befunde kommen nach Schwere sortiert,
jeder mit Stelle, Beispiel und Korrektur.

- **Code-Review** kennt die typischen Fehler: Logik und Randfälle, Fehlerbehandlung,
  Ressourcen, Nebenläufigkeit, Zeitzonen. Dazu die Fehler von KI-Code: erfundene Funktionen
  und Pakete, Platzhalter, Tests nur für den Erfolgsfall, veraltete Bibliotheken.
- **Security-Review** prüft nach den OWASP Top 10:2025 und den OWASP Top 10 für
  LLM-Anwendungen: Zugriffskontrolle, Injection (SQL, Shell, XSS), Anmeldung, Lieferkette,
  Prompt-Injection, Datenabfluss, zu viel Freiheit für Agenten. Aus Sicht eines Verteidigers:
  finden, belegen, beheben.

Unter **Rechte** wählst du, ob alle Befunde kommen oder nur kritische und hohe. Und ob Aquaticy
die Korrektur gleich mitschreibt.

---

## Speicher

**Speicher.** Aquaticy merkt sich, was länger gilt: Wohnort, Vorlieben, laufende Vorhaben. Nur
Text, verschlüsselt, höchstens 20 MB je Konto. Unter **„Was weißt du über mich?“** siehst du
jeden Eintrag und löschst ihn einzeln oder alle.

**Gedächtnis wie bei großen Chat-Apps.**
- Sagst du nebenbei „ich heiße Louis“, „ich wohne in Bremen“ oder „ich mag keine Pilze“,
  merkt Aquaticy sich das sofort. Schon die nächste Antwort nutzt es. Nach der Antwort sucht
  ein schnelles Cloud-Modell nach weiterem Beiläufigem.
- Auch Erschlossenes zählt: Beantwortest du „Wie alt bin ich?“ mit einer Rechnung, speichert
  Aquaticy das Geburtsdatum und rechnet das Alter jeden Tag neu aus.
- „Wie heiße ich?“ beantwortet Aquaticy sofort in einem ganzen Satz („Du heißt Louis.“).
- Je Sache gibt es einen Stand: „Ich bin nach Hamburg gezogen“ ersetzt Bremen.
- Das Gedächtnis gilt im normalen Chat, in Pro und in Secure Pro. Im Code-Modus gibt es keins.
- Gesundheit, Religion, Politik, Sexualität, Passwörter und Nummern merkt Aquaticy nur auf
  ausdrückliche Bitte. „Merk dir das nicht“ verhindert das Merken, „Vergiss, dass …“ löscht.

---

## Gmail und Kalender

Aquaticy liest Termine und Mails. Mit „Ändern erlaubt“ legt es auch Termine an und schreibt
Mail-**Entwürfe**.

**Ganze Mails lesen (seit 13.0.1 Luna).** Nach „Was sind meine neusten Mails?“ kannst du
nachfragen: „Sende mir den ganzen Text der Mail von Amazon“, „Lies mir die zweite vor“,
„Kannst du mir die Mail von der Bank zeigen?“. Aquaticy erkennt das als Frage an dein eigenes
Postfach, auch ohne „meine“. Der Rechtsprüfer erfährt das: Die eigene Post ganz zu lesen ist
erlaubt, auch Post von anderen Personen. Er prüft die Anfrage trotzdem selbst, etwa auf
Beleidigungen oder fremde Konten. Aquaticy liest eine Mail bis 6.000 Zeichen; was länger ist,
kommt gekürzt an. **Verschickt und gelöscht wird nichts.** Aquaticy bietet dafür keine
Werkzeuge an und verwendet feste API-Pfade. Googles Recht `gmail.compose` wird für Entwürfe
benötigt und erlaubt technisch auch Senden; die Begrenzung auf Entwürfe liegt daher im Code.

**Ändern klappt nur, wenn Google es erlaubt hat.** Bei der Zustimmung zeigt Google jedes Recht
einzeln, und du kannst Haken abwählen. Ein Haken fehlt? Dann steht unter „Gmail & Kalender“:
„Google hat das Ändern noch nicht erlaubt.“ Klick noch einmal auf „Verbinden“ und setz alle
Haken. Das gilt auch, wenn du „Ändern erlaubt“ erst nach dem Verbinden einschaltest.

**Ohne Rückfrage:** Mit **„Auf Befehl ohne Rückfrage ändern“** (`AQUATICY_GOOGLE_DIRECT`) trägt
Aquaticy Termine ein und legt Entwürfe an, sobald du darum bittest.
Hat es Mails oder Webseiten gelesen, fragt es trotzdem. Dein eigener Kalender zählt dafür nicht.

**Einrichten (einmal, etwa fünf Minuten):**

1. Auf [console.cloud.google.com](https://console.cloud.google.com/) ein Projekt anlegen.
2. **APIs und Dienste → Bibliothek:** „Gmail API“ und „Google Calendar API“ aktivieren.
3. **OAuth-Zustimmungsbildschirm:** Nutzertyp „Extern“, dich als Testnutzer eintragen.
4. **Anmeldedaten → OAuth-Client-ID**, Typ **Desktop-App**. Eine Weiterleitung trägst du
   nicht ein: Aquaticy nutzt dieselbe Adresse wie dein Browser (`http://127.0.0.1:8765/google`
   oder `http://localhost:8765/google`). Landest du nach der Zustimmung auf einer Seite mit
   einer Adresse zum Kopieren, füge sie in den Einstellungen ein.
5. Client-ID und Client-Secret in *Einstellungen → Gmail & Kalender* eintragen (oder als
   `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`), dann **Verbinden**.

Im Terminal: `aquaticy google` (oder `aquaticy google --aendern`). Von einem anderen Gerät aus
kopierst du die Adresse, auf der Google endet, in das Feld in den Einstellungen. **Trennen**
löscht die Zugangsdaten.

---

## Sicherheit, Rechts-Leitplanken und Ai-guard

**Feste Grenzen** (immer, für jedes Konto):
- keine Bezahlschranken, Logins oder Captchas umgehen; `robots.txt` gilt (RFC 9309);
- ins Heimnetz nur private Adressen, Webseiten nie ins Heimnetz;
- im Haus nur nach Rückfrage schalten; bei Google nie senden, nie löschen;
- Zugangsdaten nie an den Browser und nie an das Modell;
- keine PHP- oder JSP-Dateien als Upload, und Bilder müssen echte Bilder sein.

**Schutz vor Prompt-Injection.** Webseiten, Mails, Feeds und Anhänge sind für Aquaticy
*Material*, nie ein Auftrag:
- unsichtbare Zeichen fliegen raus, falsche Chat-Steuerzeichen werden entschärft;
- stehen in fremdem Text Anweisungen an eine KI, erscheint **[Schutz]** im Verlauf;
- nach fremdem Inhalt geht nichts Privates ohne Rückfrage in eine Adresse oder einen Befehl.

**Website.** Anmelde-Cookie `HttpOnly` und `SameSite=Strict`, über HTTPS auch `Secure` mit
HSTS. Strenge Content-Security-Policy, Schreibzugriffe nur von der eigenen Seite, Grenzen für
Anfragen und falsche Passwörter.

**Anmeldeschutz gegen Bots.** Vor dem Passwort bekommt jede Anmeldung eine Risikozahl aus drei
Hinweisen:

| Hinweis | gut | schlecht |
|---|---|---|
| Fingerabdruck des Clients | passt zur App (+0) | wie ein Skript (+40) |
| Fehlversuche dieses Clients in der letzten Stunde | keine (+0) | +4 je Versuch, höchstens +33 |
| dieses Gerät | schon angemeldet (+0) | neu (+20) |

Dazu kommt ein Grundwert von 6. Unter 34 geht es weiter zum Passwort. Von 34 bis 66 kommt
„Bestätige kurz, dass du ein Mensch bist“, ein Regler, den man ganz nach rechts schiebt. Ab 67
wird abgewiesen, ohne Passwortprüfung, und die Adresse eines Skripts ist 15 Minuten gesperrt.
Beispiele: App, keine Fehlversuche, bekanntes Gerät = 6; App, 6 Fehlversuche, neues Gerät = 50;
Skript, 40 Fehlversuche, neues Gerät = 99. Ein Browser, dessen Fingerabdruck passt, kommt
höchstens auf 59 und wird nie abgewiesen.

Den echten TLS-Fingerabdruck (JA3/JA4) sieht Aquaticy nicht: Auf Vercel endet die
Verschlüsselung bei Vercel, im Heimnetz gibt es keine. Als Fingerabdruck zählen deshalb
User-Agent, `Accept-Language`, die Fetch-Metadaten des Browsers (`Sec-Fetch-Site`),
`navigator.webdriver` und eine kleine Rechenaufgabe (SHA-256), die die Seite beim Besuch im
Hintergrund löst. Alles liegt nur im Arbeitsspeicher, siehe `aquaticy/botguard.py`.

**Rechts-Leitplanken.** Aquaticy prüft jede Frage gegen Grundgesetz und BGB – auch
Personensuchen, Kamerabilder und Mail-Entwürfe. Die Regeln stehen unter *Dev settings →
Welche Regeln gelten?*. Nach einer Person suchen ist erlaubt (öffentliche Angaben, Beruf).
Private Anschrift, Handynummer oder Aufenthaltsort auszuforschen ist es nicht.

- **Abgelehnt bleibt abgelehnt.** „Bitte“ oder Drängen ändern nichts. Eine neue Frage oder ein
  neuer Chat heben die Absage auf.
- **Abschalten** geht nur mit Ultra, nur in den Einstellungen und nur fürs eigene Konto.
- **Grundschutz bleibt immer:** keine Schadsoftware, keine Bilder, die echte Menschen
  herabsetzen.

**Ai-guard** läuft auf jedem Konto und entscheidet nach **Art und Schwere**:

| Art | Was passiert |
|---|---|
| Beleidigung, leicht | nur **dieser Chat** wird gesperrt |
| Beleidigung, mittel bis schwer | Bann für 1 Tag, 7 Tage oder für immer |
| Schadsoftware bauen oder installieren | sofort Bann, 4 Tage bis für immer |
| Angriffshilfe, schwerer Rechtsverstoß, Schutzregeln aushebeln | ab dem **zweiten** Anhaltspunkt Bann |
| Bagatellen, Bildung, Verteidigung | nichts |

- **Beleidigungen** erkennt Aquaticy auch ohne Modell, auf Deutsch und Englisch. Gezählt wird
  nur, was **gegen jemanden** geht. Tarnungen wie Leetspeak oder Sternchen helfen nicht.
- **Zitieren ist frei.** Hilfe beim Mobben nicht.
- **Antworten werden mitgeprüft**, wenn Rechts-Leitplanken und `AQUATICY_ANSWER_CHECK` an sind.
  Der ursprüngliche Auftrag hilft bei der Einordnung. Sachliche Beschreibungen von Risiken
  bleiben erlaubt. Bei ausgeschalteten Rechts-Leitplanken entfällt diese automatische
  Rücknahme, auch für laufende Antworten. Anbieter können weiterhin eigene Grenzen anwenden.
- Ein gesperrtes Konto kann sich anmelden und seine Chats ansehen, sonst nichts. Oben links
  steht ein rotes **Info** mit Dauer und Grund. Ultra-Konten werden nur gewarnt.

```bash
aquaticy ban "name"            # Konto dauerhaft sperren
aquaticy ban "name" --tage 7   # für 7 Tage
aquaticy ban 203.0.113.7       # IP-Adresse sperren
aquaticy unban "name"          # wieder freigeben
aquaticy aiguard "du Idiot"    # Stufe eines Satzes testen, ohne Vermerk
aquaticy aiguard --konto "name"  # die letzten Vorfälle eines Kontos
```

---

## Modelle und Anbieter

Aquaticy nimmt **Mistral** und **NVIDIA NIM** in der Cloud und sonst nur, was **auf dem
Server** läuft: Ollama, LM Studio, vLLM und llama.cpp. Andere Anbieter
(Claude, ChatGPT, Gemini, Groq, OpenRouter …) ruft es nicht auf, auch nicht über eine
eingetragene Modell-ID.

| Anbieter | Kürzel | Schlüssel |
|---|---|---|
| [Mistral](https://console.mistral.ai/api-keys/) | `mistral/` | Add-on Mistral |
| [NVIDIA NIM](https://build.nvidia.com/) | `nvidia_nim/` | Add-on NVIDIA NIM |
| Ollama (lokal) | `ollama_chat/` | – |
| LM Studio, vLLM, llama.cpp auf dem Server | `lm_studio/`, `hosted_vllm/`, `openai/` + lokale Adresse | – |

Je Anbieter wählt Aquaticy das passende Modell:

| Aufgabe | Mistral | NVIDIA NIM |
|---|---|---|
| Recherche und Antwort | `mistral-large-latest` | `nvidia/llama-3.3-nemotron-super-49b-v1.5` |
| Helfer, Planung | `mistral-small-latest` | `nvidia/nvidia-nemotron-nano-9b-v2` |
| Code-Modus | `codestral-latest` | `qwen/qwen2.5-coder-32b-instruct` |

Hat ein Anbieter ein Modell abgeschaltet (Antwort „410 Gone“), merkt Aquaticy sich das. Die
Beobachtung gilt nur für das betroffene Konto mit seinem Schlüssel und Endpunkt; Fehler
eines Kontos sperren keine Modelle anderer Konten. Der Ersatz greift auch bei automatischer
Modellwahl sowie im Pro- und Code-Modus. Ist eine bekannte Anbieterliste leer oder enthält
sie keine verbleibenden nutzbaren Modelle, werden keine unbestätigten Standardmodelle ergänzt.
Die Modellwahl zeigt nur noch, was der Anbieter dem Konto beim Einrichten des Add-ons genannt
hat, bei NVIDIA die Nemotron-Modelle zuerst. Ein abgeschaltetes Modell ersetzt Aquaticy durch
eines aus dieser Liste. NVIDIA hat `meta/llama-3.3-70b-instruct` und `meta/llama-3.1-8b-instruct`
am 26.08.2026 abgeschaltet.

```bash
aquaticy --model mistral/mistral-large-latest
aquaticy --model nvidia_nim/nvidia/llama-3.3-nemotron-super-49b-v1.5
aquaticy --model ollama_chat/qwen2.5:7b
```

- Das Modell muss **Werkzeuge aufrufen** können, sonst kann es nicht suchen.
- Fehlt das Kürzel, ergänzt Aquaticy es.
- Ein Server mit OpenAI-Schnittstelle zählt nur unter einer lokalen Adresse (localhost,
  Heimnetz, `.local`/`.lan`). Ohne Adresse ginge `openai/…` zu OpenAI und ist gesperrt.
- Aquaticy hält die Grenzen der Anbieter ein (NVIDIA 40/Minute, Mistral 240/Minute). Anpassbar
  mit `AQUATICY_RPM` und `AQUATICY_PARALLEL_CALLS`.
- Den Schlüssel für Mistral oder NVIDIA NIM verknüpft jedes Konto selbst unter Add-ons. Modelle
  mit eigenem Schlüssel zählen nicht gegen das Limit.
- **Modell für die Agenten:** In *Modelle und Verbindungen* wählst du es aus deinen lokalen
  Modellen. Auf „Automatisch“ nimmt Aquaticy mit einem Cloud-Modell ein schnelles Modell
  desselben Anbieters (siehe Tabelle oben), lokal das Hauptmodell.
- **Zeit:** Aquaticy rechnet immer mit deutscher Zeit (Europe/Berlin, mit Sommer- und
  Winterzeit), auch wenn die Uhr des Servers auf UTC steht.

---

## Suche

Standard ist eine **offene Metasuche** über mehrere Suchdienste, ohne Schlüssel. Jede Frage
wird auf mehrere Arten gestellt (`AQUATICY_SEARCH_VARIANTS`).

| Suchmaschine | Einstellung | Schlüssel |
|---|---|---|
| Offene Suche | `duckduckgo` | – |
| Eigener [SearXNG](https://docs.searxng.org/)-Server | `searxng` + `AQUATICY_SEARXNG_URL` | – |
| [Brave Search](https://brave.com/search/api/) | `brave` | `BRAVE_API_KEY` (nur vom Betreiber in der `.env`) |
| [Tavily](https://tavily.com/) | `tavily` | `TAVILY_API_KEY` (nur vom Betreiber in der `.env`) |

**Seiten lesen.** Aquaticy liest Seiten selbst, mit ehrlicher Kennung und mit Rücksicht auf
`robots.txt`. Klappt ein Abruf nur kurz nicht (DNS, Zeitüberschreitung, Serverfehler), merkt
sich Aquaticy das nicht. Ein echter Fehlschlag bleibt höchstens eine Stunde gemerkt.

**Nachrichten.** Bei „Was sind die neusten Nachrichten?“ holt Aquaticy die Schlagzeilen selbst
aus den Feeds großer Redaktionen (Tagesschau, ZDF, Deutschlandfunk, Spiegel; in Österreich,
der Schweiz und auf Englisch passende andere). Mit Thema („Neues zu Tesla“) sucht es gezielt.

Alles auf dem eigenen Rechner – lokales Modell plus eigener Suchserver: Starte einen
[SearXNG](https://docs.searxng.org/)-Server und trag ihn ein (`AQUATICY_SEARCH_BACKEND=searxng`,
`AQUATICY_SEARXNG_URL=http://localhost:8080`).

---

## Konfiguration

Alle Werte stehen in der `.env` (Vorlage: [`.env.example`](.env.example)). Die meisten stellst
du auch in der Weboberfläche ein.

| Variable | Bedeutung | Standard |
|---|---|---|
| `AQUATICY_MODEL` | Hauptmodell (`anbieter/name`) | `mistral/mistral-large-latest` |
| `AQUATICY_VISION_MODEL` | Modell für Bilder | wie `AQUATICY_MODEL` |
| `AQUATICY_SUBAGENT_MODEL` | Modell der Agenten | das kleine des Anbieters |
| `AQUATICY_CODE_MODEL` | Modell für den Code-Modus | das stärkste erreichbare |
| `AQUATICY_API_BASE` | eigene Adresse (Ollama, eigene NIM, Proxy) | – |
| `AQUATICY_API_KEY` | Zugangsschlüssel eines lokalen Servers (vLLM, Proxy), falls er einen verlangt | – |
| `AQUATICY_AUTO_MODEL` | Modell je Nachricht automatisch wählen | `false` |
| `AQUATICY_SEARCH_BACKEND` | `duckduckgo`, `searxng`, `brave`, `tavily` | `duckduckgo` |
| `AQUATICY_SEARCH_ENGINES` | Suchdienste der offenen Suche einschränken | alle |
| `AQUATICY_SEARCH_VARIANTS` | Formulierungen je Suche (`1` = aus) | `3` |
| `AQUATICY_SEARXNG_URL` | Adresse des SearXNG-Servers | – |
| `AQUATICY_LOCATION` | Standard-Ort | – |
| `AQUATICY_LANG` / `AQUATICY_COUNTRY` | Sprache / Land der Suche | `de` / `de` |
| `AQUATICY_MAX_TOOL_CALLS` | Suchen und Seitenaufrufe je Frage | `20` |
| `AQUATICY_SUBAGENTS_AUTO` | große Fragen automatisch aufteilen | `true` |
| `AQUATICY_SUBAGENT_BUDGET` | Suchen je Helfer | `6` |
| `AQUATICY_SUBAGENT_PARALLEL` | Helfer gleichzeitig (`0` = automatisch) | lokal `2` |
| `AQUATICY_PLANNER_TIMEOUT` | Zeit fürs Aufteilen einer Frage (s) | `20` |
| `AQUATICY_CONTEXT_TOKENS` | Lokales Kontextfenster; `0` = Ollama-Standard, sonst begrenzt | `16384` |
| `AQUATICY_RPM` | Anfragen pro Minute an den Anbieter | NVIDIA `40`, Mistral `240` |
| `AQUATICY_PARALLEL_CALLS` | gleichzeitige Anfragen | NVIDIA `4`, Mistral `8` |
| `AQUATICY_FETCH_TIMEOUT` | Wartezeit je Seite (s) | `15` |
| `AQUATICY_CACHE_TTL_HOURS` | Gültigkeit des Zwischenspeichers | `24` |
| `AQUATICY_ENABLE_PLAYWRIGHT` | echter Browser für schwierige Seiten | `true` |
| `AQUATICY_BROWSER_PARALLEL` | höchstens so viele Browser gleichzeitig | `3` |
| `AQUATICY_PROXY` | Proxy für Abrufe (`http://host:port` oder `env`) | direkt |
| `AQUATICY_MEMORY` | Speicher an | `true` |
| `AQUATICY_LEGAL_GUARD` | Rechts-Leitplanken (abschaltbar nur mit Ultra) | `true` |
| `AQUATICY_ANSWER_CHECK` | Ai-guard prüft Antworten bei aktiven Rechts-Leitplanken | `true` |
| `AQUATICY_GITHUB_TOKEN` | Token des GitHub-Add-ons | – |
| `AQUATICY_GOOGLE` / `AQUATICY_GOOGLE_WRITE` | Gmail und Kalender lesen / ändern | `false` |
| `AQUATICY_GOOGLE_DIRECT` | auf Befehl ohne Rückfrage ändern, braucht `AQUATICY_GOOGLE_WRITE` | `false` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | eigene Google-Anwendung | – |
| `AQUATICY_ACCOUNTS` | Kontensystem für mehrere Nutzer (sonst ein Konto, Ultra) | `false` |
| `AQUATICY_PRO_CODE` | Code für neue Pro-Konten | zufällig |
| `AQUATICY_ULTRA_CODE` | Code für neue Ultra-Konten (14 Zeichen) | zufällig |
| `MISTRAL_API_KEY`, `NVIDIA_NIM_API_KEY` | schreibt das Add-on (ohne Konten); mit Konten gilt ein Eintrag hier als gestellt | – |
| `BRAVE_API_KEY`, `TAVILY_API_KEY` | Schlüssel der Suchmaschine, nur vom Betreiber | – |

Daten liegen unter `~/.aquaticy/` (Konten in `accounts.sqlite3`, je Konto ein Ordner unter
`users/`). Die Einstellungen liegen in `~/.config/aquaticy/.env`.

---

## Konten verwalten (Betreiber)

```bash
aquaticy account               # ohne Kontensystem: dein Konto anlegen oder Passwort neu setzen
aquaticy list                  # alle Konten: Typ, Kürzel (#…), Geräte, Nutzung, Ai-guard
aquaticy pro-code              # Code für neue Pro-Konten
aquaticy ultra-code            # Code für neue Ultra-Konten
aquaticy ban "name"            # Konto sperren (auch per IP-Adresse)
aquaticy unban "name"          # Sperre aufheben
aquaticy remove "name"         # Konto samt Daten löschen
```

---

## Entwicklung

```bash
git clone --branch Aquaticy-ai --single-branch https://github.com/Evodragon976/Aquaticy-Test.git
cd Aquaticy-Test
uv venv && uv pip install -c constraints.txt -e ".[browser,dev]"

uv run python tools/pruefung.py            # alles: ruff, mypy, bandit, JavaScript, Tests
uv run python tools/pruefung.py --schnell  # ohne Testsuite
uv run pytest                              # nur die Tests; Netz und Modelle sind gestellt

python tools/rundgang.py            # bedient die Weboberfläche wie ein Mensch
python tools/rundgang.py --bilder   # mit Bildschirmfotos
```

Wie KI-Agenten hier arbeiten und prüfen, steht in [`AGENTS.md`](AGENTS.md).

---

## Lizenz

MIT. Der volle Text steht in [`LICENSE`](LICENSE).
