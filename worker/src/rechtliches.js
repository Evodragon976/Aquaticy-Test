// Datenschutz, Cookies, Nutzung und Barrierefreiheit fuer die Cloudflare-Fassung.
//
// Diese Fassung speichert nichts -- die Seiten sagen deshalb genau das und nennen jeden
// Dienst, an den etwas geht. Aendert sich, was der Worker abruft (dienste.js, ki.js),
// muss es hier mit.

const RAHMEN = (sprache, titel, inhalt, fassung) => `<!doctype html>
<html lang="${sprache}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${titel} · Aquaticy</title>
<style>
:root{color-scheme:light dark;--bg:#f7f7f5;--text:#1d1d1b;--muted:#5d5d58;--accent:#1f6f8b}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--text:#ececea;--muted:#a5a5a0;
--accent:#6cc3e0}}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,sans-serif}
main{max-width:720px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:28px 0 6px}
p,li{max-width:65ch}.klein{color:var(--muted);font-size:.9rem}a{color:var(--accent)}
</style></head><body><main>
<h1>${titel}</h1><p class="klein">Aquaticy ${fassung} · Cloudflare</p>
${inhalt}
<p class="klein"><a href="/">${sprache === "en" ? "Back to the chat" : "Zurück zum Chat"}</a></p>
</main></body></html>`;

const DATENSCHUTZ = {
  de: `<h2>Kurz gesagt</h2>
<ul>
<li>Diese Fassung von Aquaticy hat keine Konten und keine Datenbank. Sie speichert deine
Fragen und Antworten nicht.</li>
<li>Der Chat bleibt nur in der geöffneten Seite. Lädst du sie neu, ist er weg.</li>
<li>Keine Werbung, kein Tracking.</li>
</ul>
<h2>Was wohin geht</h2>
<ul>
<li><strong>Cloudflare</strong> betreibt den Server. Cloudflare verarbeitet dabei deine
IP-Adresse und technische Angaben zur Verbindung, nach eigenen Regeln.</li>
<li><strong>Ungefährer Ort:</strong> Cloudflare schätzt aus deiner Verbindung eine Stadt.
Aquaticy nutzt sie nur, wenn du nach dem Wetter fragst und keinen Ort nennst. Gespeichert
wird sie nicht.</li>
<li><strong>Nachschlagen:</strong> Je nach Frage geht nur der Suchbegriff an einen dieser
Dienste: Wikipedia (Thema), Open-Meteo (Ortsname), tagesschau.de (Thema),
frankfurter.dev (Währungen), date.nager.at (Jahr und Land), DuckDuckGo (Thema),
MyMemory (der Text, den du übersetzen lässt). Fügst du eine Adresse ein, ruft Aquaticy
diese Seite ab; den Namen der Seite prüft es dafür bei Cloudflare-DNS.</li>
<li><strong>Folgefragen:</strong> Damit „Wie alt ist er?“ klappt, schickt die Seite bis zu
zehn Nachrichten des offenen Chats mit. Aquaticy nutzt sie nur für diese Antwort und
speichert sie nicht.</li>
<li><strong>KI-Modell:</strong> Hat der Betreiber einen Schlüssel für Mistral AI (EU) oder
NVIDIA (USA) hinterlegt, gehen deine Frage und bis zu zehn Nachrichten davor aus dem
offenen Chat an diesen Anbieter. Das Modell prüft die Frage erst gegen den Rechtsrahmen
und antwortet dann. Feste Antworten (z. B. „Hallo“), Rechnen und Uhrzeit gehen nie an ein
Modell.</li>
</ul>
<h2>Cookie</h2>
<p>Ein Cookie merkt sich die Einstellungen der Oberfläche (Design, Sprache, Schalter).
Es liegt ein Jahr nur in deinem Browser. Du kannst es dort jederzeit löschen.</p>
<h2>Löschen</h2>
<p>Bei Aquaticy liegt nichts von dir, also gibt es nichts zu löschen. Für das Cookie:
Browserdaten dieser Seite löschen.</p>`,
  en: `<h2>In short</h2>
<ul>
<li>This version of Aquaticy has no accounts and no database. It doesn't store your
questions or answers.</li>
<li>The chat only lives in the open page. If you reload it, it's gone.</li>
<li>No ads, no tracking.</li>
</ul>
<h2>What goes where</h2>
<ul>
<li><strong>Cloudflare</strong> runs the server. Cloudflare processes your IP address and
technical connection details, under its own rules.</li>
<li><strong>Approximate location:</strong> Cloudflare estimates a city from your connection.
Aquaticy only uses it when you ask about the weather without naming a place. It isn't
stored.</li>
<li><strong>Looking things up:</strong> depending on the question, only the search term goes
to one of these services: Wikipedia (topic), Open-Meteo (place name), tagesschau.de (topic),
frankfurter.dev (currencies), date.nager.at (year and country), DuckDuckGo (topic), MyMemory
(the text you ask to translate). If you paste an address, Aquaticy fetches that page and
checks its name with Cloudflare DNS.</li>
<li><strong>Follow-up questions:</strong> so that “How old is he?” works, the page sends up to
ten messages of the open chat along. Aquaticy uses them only for this answer and doesn't
store them.</li>
<li><strong>AI model:</strong> if the operator has added a key for Mistral AI (EU) or NVIDIA
(USA), your question and up to ten earlier messages from the open chat go to that provider.
The model first checks the question against the legal rules, then answers. Fixed answers
(such as “Hello”), maths and the time never go to a model.</li>
</ul>
<h2>Cookie</h2>
<p>A cookie remembers the interface settings (design, language, switches). It stays in your
browser only, for one year. You can delete it there at any time.</p>
<h2>Deleting</h2>
<p>Aquaticy holds nothing about you, so there's nothing to delete. For the cookie: clear this
site's data in your browser.</p>`,
};

