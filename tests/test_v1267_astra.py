"""12.6.7 Astra: der QR-Code kommt auch bei dichten Codes, und es gibt immer einen Ausweg."""

import base64
import io
import json
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

import segno
import zxingcpp
from PIL import Image

from aquaticy import web
from tests.test_v965 import parallel_site as parallel_site
from tests.test_v1266_sol import Box

WEB = Path(web.__file__).parent


def dense_screen(payload: str, ecc: str, pixels: float, quality: int = 75) -> bytes:
    """Wie ein dichter WhatsApp-Code auf dem Bildschirm: wenige Pixel je Punkt, weich skaliert."""
    qr = segno.make(payload, error=ecc, boost_error=False)
    raw = io.BytesIO()
    qr.save(raw, kind="png", scale=1, border=2)
    raw.seek(0)
    modules = Image.open(raw).convert("RGB")
    side = round(modules.width * pixels)
    code = modules.resize((side, side), Image.Resampling.LANCZOS)
    page = Image.new("RGB", (1280, 800), "white")
    page.paste(code, (700, 150))
    out = io.BytesIO()
    page.save(out, format="JPEG", quality=quality, subsampling=2)
    return out.getvalue()


def payloads(count: int) -> list[str]:
    rng = random.Random(1267)
    out = []
    for _ in range(count):
        fields = ["2@" + base64.b64encode(rng.randbytes(100)).decode()]
        fields += [base64.b64encode(rng.randbytes(32)).decode() for _ in range(3)]
        out.append("https://wa.me/settings/linked_devices#" + ",".join([*fields, "1"]))
    return out


# 16.0.1 (Aquaticy-Test): 5 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_the_original_alone_does_not_read_these_codes() -> None:
    """Gegenprobe: Ohne die Varianten scheitert ein Teil -- der Test oben misst also etwas."""
    formats = zxingcpp.BarcodeFormats(zxingcpp.BarcodeFormat.QRCode)
    failed = 0
    for ecc in ("l", "m"):
        for payload in payloads(6):
            image = Image.open(io.BytesIO(dense_screen(payload, ecc, 3.4, 95)))
            failed += not any(c.text == payload
                              for c in zxingcpp.read_barcodes(image, formats=formats))
    assert failed >= 1


# -- Wer ist vorn? ---------------------------------------------------------------------
WINDOW = {"id": "0x1", "klasse": "Navigator.aquaticy-whatsapp", "titel": "WhatsApp Web"}


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


class FrontBox(Box):
    """Ein Fensterstand, den der Test frei einstellt."""

    window_title = "Signal Messenger"
    active_title: str | None = None
    active_class: str | None = None
    show_code = True

    def desktop(self, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        data = {"fenster": [{"id": "0x123", "klasse": self.klass, "titel": self.window_title}],
                "aktiv": self.window_title if self.active_title is None else self.active_title,
                "aktiv_klasse": self.klass if self.active_class is None else self.active_class}
        return subprocess.CompletedProcess(args, 0, json.dumps(data).encode(), b"")

    def screenshot(self, **kwargs: Any) -> bytes:
        self.reads += 1
        if self.show_code:
            return super().screenshot(**kwargs)
        blank = io.BytesIO()
        Image.new("RGB", (1280, 800), "white").save(blank, format="JPEG")
        return blank.getvalue()


# 16.0.0 (Aquaticy-Test): test_the_answer_says_why_there_is_no_image entfaellt.
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


def _ui() -> str:
    return (WEB / "webui.html").read_text(encoding="utf-8")


# 16.0.0 (Aquaticy-Test): entfaellt:
# test_every_reason_the_server_gives_has_a_text_and_an_english_one
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


# 16.0.0 (Aquaticy-Test): test_the_way_out_is_wired_in_the_dialog entfaellt.
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


def _chromium() -> str | None:
    found = shutil.which("chromium")
    if found:
        return found
    return "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None


# 16.0.0 (Aquaticy-Test): test_without_a_code_the_dialog_offers_the_screen entfaellt.
# Grund: Anmeldung von WhatsApp/Signal ueber QR-Code, Bildschirm oder Bruecke in der virtual
# machine ist geloescht


