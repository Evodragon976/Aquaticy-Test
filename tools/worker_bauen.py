"""Erzeugt worker/src/erzeugt.js aus dem Python-Paket -- eine Quelle fuer beide Fassungen.

Der Cloudflare-Worker (worker/) laeuft ohne Python. Was er mit der App teilen muss --
Fassung, Grundeinstellungen der Oberflaeche, Begruessungen und Vorschlaege, die festen
Antworten aus smalltalk.py und der Rechtsrahmen aus guardrails.py --, kommt deshalb
von hier und wird nicht von Hand abgeschrieben.

Aufruf:
    python tools/worker_bauen.py            # Datei neu schreiben
    python tools/worker_bauen.py --pruefen  # Rueckgabe 1, wenn die Datei veraltet ist
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

ZIEL = WURZEL / "worker" / "src" / "erzeugt.js"

#: Platzhalter fuer die Frage in der Pruefer-Vorlage.
FRAGE = "\u0000FRAGE\u0000"
#: Platzhalter fuer den Gespraechsverlauf davor.
VERLAUF = "\u0000VERLAUF\u0000"


def _erlaubt(werte: Any) -> Any:
    """Die erlaubten Werte eines Feldes der Oberflaeche, als JSON."""
    if werte is bool:
        return "bool"
    if werte is dict:
        return "design"
    if isinstance(werte, range):
        return {"von": werte.start, "bis": werte.stop - 1}
    return list(werte)


def daten() -> dict[str, Any]:
    from aquaticy import __version__, addons, guardrails, smalltalk, uistate, webview
    from aquaticy.web import VERSION_LABEL

    vor, _, nach = guardrails.judge_prompt(FRAGE).partition(FRAGE)
    vor_verlauf, _, nach_verlauf = guardrails.judge_prompt(
        FRAGE, context=VERLAUF).partition(FRAGE)
    regeln = {
        regel.id: {"titel": regel.title, "basis": regel.basis, "text": regel.text,
                   "statt": regel.instead}
        for regel in guardrails.RULES
    }
    allgemein = guardrails.GENERIC
    return {
        "version": __version__,
        "version_label": VERSION_LABEL,
        "zustand": uistate.defaults(),
        "felder": {name: _erlaubt(werte) for name, (_, werte) in uistate.FIELDS.items()},
        "design_schluessel": list(uistate.DESIGN_KEYS),
        "texte": webview.start_texts(),
        "smalltalk": [
            {"name": art.name, "muster": art.muster.pattern, "antworten": list(art.antworten),
             "nicht_bei_offener_frage": art.nicht_bei_offener_frage}
            for art in smalltalk.ARTEN
        ],
        "anrede": smalltalk._ANREDE.pattern,
        "wetterlage": {str(code): text for code, text in addons.WMO.items()},
        "quellen": {
            "geo": addons.OPEN_METEO_GEO, "wetter": addons.OPEN_METEO,
            "tagesschau": addons.TAGESSCHAU, "kurse": addons.FRANKFURTER,
            "feiertage": addons.NAGER, "wikipedia": addons.WIKIPEDIA,
        },
        "pruefer": {
            "vor": vor,
            "nach": nach,
            "vor_mit_verlauf": vor_verlauf,
            "nach_mit_verlauf": nach_verlauf,
            "zeichen": guardrails.JUDGE_CHARS,
            "regeln_kurz": guardrails.rules_prompt(),
            "regeln": regeln,
            "allgemein": {"titel": allgemein.title, "basis": allgemein.basis,
                          "text": allgemein.text, "statt": allgemein.instead},
            "absage_en": guardrails.ENGLISH_REFUSAL,
            "nicht_erreichbar": guardrails.UNAVAILABLE,
        },
    }


def inhalt() -> str:
    roh = json.dumps(daten(), ensure_ascii=False, indent=1, sort_keys=True)
    return (
        "// Erzeugt von tools/worker_bauen.py -- nicht von Hand aendern.\n"
        "// Neu erzeugen: python tools/worker_bauen.py\n"
        f"export const DATEN = {roh};\n"
    )


def main(argv: list[str]) -> int:
    neu = inhalt()
    if "--pruefen" in argv:
        alt = ZIEL.read_text(encoding="utf-8") if ZIEL.exists() else ""
        if alt != neu:
            print("worker/src/erzeugt.js ist veraltet: python tools/worker_bauen.py")
            return 1
        print("worker/src/erzeugt.js ist aktuell")
        return 0
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(neu, encoding="utf-8")
    print(f"geschrieben: {ZIEL.relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
