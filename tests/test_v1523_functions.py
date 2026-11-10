"""15.2.3: 25 weitere nachgestellte Funktionsfehler und ihre Gegenproben."""

import base64
import json
import shutil
import sqlite3
from contextlib import contextmanager

import httpx
import pytest
from selectolax.parser import HTMLParser

from aquaticy import (
    export,
    extract,
    google,
    local_model,
    news,
    places,
    queries,
    router,
    uistate,
    webview,
)
from aquaticy.models import Product, SearchResult
from tests.test_rundgang import _browser_da


def test_f01_fractional_agent_counts_are_not_silently_truncated():
    assert uistate.clean({"agents": 2.9}, base={"agents": 7})["agents"] == 7
    assert uistate.clean({"agents": True}, base={"agents": 7})["agents"] == 7


def test_f02_failed_setting_writes_do_not_claim_success(tmp_path, monkeypatch):
    state = uistate.UIState(tmp_path / "state.db")

    @contextmanager
    def broken():
        raise sqlite3.OperationalError("disk full")
        yield

    monkeypatch.setattr(state, "_connect", broken)
    with pytest.raises(OSError):
        state.write({"theme": "dark"})


def place_client(monkeypatch, payload):
    monkeypatch.setattr(places, "_warte", lambda: None)
    monkeypatch.setattr(places, "_client", lambda *a: httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))))


def test_f03_a_real_zero_coordinate_is_not_replaced_by_the_center(monkeypatch):
    monkeypatch.setattr(places, "geocode", lambda *a, **kw: (0, 0, "Place"))
    place_client(monkeypatch, {"elements": [{"lat": 0, "lon": 0,
        "center": {"lat": 50, "lon": 8}, "tags": {"name": "Origin"}}]})
    result, _ = places.find_places("cafe", "place", "test")
    assert (result[0].lat, result[0].lon) == (0, 0)


@pytest.mark.parametrize("latitude,longitude", [("nan", "1"), ("91", "8"), ("1", "181")])
def test_f04_invalid_geocoding_cannot_send_a_broken_map_query(monkeypatch, latitude, longitude):
    place_client(monkeypatch, [{"lat": latitude, "lon": longitude}])
    with pytest.raises(places.PlacesError):
        places.geocode("Bremen", "test")


def test_f05_the_explicit_bicycle_workshop_category_is_reachable():
    assert places._filter_for("Werkstatt Fahrrad") == 'nwr[shop=bicycle]'


def test_f06_duplicate_headlines_keep_the_newest_version(monkeypatch):
    monkeypatch.setattr(news, "feeds_for", lambda *a: ("old", "new"))
    def reader(feeds, **kwargs):
        newer = feeds == ["new"]
        return {"eintraege": [{"titel": "A headline", "link": "https://example.org/" + feeds[0],
            "datum": "2026-11-06T12:00:00Z" if newer else "2026-11-05T12:00:00Z"}]}
    assert news.headlines(reader=reader)[0].url == "https://example.org/new"


def test_f07_html_mail_keeps_line_breaks_and_paragraphs():
    payload = {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(
        b"<p>First<br>Second</p><p>Third</p>").decode()}}
    text = google._body_text(payload)
    assert text.splitlines() == ["First", "Second", "", "Third"]


def test_f08_end_only_calendar_patches_preserve_all_day_dates():
    assert google._end_time("2026-11-07", False) == {"date": "2026-11-07"}


@pytest.mark.skipif(not _browser_da(), reason="Playwright oder Browser fehlen")
def test_f09_export_cards_are_dark_in_dark_mode():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        executable = (shutil.which("chromium") or shutil.which("chromium-browser")
                      or "/opt/pw-browsers/chromium")
        browser = p.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        page = browser.new_page(color_scheme="dark")
        page.set_content(export.to_html([export.Turn(question="q", answer="a")]))
        assert page.locator('.turn').evaluate('el => getComputedStyle(el).backgroundColor') \
            == "rgb(32, 32, 36)"
        browser.close()


