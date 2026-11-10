"""16.0.0 (Aquaticy-Test): Aquaticy Standard antwortet ohne Sprachmodell -- ohne Netz getestet."""

from __future__ import annotations

import datetime
import random
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from aquaticy import standard
from aquaticy.config import STANDARD_MODEL_ID, Settings, model_problem

JETZT = datetime.datetime(2026, 11, 9, 17, 30, tzinfo=ZoneInfo("Europe/Berlin"))


def holen(url: str) -> Any:
    if "geocoding" in url:
        ort = "Bremen" if "Bremen" in url else "Berlin"
        return {"results": [{"name": ort, "latitude": 52.5, "longitude": 13.4}]}
    if "forecast" in url:
        return {"daily": {"weather_code": [61, 0, 3], "temperature_2m_max": [9.4, 11, 8],
                          "temperature_2m_min": [3.1, 4, 2],
                          "precipitation_probability_max": [70, 10, 20]},
                "current": {"temperature_2m": 7.2}}
    if "frankfurter" in url:
        return {"date": "2026-11-09", "rates": {"USD": 1.0823}}
    if "tagesschau" in url:
        return {"news": [{"title": "Meldung A", "shareURL": "https://www.tagesschau.de/a"},
                         {"title": "Meldung [B]"}]}
    if "opensearch" in url:
        return ["Eiffelturm", ["Eiffelturm"], [""], [""]]
    if "summary" in url:
        return {"title": "Eiffelturm", "extract": "Der Eiffelturm ist 330 Meter hoch. Er steht "
                "in Paris. Er wurde 1889 gebaut. Noch ein Satz.",
                "content_urls": {"desktop": {"page": "https://de.wikipedia.org/wiki/Eiffelturm"}}}
    return None


def frag(text: str, **kwargs: Any) -> str:
    kwargs.setdefault("holen", holen)
    return standard.antwort(text, jetzt=JETZT, wuerfel=random.Random(1), **kwargs)


@pytest.mark.parametrize(("frage", "teil"), [
    ("Was ist 12 * (3 + 4)?", "**84**"),
    ("Wie viel ist 2 hoch 10", "**1.024**"),
    ("19 % von 250", "**47,5**"),
    ("200 plus 19 %", "**238**"),
    ("119 € brutto in netto", "**100 € netto**"),
    ("5 km in Meilen", "**3,1069 Meilen**"),
    ("100 Fahrenheit in Celsius", "**37,78 °C**"),
    ("3 GB in MB", "**3.000 MB**"),
    ("Wie spät ist es?", "**17:30 Uhr**"),
    ("Welcher Tag ist heute?", "Montag, der 09.11.2026"),
    ("Wie viele Tage bis Weihnachten?", "**45 Tage**"),
    ("Welcher Wochentag ist der 3.10.2027?", "**Sonntag**"),
    ("Wann ist Ostern?", "28.03.2027"),
    ("Wetter in Berlin", "**Heute in Berlin:**"),
    ("Wird es morgen in Berlin regnen?", "**Morgen in Berlin:**"),
    ("100 Euro in Dollar", "**108,23 USD**"),
    ("Nachrichten", "[Meldung A](https://www.tagesschau.de/a)"),
    ("Was ist der Eiffelturm?", "Quelle: [Wikipedia](https://de.wikipedia.org/wiki/Eiffelturm)"),
    ("Würfel", "🎲"),
    ("Soll ich Pizza oder Pasta essen?", "**P"),
])
def test_answers_without_a_language_model(frage: str, teil: str) -> None:
    assert teil in frag(frage)


def test_sources_are_named() -> None:
    assert "Quelle: [Open-Meteo]" in frag("Wetter in Berlin")
    assert "Europäische Zentralbank" in frag("100 Euro in Dollar")


def test_follow_up_weather_question() -> None:
    vorher = [{"role": "assistant", "content": "**Heute in Berlin:** klar"}]
    assert "**Morgen in Berlin:**" in frag("und morgen?", verlauf=vorher)


def test_unknown_questions_are_honest_and_point_to_keys() -> None:
    antwort = frag("Wie geht es dem Universum?")
    # 16.0.2: menschlicher formuliert -- ehrlich bleibt es, und der Weg zu den Schluesseln auch.
    assert "ohne Sprachmodell" in antwort and "Add-ons" in antwort
    assert "Was kannst du?" in antwort


