"""Routervorschlag, bestaetigter Start und ehrliche Secure-Pro-Ergebnisse."""

import ipaddress

from tests.test_v1300_luna import _anlegen, _zustimmung, server  # noqa: F401
from tests.test_v1401 import owner  # noqa: F401


def route_line(interface, destination, gateway, mask, metric=100):
    def hex_ip(value):
        return ipaddress.IPv4Address(value).packed[::-1].hex()

    return (f"{interface}\t{hex_ip(destination)}\t{hex_ip(gateway)}\t0003\t0\t0\t"
            f"{metric}\t{hex_ip(mask)}\t0\t0\t0")


def routes(prefix="255.255.255.0"):
    return "Iface Destination Gateway Flags RefCnt Use Metric Mask\n" + "\n".join([
        route_line("eth0", "0.0.0.0", "192.168.1.1", "0.0.0.0"),
        route_line("eth0", "192.168.1.0", "0.0.0.0", prefix),
    ])


# 16.0.1 (Aquaticy-Test): 15 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


