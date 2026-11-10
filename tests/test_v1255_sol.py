"""12.5.5 Sol: "Auf Befehl ohne Rückfrage schalten" (AQUATICY_HA_DIRECT).

Wer "Mach die Lampen an" schrieb, wurde gefragt, ob Aquaticy das wirklich darf: Das
Nachsehen mit ``ha_states`` zählte als fremder Inhalt, danach fragte ``ha_call`` jedes
Mal nach. Mit dem neuen Schalter gilt das nicht mehr -- für den Chat und für Coworker.
Geschützte Bereiche (Schloss, Alarm, Tor, Heizung, Skript, Szene) fragen weiter, und
nach Webseiten oder Mails fragt Aquaticy auch.
"""

from __future__ import annotations

from aquaticy import preferences

LICHT = {"domain": "light", "service": "turn_on", "entity_id": "light.kueche"}


# 16.0.1 (Aquaticy-Test): 13 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_the_model_cannot_turn_the_switch_on() -> None:
    assert "AQUATICY_HA_DIRECT" in preferences.PROTECTED
    assert preferences.find("AQUATICY_HA_DIRECT") is None
    assert preferences.refusal("AQUATICY_HA_DIRECT")


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 1 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.0 (Aquaticy-Test): test_the_switch_is_in_the_form_and_the_state entfaellt.
# Grund: virtual machine, Heimnetz, Messenger, Upgrading und Verbund sind aus der Oberflaeche
# geloescht