def test_weather_without_a_place_uses_the_home_town() -> None:
    assert "**Heute in Bremen:**" in frag("Wie wird das Wetter?", wohnort="Bremen")
    assert standard.ORT_FRAGE in frag("Wie wird das Wetter?")


def test_it_confirms_what_it_remembered() -> None:
    antwort = frag("Ich wohne in Bremen.", gemerkt=["Wohnt in Bremen."])
    assert "merke ich mir" in antwort and "Wohnt in Bremen." in antwort


def test_secure_pro_answers_from_fixed_knowledge() -> None:
    assert "RDP" in frag("Was ist Port 3389?", secure=True)
    assert "Phishing" in frag("Wie erkenne ich Phishing?", secure=True)


def test_only_fixed_public_hosts_are_fetched() -> None:
    assert standard.holen_json("https://example.com/x") is None
    assert standard.holen_json("http://de.wikipedia.org/x") is None
    assert standard.holen_json("https://169.254.169.254/latest") is None


def test_the_model_is_known_and_usable() -> None:
    from aquaticy.system import model_usable

    assert STANDARD_MODEL_ID == standard.MODEL_ID == "aquaticy/standard"
    assert model_problem(STANDARD_MODEL_ID) == ""
    assert model_usable(Settings(), STANDARD_MODEL_ID)


