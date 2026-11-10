"""QR-Anmeldung: lokale Bilder, Kontogrenzen, Abbruch und echter Browserdialog."""

from __future__ import annotations

import io
import json
import subprocess
from typing import Any

import zxingcpp
from PIL import Image

from tests.test_v965 import parallel_site as parallel_site

CODES = {
    "signal": "sgnl://linkdevice?uuid=local-test&pub_key=example-public-key",
    "whatsapp": "2@test-key-with-random-text,public-key,identity-key,client-key",
}


def screenshot(messenger: str) -> bytes:
    code = zxingcpp.create_barcode(CODES[messenger], zxingcpp.BarcodeFormat.QRCode)
    qr = Image.fromarray(zxingcpp.write_barcode_to_image(code, scale=5))
    image = Image.new("RGB", (1280, 800), "red")
    image.paste(qr, (450, 200))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95)
    return out.getvalue()


# 16.0.1 (Aquaticy-Test): 4 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


class Box:
    alive = True
    user_mode = True
    active = "Signal Messenger"
    reads = 0
    messenger = "signal"
    klass = "signal.Signal"

    def desktop(self, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        data = {"fenster": [{"id": "0x123", "klasse": self.klass, "titel": "Signal Messenger"}],
                "aktiv": self.active, "aktiv_klasse": self.klass}
        return subprocess.CompletedProcess(args, 0, json.dumps(data).encode(), b"")

    def screenshot(self, **kwargs: Any) -> bytes:
        self.reads += 1
        return screenshot(self.messenger)


# 16.0.0 (Aquaticy-Test): test_qr_session_is_tied_to_the_owner_and_can_be_cancelled entfaellt.
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


# 16.0.0 (Aquaticy-Test): test_invalid_or_busy_sessions_never_read_a_frame entfaellt.
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


# 16.0.0 (Aquaticy-Test): test_other_window_and_changed_foreground_cannot_leak_a_code entfaellt.
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


# 16.0.0 (Aquaticy-Test): entfaellt:
# test_the_real_desktop_helper_protocol_uses_a_title_not_a_window_id
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


