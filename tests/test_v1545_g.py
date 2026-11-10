"""15.4.5: Netzfreigaben, sparsames Scannen und wiederkehrende UI-Abfragen."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / 'aquaticy' / 'webui.html'
NODE = shutil.which('node')


# 16.0.1 (Aquaticy-Test): 2 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def _function(name):
    source = UI.read_text(encoding='utf-8')
    start = source.index('async function ' + name + '(')
    return source[start:source.index('\n}', start) + 2]


@pytest.mark.skipif(not NODE, reason='JavaScript-Laufzeit fehlt')
# 16.0.1 (Aquaticy-Test): 'coworker' entfaellt -- es gibt keine Coworker mehr.
@pytest.mark.parametrize('component', ['addons'])
def test_f060_polling_recovers_from_a_transient_connection_failure(component):
    function = 'coworkerLaden' if component == 'coworker' else 'addonsLaden'
    setup = '''
    let timers = [], calls = 0;
    const elements = new Map();
    const $ = selector => {
      if (!elements.has(selector)) elements.set(selector, {classList:{contains:()=>true}});
      return elements.get(selector);
    };
    const document = {hidden:false};
    const setTimeout = (callback, delay) => { timers.push(callback); return timers.length; };
    const clearTimeout = () => {};
    const addonBox = $('#addonbox'), coworkerBox = $('#coworkerbox');
    let addonTakt = 0, coworkerTakt = 0, addonDaten = null, coworkerDaten = null;
    const zeigeAddons = () => {}, coworkerZeigen = () => {}, coworkerAbzeichen = () => {};
    const api = async () => { calls++; throw new Error('Connection briefly interrupted'); };
    '''
    script = setup + _function(function) + f'\n{function}().then(() => {{' + '''
      if (!timers.length) throw new Error('The open window never retries after the outage');
    });
    '''
    result = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not NODE, reason='JavaScript-Laufzeit fehlt')
def test_f061_addon_polling_does_not_request_hidden_tabs():
    script = '''
    let calls = 0, addonTakt = 0, addonDaten = null;
    const document = {hidden:true};
    const clearTimeout = () => {}, setTimeout = () => 1;
    const addonBox = {classList:{contains:()=>true}};
    const $ = () => ({});
    const api = async () => { calls++; return {json:async () => ({addons:[]})}; };
    const zeigeAddons = () => {};
    ''' + _function('addonsLaden') + '''
    addonsLaden().then(() => process.stdout.write(JSON.stringify({calls})));
    '''
    result = subprocess.run([NODE, '-e', script], capture_output=True, text=True,
                            timeout=10, check=True)
    assert json.loads(result.stdout)['calls'] == 0