const COOKIES = {
  de: `<p>Es gibt genau ein Cookie: <code>aquaticy_ui</code>. Es speichert die Einstellungen der
Oberfläche (Design, Sprache, Schalter) für ein Jahr, nur in deinem Browser. Es ist nötig,
damit die Seite so aussieht, wie du sie eingestellt hast. Kein Tracking, keine Werbung.</p>`,
  en: `<p>There is exactly one cookie: <code>aquaticy_ui</code>. It stores the interface
settings (design, language, switches) for one year, only in your browser. It's needed so the
page looks the way you set it up. No tracking, no ads.</p>`,
};

const NUTZUNG = {
  de: `<ul>
<li>Aquaticy kann sich irren. Prüf wichtige Antworten, vor allem bei Gesundheit, Geld und
Recht. Aquaticy ersetzt keine Beratung.</li>
<li>Nutze Aquaticy nicht, um anderen zu schaden. Mit KI-Modell prüft Aquaticy jede Frage
gegen Grundgesetz und BGB und lehnt ab, was dagegen verstößt.</li>
<li>Texte aus Wikipedia stehen unter CC BY-SA 4.0, Wetterdaten von Open-Meteo unter
CC BY 4.0. Die Meldungen der Tagesschau sind nur für den privaten Gebrauch.</li>
</ul>`,
  en: `<ul>
<li>Aquaticy can be wrong. Check important answers, especially about health, money and law.
Aquaticy doesn't replace professional advice.</li>
<li>Don't use Aquaticy to harm others. With an AI model, Aquaticy checks every question
against German law and declines what breaks it.</li>
<li>Wikipedia texts are under CC BY-SA 4.0, Open-Meteo weather data under CC BY 4.0.
Tagesschau news is for private use only.</li>
</ul>`,
};

const BARRIEREFREIHEIT = {
  de: `<p>Die Oberfläche lässt sich mit Tastatur und Bildschirmleser bedienen. Schriftgröße,
helles oder dunkles Design und die Sprache stellst du unter Einstellungen ein. Wenn etwas
nicht geht, melde es bitte im Repository auf GitHub.</p>`,
  en: `<p>The interface works with a keyboard and screen readers. You can set the font size,
light or dark design and the language under Settings. If something doesn't work, please
report it in the repository on GitHub.</p>`,
};

function seite(texte, titel) {
  return (sprache, fassung) => RAHMEN(sprache, titel[sprache], texte[sprache], fassung);
}

export const RECHTLICHES = {
  "/privacy": seite(DATENSCHUTZ, { de: "Datenschutz", en: "Privacy" }),
  "/datenschutz": seite(DATENSCHUTZ, { de: "Datenschutz", en: "Privacy" }),
  "/cookies": seite(COOKIES, { de: "Cookies", en: "Cookies" }),
  "/terms": seite(NUTZUNG, { de: "Nutzungsbedingungen", en: "Terms of use" }),
  "/accessibility": seite(BARRIEREFREIHEIT, { de: "Barrierefreiheit", en: "Accessibility" }),
};
