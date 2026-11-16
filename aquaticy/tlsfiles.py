"""Private Dateien (TLS-Schluessel) sicher schreiben: erst daneben, dann ersetzen."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _stage(path: Path, data: bytes) -> Path:
    from aquaticy.memory import secure_file

    descriptor, name = tempfile.mkstemp(prefix=".tls-", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        secure_file(temporary)
        temporary.write_bytes(data)
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_private(path: Path, data: bytes) -> None:
    """Private Dateien ohne vorhersagbare Zwischenpfade atomar ersetzen."""
    temporary = _stage(path, data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