def test_f10_markdown_product_sources_have_a_visible_fallback_label():
    turn = export.Turn(question="q", answer="a", products=[
        Product(name="A", url="https://shop.example/p")])
    assert "[https://shop.example/p](https://shop.example/p)" in export.to_markdown([turn])


@pytest.mark.parametrize("text", ["Erkläre C++", "Schreib C# für mich"])
def test_f11_programming_languages_with_punctuation_select_the_code_route(text):
    assert router.kategorie(text) == "code"


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f14_invalid_sizes_do_not_crash_the_file_list():
    assert webview.size_text(float("inf")) == "0 B"


def test_f15_osm_named_places_are_kept_in_rural_addresses():
    assert places._address({"addr:place": "Dorf", "addr:housenumber": "4"}) == "Dorf 4"


def test_f16_whitespace_only_optional_calendar_ends_use_the_default_duration():
    assert google._times("2026-11-06", "  ", True)[1] == {"date": "2026-11-07"}


def test_f17_fully_qualified_schema_product_types_are_recognized():
    assert extract._is_product({"@type": "https://schema.org/Product"})


def test_f18_jsonld_list_items_expose_their_nested_product():
    data = {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "item": {
        "@type": "Product", "name": "Camera"}}]}
    tree = HTMLParser('<script type="application/ld+json">' + json.dumps(data) + '</script>')
    result = extract.product_from_jsonld(tree, "https://shop.example")
    assert result is not None and result.name == "Camera"


def test_f19_microdata_supports_space_separated_property_names():
    tree = HTMLParser('<div itemscope itemtype="https://schema.org/Product">'
        '<span itemprop="name alternateName">Camera</span></div>')
    assert extract.product_from_microdata(tree, "https://shop.example") is not None


def test_f20_duplicates_within_one_search_list_do_not_create_extra_votes():
    a = SearchResult(url="https://a.example", title="A")
    b = SearchResult(url="https://b.example", title="B")
    result = queries.fuse([[a, a, a, b], [b]], 2)
    assert result[0].title == "B"


def test_f21_fusing_searches_does_not_mutate_reusable_input_results():
    source = SearchResult(url="https://a.example", title="A", rank=8)
    result = queries.fuse([[source]], 1)
    assert result[0].rank == 1 and source.rank == 8 and source.source_domain == ""


def test_f23_explicit_currency_codes_override_an_ambiguous_dollar_symbol():
    assert extract.parse_price("CAD $12.50") == ("12.50", "CAD")


def test_f24_empty_plaintext_alternatives_do_not_hide_an_html_body():
    def part(mime, text):
        data = base64.urlsafe_b64encode(text.encode()).decode()
        return {"mimeType": mime, "body": {"data": data}}
    payload = {"parts": [part("text/plain", " \n "), part("text/html", "<p>Message</p>")]}
    assert google._body_text(payload) == "Message"


def test_f25_ollama_memory_ranking_accepts_the_default_latest_alias(monkeypatch):
    monkeypatch.setattr(local_model, '_tag_list', lambda base: [
        {"name": "qwen3:latest", "size": 7_000_000_000}])
    assert local_model.model_size_gb("qwen3") == 7


def test_duplicate_search_metadata_can_still_supply_a_better_snippet():
    short = SearchResult(url='https://a.example', title='A', snippet='short')
    detailed = SearchResult(url='https://a.example', title='A', snippet='a much longer snippet')
    assert queries.fuse([[short, detailed]], 1)[0].snippet == 'a much longer snippet'


def test_optional_null_coordinates_still_use_an_available_center(monkeypatch):
    monkeypatch.setattr(places, 'geocode', lambda *a, **kw: (50, 8, 'Place'))
    place_client(monkeypatch, {'elements': [{'lat': None, 'lon': None,
        'center': {'lat': 50, 'lon': 8}, 'tags': {'name': 'Cafe'}}]})
    result, _ = places.find_places('cafe', 'place', 'test')
    assert (result[0].lat, result[0].lon) == (50, 8)
