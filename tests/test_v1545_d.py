"""15.4.5: Proxy-Vertrauen, TCP-Dienstpruefung und sichere Aktionsparameter."""

import ipaddress
from email.message import Message

import pytest

from aquaticy import metering, web


def test_f033_proxy_chains_resolve_the_client_beyond_trusted_intermediate_proxies(monkeypatch):
    monkeypatch.setattr(web, 'trusted_proxies', lambda: [
        ipaddress.ip_network('10.0.0.0/8'), ipaddress.ip_network('192.168.0.0/16')])
    assert web.client_ip('10.0.0.2', '198.51.100.7, 192.168.1.3') == '198.51.100.7'


def test_f036_ipv4_mapped_proxy_peers_keep_their_explicit_trust(monkeypatch):
    monkeypatch.setattr(web, 'trusted_proxies', lambda: [ipaddress.ip_network('127.0.0.0/8')])
    assert web.client_ip('::ffff:127.0.0.1', '198.51.100.7') == '198.51.100.7'
    handler = object.__new__(web.Handler)
    handler.connection = object()
    handler.client_address = ('::ffff:127.0.0.1', 12345)
    handler.headers = Message()
    handler.headers['X-Forwarded-Proto'] = 'https'
    assert handler._https() is True


def test_f037_an_invalid_nearest_forwarded_hop_does_not_expose_an_attacker_prefix(monkeypatch):
    monkeypatch.setattr(web, 'trusted_proxies', lambda: [ipaddress.ip_network('127.0.0.0/8')])
    assert web.client_ip('127.0.0.1', '8.8.8.8, malformed') == '127.0.0.1'


class _Socket:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def settimeout(self, *args):
        pass

    def sendall(self, *args):
        pass

    def recv(self, limit):
        return self.chunks.pop(0) if self.chunks else b''


# 16.0.1 (Aquaticy-Test): 3 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


@pytest.mark.parametrize('usage', [
    {'prompt_tokens': True, 'completion_tokens': 2},
    {'prompt_tokens': 10, 'completion_tokens': False},
])
def test_f041_boolean_usage_fields_fall_back_to_accounting_instead_of_one_token(usage):
    assert metering.usage_of(usage) is None
