"""15.4.5: Coworker achten auch bei Werkzeugen auf widerrufene Rechte."""


import pytest

from aquaticy.memory import Memory

# 16.0.1 (Aquaticy-Test): 7 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


@pytest.mark.parametrize('identifier', [True, 1.5, float('inf')])
def test_memory_deletion_never_rounds_invalid_identifiers(settings, identifier):
    from aquaticy.tools import Toolbox

    memory = Memory(settings.db_path, settings.data_dir, settings.memory_key)
    memory.remember('Eine unveränderte Notiz')
    toolbox = Toolbox(settings)
    try:
        assert toolbox.forget_memory(identifier).get('error')
        assert memory.count() == 1
    finally:
        toolbox.close()
