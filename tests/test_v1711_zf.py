"""17.1.1: Bestaetigung in zwei Schritten -- Funde in Aquaticy-Test (nur hier gibt es sie)."""

from __future__ import annotations

import pytest

from aquaticy.auth import AuthStore
from tests.test_v1657 import (  # noqa: F401 -- Fixtures
    ANMELDEN,
    GERAET,
    KEKS,
    Postfach,
    Uhr,
    ZweiFaktor,
    auth,
    konto,
    postfach,
    uhr,
    zf,
)


@pytest.mark.parametrize("ziffern", ["۰۱۲۳۴۵۶۷۸۹", "٠١٢٣٤٥٦٧٨٩", "０１２３４５６７８９"])
def test_the_code_counts_in_any_script_of_digits(
        zf: ZweiFaktor, auth: AuthStore, postfach: Postfach,  # noqa: F811
        ziffern: str) -> None:
    start = zf.beginnen(konto(auth), ANMELDEN, GERAET, KEKS)
    eingabe = "".join(ziffern[int(z)] for z in postfach.code())
    assert zf.pruefen(start["challenge"], eingabe, ANMELDEN, GERAET, KEKS).id == konto(auth).id
