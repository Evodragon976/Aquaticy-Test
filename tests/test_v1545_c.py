"""15.4.5: Gegenproben fuer getrennte Kontexte und widerrufene Speicherfreigaben."""


import pytest

from aquaticy import memory_auto, news
from aquaticy.memory import Memory

# 16.0.1 (Aquaticy-Test): 8 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f017_an_extreme_feed_date_does_not_break_other_headlines():
    def reader(feeds, **kwargs):
        return {'eintraege': [
            {'titel': 'Invalid date', 'link': 'https://example.org/a',
             'datum': 'Fri, 31 Dec 9999 23:59:59 -2359'},
            {'titel': 'Normal article', 'link': 'https://example.org/b',
             'datum': 'Sat, 07 Nov 2026 12:00:00 +0000'},
        ]}

    result = news.headlines(reader=reader)
    assert any(item.title == 'Normal article' for item in result)


def test_f022_news_deduplication_keeps_distinct_programming_language_titles():
    def reader(feeds, **kwargs):
        return {'eintraege': [
            {'titel': 'C++ 26 released', 'link': 'https://example.org/cpp'},
            {'titel': 'C# 26 released', 'link': 'https://example.org/csharp'},
        ]}

    result = news.headlines(reader=reader)
    assert {item.title for item in result} == {'C++ 26 released', 'C# 26 released'}


@pytest.mark.parametrize('fence', ['```', '~~~'])
def test_f028_unclosed_code_fences_do_not_teach_personal_memories(fence):
    assert memory_auto.extract(fence + 'text\nIch heiße Mallory.') == []


@pytest.mark.parametrize(('message', 'fact', 'topic'), [
    ('Vergiss meinen Namen.', 'Der Nutzer heißt Lisa.', 'person:name'),
    ('Vergiss meinen Wohnort.', 'Wohnt in Bremen.', 'person:wohnort'),
    ('Forget my name.', 'Der Nutzer heißt Lisa.', 'person:name'),
])
def test_f029_named_personal_fields_can_be_forgotten(settings, message, fact, topic):
    memory = Memory(settings.db_path, settings.data_dir, settings.memory_key)
    memory.remember(fact, topic)
    request = memory_auto.forget_request(message)
    assert request and memory_auto.forget_matching(memory, request) == [fact]
    assert memory.count() == 0


def test_f031_quoted_forget_requests_do_not_erase_personal_facts(settings):
    memory = Memory(settings.db_path, settings.data_dir, settings.memory_key)
    memory_auto.store_facts(memory, memory_auto.extract('Ich mag Jazz.'))
    quoted = 'Erkläre den Satz: „Vergiss, dass ich Jazz mag.“'
    request = memory_auto.forget_request(quoted)
    if request:
        memory_auto.forget_matching(memory, request)
    assert memory.count() == 1


def test_f032_short_personal_names_can_be_forgotten(settings):
    memory = Memory(settings.db_path, settings.data_dir, settings.memory_key)
    memory_auto.store_facts(memory, memory_auto.extract('Ich heiße Li.'))
    assert memory_auto.forget_matching(memory, 'Li')
    assert memory.count() == 0


def test_personal_topic_classification_is_consistently_case_insensitive(settings):
    memory = Memory(settings.db_path, settings.data_dir, settings.memory_key)
    memory.remember('Der Nutzer heißt Lisa.', 'Person:name')
    assert [entry.text for entry in memory_auto.person_entries(memory)] == [
        'Der Nutzer heißt Lisa.']


