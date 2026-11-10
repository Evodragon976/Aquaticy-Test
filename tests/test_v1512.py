"""15 bestaetigte Regressionen: GitHub, VM-Grenzen, Secure Pro und Serverprozesse."""

import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from aquaticy import addons, old_server
from aquaticy.tools import Toolbox
from tests.test_v1500 import FakeGitHub

TOKEN = "ghp_" + "a" * 36


@pytest.fixture
def github_case(settings, monkeypatch):
    fake = FakeGitHub()
    client_type = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **kw: client_type(
        *a, **{"transport": httpx.MockTransport(fake), **kw}))
    monkeypatch.setattr(addons, "_takt", lambda *a, **kw: None)
    addons.install(settings, "github", pro=False)
    settings.github_token = TOKEN
    box = Toolbox(settings)
    box.ask_handler = lambda *a: "ja"
    yield box, fake
    box.close()


def test_f01_unrelated_process_with_aquaticy_in_arguments_is_not_a_server():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)", "Aquaticy"])
    try:
        assert not old_server.is_aquaticy(child.pid)
    finally:
        child.terminate()
        child.wait(timeout=5)


@pytest.mark.skipif(not Path('/proc').is_dir(), reason="Linux-Prozesszustand erforderlich")
def test_f02_a_terminated_child_counts_as_stopped_before_its_parent_reaps_it(monkeypatch):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
    monkeypatch.setattr(old_server, "is_aquaticy", lambda pid: pid == child.pid)
    try:
        assert old_server.stop(child.pid, wait=0.4)
    finally:
        child.wait(timeout=5)


# 16.0.1 (Aquaticy-Test): 2 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 3 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain, GitHub schreiben).


# 16.0.1 (Aquaticy-Test): 12 Test(s) entfallen -- sie pruefen Teile, die es hier
# nicht mehr gibt (virtual machine, Messenger, Verbund, Auto-Upgrading, Coworker,
# Heimnetz, Home Assistant, Lager, eigene Domain).


def test_f15_comparison_pagination_keeps_files_that_github_only_sends_on_page_one():
    files = [{"filename": f"file{i}.py", "status": "modified"} for i in range(30)]

    def fetch(route, **params):
        return {"files": files if params.get("page") == 1 else [], "commits": []}

    first = addons._github_action(fetch, "vergleich", "o/r", 0, "", "fix", "open", "",
                                   base="main", page=1)
    second = addons._github_action(fetch, "vergleich", "o/r", 0, "", "fix", "open", "",
                                    base="main", page=2)
    assert first["next_page"] == 2
    assert [f["datei"] for f in second["dateien"]] == [f"file{i}.py" for i in range(20, 30)]
    assert second["next_page"] is None


@pytest.mark.parametrize("command,expected", [
    (["python3", "-m", "aquaticy.cli", "web"], True),
    (["python3.12", "-u", "-m", "aquaticy.cli", "web", "--lan"], True),
    (["python3", "-c", "pass", "aquaticy", "web"], False),
    (["echo", "-m", "aquaticy.cli", "web"], False),
    (["python3", "-m", "/tmp/aquaticy.cli", "web"], False),
    (["/usr/bin/aquaticy", "/tmp/web"], False),
    (["/usr/bin/aquaticy", "chat", "web"], False),
])
def test_f01_command_recognition_accepts_only_actual_server_invocations(command, expected):
    assert old_server._ist_server(command) is expected


