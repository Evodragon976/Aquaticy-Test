"""12.6.7 Astra: der QR-Code kommt auch bei dichten Codes, und es gibt immer einen Ausweg."""

import base64
import io
import json
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import segno
import zxingcpp
from PIL import Image

from aquaticy import web
from aquaticy.messenger_login import pairing_code, qr_image
from tests.test_v965 import parallel_site as parallel_site
from tests.test_v1266_sol import Box
from tests.test_v1266_sol import login as login

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


@pytest.mark.parametrize("ecc", ["l", "m"])
@pytest.mark.parametrize("quality", [75, 95])
def test_dense_codes_with_few_pixels_per_dot_are_read(ecc: str, quality: int) -> None:
    for payload in payloads(6):
        shot = dense_screen(payload, ecc, 3.4, quality)
        result = qr_image(shot, "whatsapp")
        assert result is not None
        with Image.open(io.BytesIO(base64.b64decode(result.split(",", 1)[1]))) as image:
            assert zxingcpp.read_barcodes(image)[0].text == payload


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


def test_the_code_is_drawn_fresh_sharp_and_small() -> None:
    payload = payloads(1)[0]
    result = qr_image(dense_screen(payload, "m", 4.0), "whatsapp")
    assert result is not None and result.startswith("data:image/png;base64,")
    with Image.open(io.BytesIO(base64.b64decode(result.split(",", 1)[1]))) as image:
        assert image.width < 600 and image.height < 600
        assert image.getpixel((0, 0)) == (255, 255, 255)
        colours = {pixel for pixel in image.getdata()}
        assert colours == {(0, 0, 0), (255, 255, 255)}, "scharf: nur Schwarz und Weiß"


def test_only_a_valid_code_of_the_chosen_service_is_ever_drawn() -> None:
    other = dense_screen("https://example.org/attacker-login?" + "a" * 120, "m", 4.0)
    assert qr_image(other, "whatsapp") is None
    assert qr_image(dense_screen(payloads(1)[0], "m", 4.0), "signal") is None
    assert not pairing_code("https://example.org/x", "whatsapp")


def test_a_screen_without_a_code_gives_nothing_and_is_quick() -> None:
    import time

    blank = io.BytesIO()
    Image.new("RGB", (1280, 800), "white").save(blank, format="JPEG", quality=75)
    start = time.monotonic()
    assert qr_image(blank.getvalue(), "whatsapp") is None
    assert time.monotonic() - start < 4


# -- Wer ist vorn? ---------------------------------------------------------------------
WINDOW = {"id": "0x1", "klasse": "Navigator.aquaticy-whatsapp", "titel": "WhatsApp Web"}


@pytest.mark.parametrize(("after", "expected"), [
    ({"aktiv": "WhatsApp Web", "aktiv_klasse": "Navigator.aquaticy-whatsapp"}, True),
    ({"aktiv": "WhatsApp Web", "aktiv_klasse": ""}, True),
    ({"aktiv": "Ein anderes Fenster", "aktiv_klasse": "Navigator.aquaticy-whatsapp"}, False),
    ({"aktiv": "Terminal", "aktiv_klasse": "xterm.XTerm"}, False),
    ({"aktiv": "", "aktiv_klasse": "Navigator.aquaticy-whatsapp"}, True),
    ({"aktiv": "", "aktiv_klasse": "xterm.XTerm"}, False),
    ({"aktiv": "", "aktiv_klasse": "feh.Signal"}, False),
    ({"aktiv": "", "aktiv_klasse": ""}, True),
    ({}, True),
])
def test_the_front_window_check(after: dict[str, Any], expected: bool) -> None:
    assert web.front_is_messenger(WINDOW, after, "whatsapp") is expected


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


@pytest.fixture
def front(login, monkeypatch):
    from aquaticy import sandbox

    session, _, payload = login
    box = FrontBox()
    monkeypatch.setattr(sandbox, "shared", lambda settings: box)
    return session, box, payload


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


def test_the_sandbox_passes_the_quality_to_the_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import sandbox

    called: list[tuple[str, ...]] = []
    box = sandbox.Sandbox(user_mode=True)

    def fake(*args: str, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        called.append(args)
        return subprocess.CompletedProcess(args, 0, b"\xff\xd8bild", b"")

    monkeypatch.setattr(box, "desktop", fake)
    box.screenshot(quality=92)
    box.screenshot(quality=999)
    box.screenshot(quality=1)
    box.screenshot()
    assert called == [("shot", "--quality", "92"), ("shot", "--quality", "95"),
                      ("shot", "--quality", "30"), ("shot",)]
