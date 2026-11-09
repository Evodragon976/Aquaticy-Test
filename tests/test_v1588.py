"""15.8.8: Vercel findet einen Einstieg statt mit PYTHON_ENTRYPOINT_NOT_FOUND abzubrechen.

In Aquaticy-Ai ist das eine schlichte Startseite. In Aquaticy-Test laeuft dort die ganze
Oberflaeche (Vercel-Modus); deren Tests stehen in tests/test_vercel_modus.py.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_names_the_vercel_entrypoint() -> None:
    daten = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert daten["tool"]["vercel"]["entrypoint"] == "aquaticy.vercel:app"


def test_every_extra_can_be_installed_with_pillow_13() -> None:
    """uv lock auf Vercel loest alle Extras auf: term-image (Pillow < 11) brach den Build ab.

    Aquaticy-Test 16.0.0 braucht Pillow gar nicht mehr (nur fuer den QR-Code der Messenger).
    """
    daten = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert not any(d.lower().startswith(("pillow", "neonize", "zxing"))
                   for d in daten["project"]["dependencies"])
    extras = daten["project"]["optional-dependencies"]
    assert not any(d.lower().startswith("term-image") for paket in extras.values() for d in paket)


def test_vercelignore_keeps_what_the_wheel_includes() -> None:
    """hatchling bricht ab, wenn eine force-include-Datei fehlt ("Forced include not found")."""
    import pathspec

    daten = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    fest = daten["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    regeln = (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
    spec = pathspec.PathSpec.from_lines("gitwildmatch", regeln)
    assert fest and not [quelle for quelle in fest if spec.match_file(quelle)]


def test_the_readme_explains_vercel() -> None:
    assert "### Vercel" in (ROOT / "README.md").read_text(encoding="utf-8")