def test_the_agent_answers_with_standard_and_never_calls_litellm(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy.agent import Agent
    from aquaticy.cache import Cache

    monkeypatch.setattr(standard, "holen_json", holen)

    def nie(**_kw: Any) -> None:
        raise AssertionError("LiteLLM darf nicht gerufen werden")

    monkeypatch.setattr("litellm.completion", nie)
    settings = Settings(model=STANDARD_MODEL_ID, data_dir=tmp_path / "d", memory_enabled=True,
                        enable_playwright=False, subagents_auto=False,
                        request_delay_seconds=0.0)
    agent = Agent(settings, cache=Cache(settings.db_path))
    assert agent.ask("Was ist 2 + 3?", stream=False).answer == "**5**"
    assert "merke ich mir" in agent.ask("Ich wohne in Bremen.", stream=False).answer
    assert "**Heute in Bremen:**" in agent.ask("Wie wird das Wetter?", stream=False).answer
    agent.ask("Ich heiße Louis.", stream=False)
    assert agent.ask("Wie heiße ich?", stream=False).answer == "Du heißt Louis."


def test_the_header_offers_keys_while_only_standard_is_there() -> None:
    from aquaticy import web

    kopf = web.header_for(Settings(model=STANDARD_MODEL_ID))
    assert kopf["model_label"] == "Aquaticy Standard" and kopf["key_hint"] is True
    eigene = Settings(model=STANDARD_MODEL_ID)
    eigene.own_key_names = frozenset({"MISTRAL_API_KEY"})
    assert web.header_for(eigene)["key_hint"] is False


def test_the_ui_shows_the_key_hint_with_the_way_to_the_add_ons() -> None:
    from aquaticy import web

    html = web.UI_FILE.read_text(encoding="utf-8")
    assert 'id="key-banner"' in html and 'id="key-banner-open"' in html
    assert "schluesselHinweis(kopf.key_hint === true);" in html
    teil = html[html.index('$("#key-banner-open")'):]
    assert "addonsOeffnen();" in teil[:200]
    assert '"/api/key-hint"' in html and "localStorage" not in html


def test_the_key_hint_comes_on_the_first_start_and_every_fifth_per_account(
        tmp_path: Path) -> None:
    from aquaticy import web

    konto_a, konto_b = tmp_path / "a", tmp_path / "b"
    assert [web.key_hint_due(konto_a) for _ in range(11)] == [
        True, False, False, False, False, True, False, False, False, False, True]
    assert web.key_hint_due(konto_b) is True


# -- 16.0.2: Gespraechsspeicher und neue Antworten ---------------------------------------------

def gespraech(*fragen: str) -> list[str]:
    verlauf: list[dict[str, Any]] = []
    antworten = []
    for text in fragen:
        antwort = frag(text, verlauf=verlauf)
        verlauf += [{"role": "user", "content": text}, {"role": "assistant", "content": antwort}]
        antworten.append(antwort)
    return antworten


def test_the_place_after_the_question_answers_the_open_question() -> None:
    """Der Fehler aus 16.0.1: nach "Fuer welchen Ort?" kam bei "Erkelenz" nur "Kann ich nicht"."""
    frage, ort = gespraech("wie wird das wetter heute", "Erkelenz")
    assert standard.ORT_FRAGE in frage
    assert "**Heute in Bremen:**" not in ort and "Heute in" in ort
    assert "ohne Sprachmodell" not in ort


def test_the_last_place_counts_for_the_next_questions() -> None:
    antworten = gespraech("Wetter in Berlin", "was soll ich anziehen?", "und morgen?",
                          "brauche ich morgen einen Schirm?")
    assert "in **Berlin**" in antworten[1] and "zieh am besten" in antworten[1]
    assert "**Morgen in Berlin:**" in antworten[2]
    assert "Für morgen in **Berlin**" in antworten[3] and "Schirm" in antworten[3]


def test_clothing_advice_asks_for_the_place_first() -> None:
    frage, rat = gespraech("Was soll ich heute anziehen?", "in Bremen")
    assert standard.ORT_FRAGE in frage and "Anziehen" in frage
    assert "in **Bremen**" in rat and "zieh am besten" in rat


def test_a_normal_question_is_not_taken_for_a_place() -> None:
    _, rechnung = gespraech("Wie wird das Wetter?", "Was ist 2 + 3?")
    assert rechnung == "**5**"


@pytest.mark.parametrize(("frage", "teil"), [
    ("Wann geht die Sonne unter in Berlin?", "Sonne"),
    ("Wie wird das Wetter die nächsten Tage in Berlin?", "Die nächsten Tage in Berlin"),
    ("Wann ist der nächste Feiertag?", "1. Weihnachtstag"),
    ("Wann ist Pfingstmontag?", "Pfingstmontag"),
    ("Ist heute Vollmond?", "Vollmond"),
    ("Ich bin am 3.5.1990 geboren. Wie alt bin ich?", "**36 Jahre**"),
    ("15 % Trinkgeld auf 42 Euro", "**6,30 €**"),
    ("BMI 80 kg 1,80 m", "**24,7**"),
    ("Mir ist langweilig", "Ideen"),
    ("Erzähl mir einen Fun Fact", "Wusstest du schon?"),
    ("Was kannst du?", "ohne Sprachmodell"),
])
def test_new_answers(frage: str, teil: str) -> None:
    assert teil in frag(frage)


def test_a_password_is_random_long_and_mixed() -> None:
    import re

    antwort = frag("Generiere ein Passwort mit 16 Zeichen")
    wort = re.search(r"`([^`]+)`", antwort)
    assert wort and len(wort[1]) == 16
    assert any(c.isupper() for c in wort[1]) and any(c.isdigit() for c in wort[1])
    assert frag("Generiere ein Passwort") != antwort


def test_the_time_in_another_city() -> None:
    def mit_zone(url: str) -> Any:
        if "geocoding" in url:
            return {"results": [{"name": "New York", "timezone": "America/New_York"}]}
        return holen(url)

    antwort = frag("Wie spät ist es in New York?", holen=mit_zone)
    assert "**11:30 Uhr**" in antwort and "6 Stunden weniger" in antwort


def test_the_weekend_forecast() -> None:
    def sieben_tage(url: str) -> Any:
        if "forecast" in url:
            return {"daily": {"weather_code": [61, 0, 3, 1, 2, 0, 63],
                              "temperature_2m_max": [9, 11, 8, 10, 12, 14, 7],
                              "temperature_2m_min": [3, 4, 2, 3, 5, 6, 2],
                              "precipitation_probability_max": [70, 10, 20, 5, 10, 0, 80]}}
        return holen(url)

    antwort = frag("Wetter in Berlin am Wochenende", holen=sieben_tage)
    assert "**Das Wochenende in Berlin:**" in antwort
    assert "**Sa 14.11.:**" in antwort and "**So 15.11.:**" in antwort
    assert "Am schönsten wird es wohl" in antwort


def test_a_new_home_town_wins_over_the_last_place() -> None:
    verlauf = [{"role": "user", "content": "Wetter in Berlin"},
               {"role": "assistant", "content": frag("Wetter in Berlin")},
               {"role": "user", "content": "Ich wohne in Bremen."},
               {"role": "assistant", "content": "Alles klar, das merke ich mir."}]
    assert "in Bremen:**" in frag("Wie wird das Wetter morgen?", verlauf=verlauf, wohnort="Bremen")
