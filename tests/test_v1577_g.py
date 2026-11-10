"""15.7.7: Robots-Regeln, Sicherheitsberichte und Prozessidentitaet."""

import os
import subprocess
import sys

import httpx
import pytest

from aquaticy import cli, fetch, old_server


def test_f059_untrusted_robots_wildcards_cannot_trigger_exponential_matching():
    code = ('from aquaticy.fetch import RobotsRules\n'
            'rules=RobotsRules([(False, "/" + "*a" * 18 + "b")])\n'
            'assert rules.allows("https://example.org/" + "a" * 70)\n')
    subprocess.run([sys.executable, '-c', code], check=True, timeout=3,
                   capture_output=True)


def test_f060_wildcard_characters_do_not_make_a_robots_rule_more_specific():
    rules = fetch.RobotsRules([(False, '/private'), (True, '/' + '*' * 20)])
    assert not rules.allows('https://example.org/private/document')
    assert rules.allows('https://example.org/public/document')


def test_f061_only_the_most_specific_robot_agent_group_applies():
    rules = fetch.RobotsRules.parse('User-agent: aqua\nDisallow: /private\n\n'
                                    'User-agent: aquaticy\nAllow: /\n', 'aquaticy/15')
    assert rules.allows('https://example.org/private')


def test_f062_an_unresolved_robots_redirect_is_not_treated_as_permission(monkeypatch):
    monkeypatch.setattr(fetch.netguard, 'get', lambda *a, **kw: httpx.Response(302))
    with httpx.Client() as client:
        policy = fetch.RobotsPolicy(client, 'aquaticy/15')
        assert policy.check('https://example.org/private') == 'robots_unavailable'


# 16.0.1 (Aquaticy-Test): 2 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f065_the_default_terminal_chat_is_not_misidentified_as_a_web_server(monkeypatch):
    started = []
    monkeypatch.setattr(sys, 'argv', ['aquaticy'])
    monkeypatch.setattr(cli, 'app', lambda: started.append(tuple(sys.argv)))
    monkeypatch.setattr('aquaticy.startup.update_at_start', lambda console: False)
    cli.main()
    assert started == [('aquaticy', 'chat')]
    assert old_server._ist_server(['aquaticy']) is False
    assert old_server._ist_server([sys.executable, '-m', 'aquaticy.cli']) is False


@pytest.mark.skipif(not hasattr(os, 'pidfd_open'), reason='Linux-pidfd erforderlich')
def test_f066_waiting_for_a_stopped_process_uses_the_pinned_identity(monkeypatch):
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    monkeypatch.setattr(old_server, 'is_aquaticy', lambda pid: pid == process.pid)
    monkeypatch.setattr(old_server, '_exited', lambda pid: False)
    try:
        assert old_server.stop(process.pid, wait=0.5)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
