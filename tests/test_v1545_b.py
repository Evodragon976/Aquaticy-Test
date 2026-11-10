"""15.4.5: Gegenproben fuer externe Antworten, Geheimnisse und Zeitplaene."""


import httpx
import pytest

from aquaticy import extract, github_repo, google, voice


@pytest.mark.parametrize('payload', [{}, {'error': {'message': 'Not accepted'}}])
def test_f010_google_writes_need_a_confirmed_resource_id(tmp_path, monkeypatch, payload):
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)))
    api = google.Google('id', 'secret', google.TokenStore(tmp_path), client)
    monkeypatch.setattr(api, '_access', lambda: 'test-token')
    try:
        with pytest.raises(google.GoogleError):
            api.create_event('Meeting', '2026-11-08T10:00:00+00:00')
    finally:
        api.close()


# 16.0.1 (Aquaticy-Test): 6 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


@pytest.mark.parametrize(('text', 'expected'), [
    ('Antworte nicht nur als Text, sondern auch als Sprachnachricht.', True),
    ('Eine Sprachnachricht bitte nicht. Antworte als Text.', False),
    ('Erkläre den Satz „Antworte als Sprachnachricht“.', False),
])
def test_f012_voice_output_requires_the_actual_current_request(text, expected):
    assert voice.requested(text) is expected


def test_f014_private_key_fragments_in_diff_hunks_remain_masked():
    fragment = 'MIIEpAIBAAKCAQEAq5Dx7Tn8Vb3Lu6Hw9Sz2Pr4Ey0Ca1Fk5Nm7Jt8Gv6Rb9Qs2Z'
    patch = '@@ -12,1 +12,1 @@\n+' + fragment + '\n'
    assert fragment not in github_repo.redact(patch)


# 16.0.2 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (Gemeinsames Lernen, Recherchecache, Webcams und Satellitenbilder,
# Einstellungen unter Helfer & Grenzen).


@pytest.mark.parametrize(('text', 'expected'), [('-12.50 EUR', '-12.50'), ('1e3', '1000')])
def test_f020_prices_do_not_lose_a_sign_or_exponent(text, expected):
    assert extract.parse_price(text)[0] == expected


@pytest.mark.parametrize(('text', 'currency'), [('CA$ 12.50', 'CAD'), ('AU$ 12.50', 'AUD')])
def test_f021_prefixed_dollar_prices_keep_the_actual_currency(text, currency):
    assert extract.parse_price(text)[1] == currency
