"""15.2.4: nachgestellte Fehler F021 bis F040."""

from types import SimpleNamespace

import pytest
from rich.console import Console
from selectolax.parser import HTMLParser

from aquaticy import addons, cli, extract, local_model, secure_chat
from aquaticy.agent import AgentResult
from aquaticy.config import Settings


class Worker:
    def __init__(self, error=''):
        self.error = error
        self.closed = False
        self.toolbox = SimpleNamespace(untrusted_seen=False)

    def ask(self, *a, **kw):
        return AgentResult(error=self.error, answer='')

    def close(self):
        self.closed = True


# 16.0.1 (Aquaticy-Test): 8 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f029_configured_local_vision_models_also_start_ollama(monkeypatch):
    settings = Settings(model='mistral/mistral-large-latest', vision_model='ollama_chat/qwen3:8b')
    started = []
    monkeypatch.setattr(local_model, 'server_running', lambda *a, **kw: False)
    monkeypatch.setattr(local_model, 'ollama_binary', lambda: 'ollama')
    monkeypatch.setattr(local_model, 'start_server', lambda *a, **kw: started.append(a) or True)
    monkeypatch.setattr(local_model, 'installed_models', lambda *a: ['qwen3:8b'])
    cli._ollama_beim_start(settings)
    assert started


def test_f030_changing_search_language_does_not_replace_the_country_with_a_language_code():
    settings = Settings(country='at', lang='de')
    cli._apply_overrides(settings, '', 'en', '', '', 0)
    assert settings.lang == 'en' and settings.country == 'at'


def test_f031_terminal_commands_accept_tabs_as_argument_separators(monkeypatch):
    locations = []
    agent = SimpleNamespace(set_location=locations.append)
    cli._handle_slash('/location\tBremen', agent, Settings(), [], None)
    assert locations == ['Bremen']


def test_f032_terminal_model_errors_are_printed_as_data(monkeypatch):
    console = Console(record=True, width=100)
    monkeypatch.setattr(cli, 'console', console)
    result = AgentResult(answer='', error='Model replied [/broken]')
    agent = SimpleNamespace(ask=lambda *a, **kw: result)
    renderer = SimpleNamespace(reset=lambda: None)
    assert cli._run_turn(agent, renderer, 'q', True, False) is result
    assert '[/broken]' in console.export_text()


@pytest.mark.parametrize('code', [float('nan'), float('inf'), 0.5])
def test_f033_invalid_weather_codes_do_not_report_clear_weather_or_crash(code):
    assert addons._wetterlage(code) == 'unbekannt'


def test_f034_private_home_arpa_names_never_enter_public_advisory_search():
    assert not secure_chat.public_query('router.home.arpa vulnerabilities')


def test_f035_rss_permalink_guids_are_used_when_the_link_is_missing():
    feed = b'<rss><channel><item><title>A</title><guid isPermaLink="true">' \
           b'https://example.org/story</guid></item></channel></rss>'
    assert addons.parse_feed(feed, 'https://example.org/feed')[0]['link'] \
        == 'https://example.org/story'


def test_f036_empty_feed_descriptions_do_not_hide_available_content():
    feed = b'<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item>' \
           b'<title>A</title><description> </description>' \
           b'<content:encoded>Body</content:encoded></item></channel></rss>'
    assert addons.parse_feed(feed, 'https://example.org/feed')[0]['zusammenfassung'] == 'Body'


def test_f037_atom_text_and_html_types_are_rendered_according_to_the_declared_type():
    feed = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry>' \
           b'<title type="html">&lt;b&gt;Headline&lt;/b&gt;</title>' \
           b'<summary type="text">Use &lt;vector&gt; in C++</summary></entry></feed>'
    result = addons.parse_feed(feed, 'https://example.org/feed')[0]
    assert result['titel'] == 'Headline'
    assert result['zusammenfassung'] == 'Use <vector> in C++'


def test_f038_feed_html_entities_are_decoded_for_readers():
    feed = b'<rss><channel><item><title>A</title><description><![CDATA[' \
           b'<p>One &amp; two</p>]]></description></item></channel></rss>'
    assert addons.parse_feed(feed, 'https://example.org/feed')[0]['zusammenfassung'] == 'One & two'


def test_f039_nested_microdata_brand_names_do_not_replace_product_names():
    tree = HTMLParser('<div itemscope itemtype="https://schema.org/Product">'
        '<div itemprop="brand" itemscope itemtype="https://schema.org/Brand">'
        '<span itemprop="name">Brand</span></div><span itemprop="name">Camera</span>'
        '<div itemprop="offers" itemscope itemtype="https://schema.org/Offer">'
        '<meta itemprop="price" content="10"></div></div>')
    product = extract.product_from_microdata(tree, 'https://example.org')
    assert product is not None and product.name == 'Camera' and product.price == '10'


def test_f040_named_jsonld_brands_use_the_name_instead_of_the_identifier_url():
    tree = HTMLParser('<script type="application/ld+json">{"@type":"Product","name":"Camera",'
        '"brand":{"@type":"Brand","@id":"https://example.org/brand","name":"Acme"}}'
        '</script>')
    product = extract.product_from_jsonld(tree, 'https://example.org')
    assert product is not None and product.specs['Marke'] == 'Acme'
