"""15.7.7: Zertifikatsketten, DNS-Fristen und Prozessuebergreifende Zustandsupdates."""

import subprocess
import sys

from aquaticy import uistate

# 16.0.1 (Aquaticy-Test): 7 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f088_separate_processes_do_not_lose_independent_ui_settings(tmp_path):
    db = tmp_path / 'state.db'
    uistate.UIState(db)
    code = '''import sys,time
from pathlib import Path
from aquaticy.uistate import UIState
state=UIState(sys.argv[1]); original=state.read
def read():
    value=original(); Path(sys.argv[2]+sys.argv[3]).touch()
    end=time.monotonic()+.3
    while time.monotonic()<end and len(list(Path(sys.argv[2]).parent.glob('ready-*')))<2:
        time.sleep(.005)
    return value
state.read=read
state.write({sys.argv[4]:sys.argv[5]})
'''
    processes = [subprocess.Popen([sys.executable, '-c', code, str(db),
                  str(tmp_path / 'ready-'), str(n), field, value],
                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                 for n, (field, value) in enumerate([('theme', 'dark'), ('lang', 'en')])]
    for process in processes:
        out, err = process.communicate(timeout=10)
        assert process.returncode == 0, (out, err)
    result = uistate.UIState(db).read()
    assert result['theme'] == 'dark' and result['lang'] == 'en'


