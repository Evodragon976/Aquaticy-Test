"""11.3.2 Terra: Tailscale-Ziele, MagicDNS und echte IPv6-Webverbindungen."""

from __future__ import annotations

import http.client
import socket
import threading
from contextlib import closing
from http.server import BaseHTTPRequestHandler

import pytest

from aquaticy import web


def _ipv6_da() -> bool:
    """Kann dieser Rechner ueberhaupt auf ::1 lauschen? (11.3.2 Sol)

    Manche Container und Dienste haben IPv6 ganz abgeschaltet; dort scheitert
    schon das Anlegen des Sockets ("Address family not supported"). Das ist
    eine Bedingung der Umgebung wie Chromium fuer den Rundgang, kein Fehler.
    """
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
            probe.bind(("::1", 0))
        return True
    except OSError:
        return False


IPV6 = _ipv6_da()
OHNE_IPV6 = "Dieser Rechner hat kein IPv6 (::1 laesst sich nicht binden)."


def _dns(addresses):
    return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM,
             socket.IPPROTO_TCP, "", (ip, 0, 0, 0) if ":" in ip else (ip, 0))
            for ip in addresses]


@pytest.mark.parametrize("address", ["100.81.120.999", "100.81.x.y", "100.81.-1.2",
                                   "100.81.1.2.evil", "100.81.1", "100.081.1.2"])
def test_tailscale_detection_rejects_malformed_addresses(address):
    assert not web.is_tailscale(address)


# 16.0.1 (Aquaticy-Test): 11 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


@pytest.mark.skipif(not IPV6, reason=OHNE_IPV6)
def test_ipv6_bind_and_http_request_use_the_same_address_family(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Aquaticy IPv6")

        def log_message(self, *args):
            pass

    monkeypatch.setattr(web, "Handler", Handler)
    server = web.bind_server("::1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert server.address_family == socket.AF_INET6
        with closing(http.client.HTTPConnection("::1", server.server_address[1], timeout=5)) \
                as conn:
            conn.request("GET", "/")
            response = conn.getresponse()
            assert response.status == 200 and response.read() == b"Aquaticy IPv6"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_bound_urls_are_valid_and_do_not_advertise_unbound_interfaces():
    assert web.urls_for("::1", 8765) == ["http://[::1]:8765/"]
    assert web.urls_for("fd7a:115c:a1e0::1", 8765) == [
        "http://[fd7a:115c:a1e0::1]:8765/",
    ]
    assert web.urls_for("::", 8765)[-1] == "http://[::1]:8765/"
    assert web.urls_for("100.81.120.100", 8765) == ["http://100.81.120.100:8765/"]


