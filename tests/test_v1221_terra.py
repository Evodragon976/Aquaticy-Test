"""12.2.1 Terra: Haus-Regel, kurze Takte und zeitgleiche Besitzer-Aenderungen."""
from __future__ import annotations

import re

# 16.0.1 (Aquaticy-Test): 9 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_product_has_no_decorative_emoji_outside_coworkers_or_notes_sidebar_button():
    from aquaticy.web import UI_FILE

    source = UI_FILE.read_text()
    assert 'id="btn-notes"' not in source and '$("#btn-notes")' not in source
    # 16.0.1 (Aquaticy-Test): Mit den Coworkern ist die letzte Ausnahme weg -- kein Emoji mehr.
    assert '>Coworker<span' not in source
    assert "Home-Assistant-Dauerfreigaben" not in source
    for line in source.splitlines():
        assert not re.search(r"[\U0001f000-\U0001ffff]", line), line[:80]
