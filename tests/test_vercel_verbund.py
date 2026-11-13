"""16.1.3 (Aquaticy-Test): Speicher-Verbund -- mehrere Postgres-Datenbanken teilen sich die Arbeit.

Die meisten Tests laufen gegen eine nachgebaute Datenbank im Speicher (kein Netz, kein Server).
Mit ``AQUATICY_TEST_POSTGRES=postgresql://nutzer@127.0.0.1:5432/`` laeuft derselbe Ablauf
zusaetzlich gegen echtes Postgres (vier Datenbanken eins, zwei, drei, vier).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest

from aquaticy import vercel_blob
from aquaticy import vercel_verbund as vv
from tests.test_vercel_modus import SECRET, FakeBlob, call, vercel_app  # noqa: F401

A, B = "a" * 32, "b" * 32


class NachbauDatenbank:
    """Versteht genau die Anweisungen des Verbunds -- und merkt sich, was geschrieben wurde."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.teile: dict[str, tuple[int, bytes]] = {}
        self.cache: dict[str, tuple[bytes, float]] = {}
        self.kaputt = False
        self.geschrieben: list[str] = []

    def ausfuehren(self, sql: str, werte: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        if self.kaputt:
            raise vv.VerbundFehler(f"{self.name} antwortet nicht (Test).")
        if sql.startswith("SELECT version, daten"):
            return [self.teile[werte[0]]] if werte[0] in self.teile else []
        if sql.startswith("SELECT version, ''::bytea"):
            return [(self.teile[werte[0]][0], b"")] if werte[0] in self.teile else []
        if "GREATEST(" in sql:
            name, mindestens, daten = werte
            fassung = max(self.teile.get(name, (0, b""))[0] + 1, int(mindestens))
            self.teile[name] = (fassung, bytes(daten))
            self.geschrieben.append(name)
            return [(fassung,)]
        if sql.startswith(f"INSERT INTO {vv.SCHEMA}.teile"):
            name, fassung, daten = werte
            self.teile[name] = (int(fassung), bytes(daten))
            return []
        if sql.startswith(f"DELETE FROM {vv.SCHEMA}.teile"):
            self.teile.pop(werte[0], None)
            return []
        if sql.startswith("SELECT name, version"):
            return [(n, self.teile[n][0]) for n in werte[0] if n in self.teile]
        if sql.startswith("SELECT daten"):
            eintrag = self.cache.get(werte[0])
            return [(eintrag[0],)] if eintrag and eintrag[1] > time.time() else []
        if sql.startswith(f"INSERT INTO {vv.SCHEMA}.cache"):
            name, _art, daten, sekunden = werte
            self.cache[name] = (bytes(daten), time.time() + sekunden)
            return []
        if sql.startswith(f"DELETE FROM {vv.SCHEMA}.cache"):
            self.cache = {k: v for k, v in self.cache.items() if v[1] > time.time()}
            return []
        raise AssertionError(f"unbekannte Anweisung: {sql}")

    def schliessen(self) -> None:
        pass


@pytest.fixture
def schluessel(monkeypatch: pytest.MonkeyPatch) -> bytes:
    monkeypatch.setenv("AQUATICY_VERCEL_SECRET", SECRET)
    wert = vercel_blob.secret_key()
    assert wert
    return wert


def vier() -> list[NachbauDatenbank]:
    return [NachbauDatenbank(n) for n in ("HAUPT", "STORAGE", "STORAGE2", "STORAGE3")]


def schreibe(pfad: Path, wert: str) -> None:
    """Eine SQLite-Datenbank im WAL-Modus, wie Aquaticy sie anlegt."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(pfad)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS t (x TEXT)")
    conn.execute("INSERT INTO t VALUES (?)", (wert,))
    conn.commit()
    conn.close()


def lies(pfad: Path) -> list[str]:
    conn = sqlite3.connect(pfad)
    try:
        return [x for (x,) in conn.execute("SELECT x FROM t")]
    finally:
        conn.close()


def konten_db(home: Path) -> Path:
    return home / ".aquaticy" / "accounts.sqlite3"


def chat_db(home: Path, kennung: str) -> Path:
    return home / ".aquaticy" / "users" / kennung / "cache.sqlite3"


# -- Adressen und Rollen ------------------------------------------------------------------------

def test_the_databases_come_from_the_environment_in_a_fixed_order() -> None:
    umgebung = {
        "STORAGE2_POSTGRES_URL": "postgres://u:p@drei.example/db?sslmode=require",
        "POSTGRES_URL": "postgres://u:p@eins.example/db",
        "DATABASE_URL": "postgres://u:p@anders.example/db",
        "STORAGE_DATABASE_URL": "postgres://u:p@zwei.example/db",
        "STORAGE3_POSTGRES_URL": "postgres://u:p@vier.example:6543/db?sslmode=require"
                                 "&supa=base-pooler.x",
        "POSTGRES_PRISMA_URL": "postgres://u:p@nicht.example/db",
        "STORAGE_POSTGRES_URL_NON_POOLING": "postgres://u:p@nicht.example/db",
        "ANDERES_URL": "https://example.org",
        "KAPUTT_POSTGRES_URL": "https://kein-postgres.example/",
    }
    gefunden = vv.adressen(umgebung)
    assert [name for name, _ in gefunden] == ["HAUPT", "STORAGE", "STORAGE2", "STORAGE3"]
    adressen = dict(gefunden)
    # POSTGRES_URL (Pool) geht vor DATABASE_URL; ohne Angabe kommt TLS dazu.
    assert adressen["HAUPT"] == "postgresql://u:p@eins.example/db?sslmode=require"
    assert adressen["STORAGE"] == "postgresql://u:p@zwei.example/db?sslmode=require"
    # Die Zusatzangabe von Supabase vertraegt der Treiber nicht -- sie bleibt weg.
    assert adressen["STORAGE3"] == "postgresql://u:p@vier.example:6543/db?sslmode=require"


def test_only_postgres_addresses_count() -> None:
    assert vv.saubere_adresse("https://example.org/x") == ""
    assert vv.saubere_adresse("") == ""
    assert vv.saubere_adresse("postgresql://u@127.0.0.1:5432/x") == \
        "postgresql://u@127.0.0.1:5432/x"


@pytest.mark.parametrize(("anzahl", "konten", "profile", "cache"), [
    (1, "HAUPT", ["HAUPT"], "HAUPT"),
    (2, "HAUPT", ["STORAGE"], "STORAGE"),
    (3, "HAUPT", ["STORAGE"], "STORAGE2"),
    (4, "HAUPT", ["STORAGE", "STORAGE3"], "STORAGE2"),
])
def test_the_tasks_are_split_by_the_number_of_databases(
        anzahl: int, konten: str, profile: list[str], cache: str, schluessel: bytes,
        tmp_path: Path) -> None:
    verbund = vv.Verbund(vier()[:anzahl], schluessel, tmp_path)  # type: ignore[arg-type]
    auskunft = verbund.auskunft()
    assert (auskunft["konten"], auskunft["profile"], auskunft["cache"]) == (konten, profile, cache)


def test_without_secret_or_database_there_is_no_verbund(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    umgebung = {"POSTGRES_URL": "postgres://u:p@eins.example/db"}
    assert vv.aus_umgebung(tmp_path, umgebung) is None, "ohne Schlüssel wird nichts gespeichert"
    monkeypatch.setenv("AQUATICY_VERCEL_SECRET", SECRET)
    assert vv.aus_umgebung(tmp_path, {}) is None
    assert vv.aus_umgebung(tmp_path, umgebung) is not None
    assert vv.aus_umgebung(tmp_path, {**umgebung, "AQUATICY_VERBUND": "0"}) is None


# -- Teile: speichern, laden, auffrischen -------------------------------------------------------

def stand_aus_dem_blob(home: Path) -> None:
    schreibe(konten_db(home), "konto-a")
    (home / ".config" / "aquaticy").mkdir(parents=True)
    (home / ".config" / "aquaticy" / ".env").write_text("AQUATICY_MODEL=x\n", encoding="utf-8")
    schreibe(chat_db(home, A), "chat-a1")
    schreibe(chat_db(home, B), "chat-b1")


def test_takeover_splits_the_folder_and_then_only_changes_are_saved(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs = vier()
    verbund = vv.Verbund(dbs, schluessel, tmp_path)  # type: ignore[arg-type]
    assert verbund.start_laden() is False, "leerer Verbund: der Stand kommt aus dem Blob"
    stand_aus_dem_blob(tmp_path)
    verbund.alles_bekannt()
    assert verbund.sichern() == 3
    assert dbs[0].geschrieben == ["kern"], "die Konten liegen in der ersten Datenbank"
    assert sorted(dbs[1].geschrieben + dbs[3].geschrieben) == [f"konto/{A}", f"konto/{B}"]
    assert not dbs[2].teile, "die Cache-Datenbank haelt keine Teile"
    # Jeder Teil hat einen Spiegel auf einer zweiten Datenbank.
    assert "kern" in dbs[3].teile
    assert f"konto/{A}" in dbs[1].teile and f"konto/{A}" in dbs[3].teile
    # Nichts geaendert (auch nicht nach dem Lesen): nichts wird hochgeladen.
    assert verbund.sichern() == 0
    assert lies(chat_db(tmp_path, A)) == ["chat-a1"]
    assert verbund.sichern() == 0
    # Nur Konto A aendert sich: genau ein Teil geht hoch.
    schreibe(chat_db(tmp_path, A), "chat-a2")
    vorher = [list(db.geschrieben) for db in dbs]
    assert verbund.sichern() == 1
    neu = [n for db, alt in zip(dbs, vorher, strict=True) for n in db.geschrieben[len(alt):]]
    assert neu == [f"konto/{A}"]


def test_everything_in_the_databases_is_encrypted(schluessel: bytes, tmp_path: Path) -> None:
    dbs = vier()
    verbund = vv.Verbund(dbs, schluessel, tmp_path)  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path)
    verbund.alles_bekannt()
    verbund.sichern()
    verbund.cache_setzen("bild", "https://example.org/a.png", b"image/png\nGEHEIMESBILD", 60)
    for db in dbs:
        for _, daten in db.teile.values():
            assert daten.startswith(b"gAAAA") and b"chat-a1" not in daten
        for daten, _ in db.cache.values():
            assert daten.startswith(b"gAAAA") and b"GEHEIMESBILD" not in daten
    assert not any("example.org" in name for name in dbs[2].cache), "nur Prüfsummen als Namen"


def test_a_second_instance_loads_the_core_and_each_profile_only_when_needed(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs = vier()
    eins = vv.Verbund(dbs, schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    zwei = vv.Verbund(dbs, schluessel, tmp_path / "zwei")  # type: ignore[arg-type]
    assert zwei.start_laden() is True
    assert lies(konten_db(tmp_path / "zwei")) == ["konto-a"]
    assert not (tmp_path / "zwei" / ".aquaticy" / "users").exists(), "noch kein Profil geladen"
    zwei.konto_laden(A)
    assert lies(chat_db(tmp_path / "zwei", A)) == ["chat-a1"]
    assert not chat_db(tmp_path / "zwei", B).exists()
    assert zwei.auskunft()["geladen"] == 1
    assert zwei.sichern() == 0, "Laden ist keine Aenderung"


def test_changes_of_another_instance_arrive_before_the_next_request(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs = vier()
    eins = vv.Verbund(dbs, schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    zwei = vv.Verbund(dbs, schluessel, tmp_path / "zwei")  # type: ignore[arg-type]
    zwei.start_laden()
    zwei.konto_laden(A)
    schreibe(chat_db(tmp_path / "zwei", A), "chat-a2")
    schreibe(konten_db(tmp_path / "zwei"), "konto-neu")
    assert zwei.sichern() == 2
    assert eins.auffrischen(jetzt=1000.0) == 2
    assert lies(chat_db(tmp_path / "eins", A)) == ["chat-a1", "chat-a2"]
    assert lies(konten_db(tmp_path / "eins")) == ["konto-a", "konto-neu"]
    assert eins.sichern() == 0
    # Hoechstens alle paar Sekunden: dazwischen fragt die Instanz nicht nach.
    schreibe(chat_db(tmp_path / "zwei", A), "chat-a3")
    zwei.sichern()
    assert eins.auffrischen(jetzt=1001.0) == 0
    assert eins.auffrischen(jetzt=1000.0 + vv.PRUEF_ABSTAND + 1) == 1


def test_an_unsaved_own_change_wins_over_a_foreign_version(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs = vier()
    eins = vv.Verbund(dbs, schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    zwei = vv.Verbund(dbs, schluessel, tmp_path / "zwei")  # type: ignore[arg-type]
    zwei.start_laden()
    # Instanz 1 kann gerade nicht speichern -- ihre Aenderung bleibt offen.
    schreibe(konten_db(tmp_path / "eins"), "wichtig")
    dbs[0].kaputt = True
    assert eins.sichern() == 0 and "kern" in eins.offen
    dbs[0].kaputt = False
    schreibe(konten_db(tmp_path / "zwei"), "fremd")
    zwei.sichern()
    assert eins.auffrischen(jetzt=1000.0) == 0, "die offene eigene Aenderung geht vor"
    assert lies(konten_db(tmp_path / "eins")) == ["konto-a", "wichtig"]
    assert eins.sichern() == 1 and not eins.offen


def test_an_existing_profile_is_never_overwritten_by_an_empty_one(
        schluessel: bytes, tmp_path: Path) -> None:
    """Legt etwas den Ordner eines Kontos an, bevor sein Profil geladen ist, zaehlt die
    Datenbank: Sie wird erst geholt, nicht ueberschrieben."""
    dbs = vier()
    eins = vv.Verbund(dbs, schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    zwei = vv.Verbund(dbs, schluessel, tmp_path / "zwei")  # type: ignore[arg-type]
    zwei.start_laden()
    fremd = tmp_path / "zwei" / ".aquaticy" / "users" / A
    fremd.mkdir(parents=True)
    (fremd / "leer.txt").write_text("", encoding="utf-8")
    zwei.sichern()
    assert lies(chat_db(tmp_path / "zwei", A)) == ["chat-a1"]
    drei = vv.Verbund(dbs, schluessel, tmp_path / "drei")  # type: ignore[arg-type]
    drei.start_laden()
    drei.konto_laden(A)
    assert lies(chat_db(tmp_path / "drei", A)) == ["chat-a1"]


def test_a_deleted_account_disappears_everywhere(schluessel: bytes, tmp_path: Path) -> None:
    dbs = vier()
    eins = vv.Verbund(dbs, schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    zwei = vv.Verbund(dbs, schluessel, tmp_path / "zwei")  # type: ignore[arg-type]
    zwei.start_laden()
    zwei.konto_laden(B)
    shutil.rmtree(tmp_path / "eins" / ".aquaticy" / "users" / B)
    assert eins.sichern() == 1
    # 16.1.4: Geloescht heisst: eine neue, leere Fassung -- auch im Spiegel. So zaehlen die
    # Fassungsnummern weiter, und kein alter Stand kommt zurueck.
    reste = [db.teile[f"konto/{B}"] for db in dbs if f"konto/{B}" in db.teile]
    assert reste and all(daten == b"" and fassung == 2 for fassung, daten in reste)
    assert eins.sichern() == 0, "ein geloeschter Teil wird nicht noch einmal geloescht"
    assert zwei.auffrischen(jetzt=1000.0) == 1
    assert not (tmp_path / "zwei" / ".aquaticy" / "users" / B).exists()


def test_the_mirror_answers_when_the_main_database_is_down(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs = vier()
    eins = vv.Verbund(dbs, schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    dbs[0].kaputt = True
    zwei = vv.Verbund(dbs, schluessel, tmp_path / "zwei")  # type: ignore[arg-type]
    assert zwei.start_laden() is True, "der Kern kommt vom Spiegel"
    assert lies(konten_db(tmp_path / "zwei")) == ["konto-a"]


def test_no_answer_at_all_is_an_error_and_never_an_empty_verbund(
        schluessel: bytes, tmp_path: Path) -> None:
    """Sonst kaeme der alte Stand aus dem Blob zurueck und ueberschriebe spaeter alles."""
    dbs = vier()
    for db in dbs:
        db.kaputt = True
    verbund = vv.Verbund(dbs, schluessel, tmp_path)  # type: ignore[arg-type]
    with pytest.raises(vv.VerbundFehler):
        verbund.start_laden()
    with pytest.raises(vv.VerbundFehler):
        verbund.konto_laden(A)
    assert f"konto/{A}" not in verbund.bekannt


def test_a_profile_follows_when_databases_are_added(schluessel: bytes, tmp_path: Path) -> None:
    """Mit einer weiteren Datenbank aendert sich, wo ein Konto liegt: gefunden wird es trotzdem,
    und beim naechsten Speichern zieht es um."""
    dbs = vier()
    drei = vv.Verbund(dbs[:3], schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    drei.alles_bekannt()
    drei.sichern()
    alle = vv.Verbund(dbs, schluessel, tmp_path / "zwei")  # type: ignore[arg-type]
    alle.start_laden()
    for kennung in (A, B):
        alle.konto_laden(kennung)
        assert lies(chat_db(tmp_path / "zwei", kennung)) == [f"chat-{kennung[0]}1"]
        schreibe(chat_db(tmp_path / "zwei", kennung), "neu")
    assert alle.sichern() == 2
    for kennung in (A, B):
        orte = {db.name for db in dbs if f"konto/{kennung}" in db.teile}
        assert orte == {db.name for db in alle.orte(f"konto/{kennung}")}


def test_wrong_secret_does_not_unpack_anything(
        schluessel: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dbs = vier()
    eins = vv.Verbund(dbs, schluessel, tmp_path / "eins")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    monkeypatch.setenv("AQUATICY_VERCEL_SECRET", "y" * 40)
    falsch = vercel_blob.secret_key()
    assert falsch
    zwei = vv.Verbund(dbs, falsch, tmp_path / "zwei")  # type: ignore[arg-type]
    with pytest.raises(vv.VerbundFehler, match="AQUATICY_VERCEL_SECRET"):
        zwei.start_laden()
    assert not konten_db(tmp_path / "zwei").exists()


def test_errors_never_show_addresses_or_passwords() -> None:
    db = vv.Datenbank("STORAGE", "postgresql://nutzer:geheimeswort@127.0.0.1:1/x")
    with pytest.raises(vv.VerbundFehler) as fehler:
        db.ausfuehren("SELECT 1")
    text = str(fehler.value)
    assert "STORAGE antwortet nicht" in text
    assert "geheimeswort" not in text and "127.0.0.1" not in text and "nutzer" not in text
    assert "geheimeswort" not in repr(db)
    # Nach einem Ausfall wartet der Verbund eine Weile, statt jede Anfrage aufzuhalten.
    start = time.monotonic()
    with pytest.raises(vv.VerbundFehler, match="Pause"):
        db.ausfuehren("SELECT 1")
    assert time.monotonic() - start < 0.5


# -- 16.1.4: Der Blob-Speicher ist der Hauptspeicher ---------------------------------------------

class NachbauBlob:
    """Der Blob-Speicher fuer einzelne Teile -- im Speicher."""

    def __init__(self) -> None:
        self.teile: dict[str, tuple[int, bytes]] = {}
        self.kaputt = False
        self.gelesen: list[str] = []

    def holen(self, teil: str) -> tuple[int, bytes] | None:
        if self.kaputt:
            raise vercel_blob.BlobError("weg")
        self.gelesen.append(teil)
        return self.teile.get(teil)

    def schreiben(self, teil: str, fassung: int, daten: bytes) -> None:
        if self.kaputt:
            raise vercel_blob.BlobError("weg")
        self.teile[teil] = (int(fassung), bytes(daten))


def mit_blob(dbs: list[NachbauDatenbank], blob: NachbauBlob, schluessel: bytes,
             home: Path) -> vv.Verbund:
    return vv.Verbund(dbs, schluessel, home, blob=blob)  # type: ignore[arg-type]


def test_the_blob_store_is_the_main_store_and_the_databases_mirror_it(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs, blob = vier(), NachbauBlob()
    eins = mit_blob(dbs, blob, schluessel, tmp_path / "eins")
    assert eins.auskunft()["haupt"] == "Blob-Speicher"
    assert eins.start_laden() is False
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    assert eins.sichern() == 3
    assert set(blob.teile) == {"kern", f"konto/{A}", f"konto/{B}"}
    # Blob und Spiegel tragen dieselbe Fassung und denselben verschluesselten Inhalt.
    for teil, (fassung, daten) in blob.teile.items():
        assert daten.startswith(b"gAAAA")
        assert eins.orte(teil)[0].teile[teil] == (fassung, daten)  # type: ignore[attr-defined]
    # Eine zweite Instanz liest den Inhalt aus dem Blob.
    zwei = mit_blob(dbs, blob, schluessel, tmp_path / "zwei")
    assert zwei.start_laden() is True
    zwei.konto_laden(A)
    assert blob.gelesen[-2:] == ["kern", f"konto/{A}"]
    assert lies(chat_db(tmp_path / "zwei", A)) == ["chat-a1"]


def test_parts_from_16_1_3_move_into_the_blob_store_when_they_are_read(
        schluessel: bytes, tmp_path: Path) -> None:
    """16.1.3 legte die Teile nur in die Datenbanken. Beim ersten Lesen ziehen sie um."""
    dbs, blob = vier(), NachbauBlob()
    alt = vv.Verbund(dbs, schluessel, tmp_path / "alt")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "alt")
    alt.alles_bekannt()
    alt.sichern()
    neu = mit_blob(dbs, blob, schluessel, tmp_path / "neu")
    assert neu.start_laden() is True
    neu.konto_laden(A)
    assert lies(chat_db(tmp_path / "neu", A)) == ["chat-a1"]
    assert set(blob.teile) == {"kern", f"konto/{A}"}
    assert neu.sichern() == 0, "der Umzug ist keine Aenderung"


def test_the_newer_version_wins_when_a_blob_write_failed(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs, blob = vier(), NachbauBlob()
    eins = mit_blob(dbs, blob, schluessel, tmp_path / "eins")
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    blob.kaputt = True
    schreibe(chat_db(tmp_path / "eins", A), "chat-a2")
    assert eins.sichern() == 1, "der Spiegel in den Datenbanken hat die Fassung"
    blob.kaputt = False
    zwei = mit_blob(dbs, blob, schluessel, tmp_path / "zwei")
    zwei.start_laden()
    zwei.konto_laden(A)
    assert lies(chat_db(tmp_path / "zwei", A)) == ["chat-a1", "chat-a2"]
    assert blob.teile[f"konto/{A}"][0] == 2, "der Blob ist wieder auf dem neuen Stand"


def test_saving_goes_on_in_the_blob_store_when_the_databases_are_down(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs, blob = vier(), NachbauBlob()
    eins = mit_blob(dbs, blob, schluessel, tmp_path / "eins")
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    for db in dbs:
        db.kaputt = True
    schreibe(chat_db(tmp_path / "eins", A), "chat-a2")
    assert eins.sichern() == 1 and not eins.offen
    assert blob.teile[f"konto/{A}"][0] == 2
    # Auch der Kaltstart geht nur mit dem Blob.
    zwei = mit_blob(dbs, blob, schluessel, tmp_path / "zwei")
    assert zwei.start_laden() is True
    zwei.konto_laden(A)
    assert lies(chat_db(tmp_path / "zwei", A)) == ["chat-a1", "chat-a2"]
    # Sind die Datenbanken zurueck, gilt weiter die hoehere Fassung aus dem Blob.
    for db in dbs:
        db.kaputt = False
    drei = mit_blob(dbs, blob, schluessel, tmp_path / "drei")
    drei.start_laden()
    drei.konto_laden(A)
    assert lies(chat_db(tmp_path / "drei", A)) == ["chat-a1", "chat-a2"]


def test_versions_never_fall_behind_after_an_outage(schluessel: bytes, tmp_path: Path) -> None:
    """16.1.5: Nach einem Ausfall ist der Blob den Datenbanken voraus. Die naechste Fassung

    muss hoeher sein als alles, was andere Instanzen schon geladen haben.
    """
    dbs, blob = vier(), NachbauBlob()
    eins = mit_blob(dbs, blob, schluessel, tmp_path / "eins")
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    for db in dbs:
        db.kaputt = True
    schreibe(chat_db(tmp_path / "eins", A), "chat-a2")
    assert eins.sichern() == 1 and blob.teile[f"konto/{A}"][0] == 2
    zwei = mit_blob(dbs, blob, schluessel, tmp_path / "zwei")
    zwei.start_laden()
    zwei.konto_laden(A)
    for db in dbs:
        db.kaputt = False
    schreibe(chat_db(tmp_path / "eins", A), "chat-a3")
    assert eins.sichern() == 1
    assert blob.teile[f"konto/{A}"][0] == 3, "weiter gezaehlt, nicht noch einmal Fassung 2"
    assert eins.orte(f"konto/{A}")[0].teile[f"konto/{A}"][0] == 3  # type: ignore[attr-defined]
    assert zwei.auffrischen(jetzt=1000.0) == 1
    assert lies(chat_db(tmp_path / "zwei", A)) == ["chat-a1", "chat-a2", "chat-a3"]


def test_a_missing_row_is_not_a_deletion(schluessel: bytes, tmp_path: Path) -> None:
    """16.1.5: Wird eine Datenbank neu aufgesetzt, fehlen dort die Zeilen. Geloescht ist

    damit nichts -- geloescht ist nur, was eine leere Fassung traegt.
    """
    dbs, blob = vier(), NachbauBlob()
    eins = mit_blob(dbs, blob, schluessel, tmp_path / "eins")
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    for db in dbs:
        db.teile.clear()
    assert eins.auffrischen(jetzt=1000.0) == 0
    assert lies(chat_db(tmp_path / "eins", A)) == ["chat-a1"]
    assert lies(chat_db(tmp_path / "eins", B)) == ["chat-b1"]
    # Auch ohne Blob: Der Spiegel hat den Teil noch.
    dbs2 = vier()
    drei = vv.Verbund(dbs2, schluessel, tmp_path / "drei")  # type: ignore[arg-type]
    stand_aus_dem_blob(tmp_path / "drei")
    drei.alles_bekannt()
    drei.sichern()
    drei.orte(f"konto/{A}")[0].teile.clear()  # type: ignore[attr-defined]
    assert drei.auffrischen(jetzt=1000.0) == 0
    assert lies(chat_db(tmp_path / "drei", A)) == ["chat-a1"]


def test_one_unreachable_profile_does_not_stop_the_others(
        schluessel: bytes, tmp_path: Path) -> None:
    """16.1.5: Ein Profil, das sich gerade nicht pruefen laesst, wartet. Der Rest wird

    gespeichert, und das Profil wird nie ungeprueft ueberschrieben.
    """
    dbs, blob = vier(), NachbauBlob()
    eins = mit_blob(dbs, blob, schluessel, tmp_path / "eins")
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    zwei = mit_blob(dbs, blob, schluessel, tmp_path / "zwei")
    zwei.start_laden()
    zwei.konto_laden(A)
    schreibe(chat_db(tmp_path / "zwei", A), "chat-a2")
    schreibe(chat_db(tmp_path / "zwei", B), "fremd")  # B ist hier noch nicht geladen

    echt = zwei._holen

    def holen(teil: str) -> tuple[int, bytes] | None:
        if teil == f"konto/{B}":
            raise vv.VerbundFehler("B antwortet nicht (Test).")
        return echt(teil)

    zwei._holen = holen  # type: ignore[method-assign]
    assert zwei.sichern() == 1
    assert blob.teile[f"konto/{A}"][0] == 2
    assert blob.teile[f"konto/{B}"][0] == 1, "B bleibt unberuehrt"


def test_nothing_is_guessed_when_blob_and_databases_are_both_silent(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs, blob = vier(), NachbauBlob()
    blob.kaputt = True
    for db in dbs:
        db.kaputt = True
    verbund = mit_blob(dbs, blob, schluessel, tmp_path)
    with pytest.raises(vv.VerbundFehler):
        verbund.start_laden()
    # Sagt der Blob "gibt es nicht" und die Datenbanken schweigen, ist das auch kein "leer".
    blob.kaputt = False
    with pytest.raises(vv.VerbundFehler):
        verbund.start_laden()


def test_a_deleted_account_stays_deleted_in_the_blob_store(
        schluessel: bytes, tmp_path: Path) -> None:
    dbs, blob = vier(), NachbauBlob()
    eins = mit_blob(dbs, blob, schluessel, tmp_path / "eins")
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    eins.sichern()
    shutil.rmtree(tmp_path / "eins" / ".aquaticy" / "users" / B)
    assert eins.sichern() == 1
    assert blob.teile[f"konto/{B}"] == (2, b"")
    zwei = mit_blob(dbs, blob, schluessel, tmp_path / "zwei")
    zwei.start_laden()
    zwei.konto_laden(B)
    assert not (tmp_path / "zwei" / ".aquaticy" / "users" / B).exists()
    # Dasselbe Konto legt wieder etwas an: Es zaehlt weiter und ist danach wieder da.
    schreibe(chat_db(tmp_path / "zwei", B), "neu")
    assert zwei.sichern() == 1 and blob.teile[f"konto/{B}"][0] == 3


def test_the_blob_part_store_speaks_the_blob_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    monkeypatch.setenv("AQUATICY_BLOB_TOKEN", "vercel_blob_rw_AbCdEf123_geheimerTeil")
    dateien: dict[str, bytes] = {}
    gesehen: list[httpx.Request] = []

    def antworten(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        if request.method == "PUT":
            dateien[request.url.params["pathname"]] = request.content
            return httpx.Response(200, json={})
        name = request.url.path.lstrip("/")
        if name == "kaputt":
            return httpx.Response(500)
        return httpx.Response(200, content=dateien[name]) if name in dateien \
            else httpx.Response(404)

    teile = vercel_blob.BlobTeile(httpx.Client(transport=httpx.MockTransport(antworten)))
    assert teile.holen(f"konto/{A}") is None
    teile.schreiben(f"konto/{A}", 7, b"gAAAAinhalt")
    assert list(dateien) == [f"aquaticy/teile/konto-{A}.enc"]
    assert teile.holen(f"konto/{A}") == (7, b"gAAAAinhalt")
    teile.schreiben("kern", 3, b"")
    assert teile.holen("kern") == (3, b"")
    put = gesehen[1]
    assert put.headers["x-vercel-blob-access"] == "private"
    assert put.headers["x-allow-overwrite"] == "1"
    assert gesehen[0].url.host == "abcdef123.private.blob.vercel-storage.com"
    dateien[f"aquaticy/teile/konto-{B}.enc"] = b"ohne kopf"
    with pytest.raises(vercel_blob.BlobError, match="beschädigt"):
        teile.holen(f"konto/{B}")


# -- Cache --------------------------------------------------------------------------------------

def test_the_cache_keeps_public_fetches_for_a_while(
        schluessel: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dbs = vier()
    verbund = vv.Verbund(dbs, schluessel, tmp_path)  # type: ignore[arg-type]
    assert verbund.cache_holen("bild", "u") is None
    assert verbund.cache_setzen("bild", "u", b"daten", 60)
    assert verbund.cache_holen("bild", "u") == b"daten"
    assert verbund.cache_holen("standard", "u") is None, "die Art gehoert zum Namen"
    assert list(dbs[2].cache) and not dbs[0].cache, "der Cache liegt in der dritten Datenbank"
    assert not verbund.cache_setzen("bild", "gross", b"x" * (vv.MAX_CACHE + 1), 60)
    assert not verbund.cache_setzen("bild", "nie", b"x", 0)
    # Abgelaufen ist abgelaufen.
    dbs[2].cache = {k: (v[0], time.time() - 1) for k, v in dbs[2].cache.items()}
    assert verbund.cache_holen("bild", "u") is None


def test_a_broken_cache_never_breaks_the_answer(schluessel: bytes, tmp_path: Path) -> None:
    dbs = vier()
    verbund = vv.Verbund(dbs, schluessel, tmp_path)  # type: ignore[arg-type]
    geholt: list[str] = []

    def holen(was: str) -> bytes | None:
        geholt.append(was)
        return b"frisch"

    mit_cache = verbund.gemerkt("standard", lambda was: 60, holen)
    assert mit_cache("a") == b"frisch" and mit_cache("a") == b"frisch"
    assert geholt == ["a"], "der zweite Abruf kam aus dem Cache"
    dbs[2].kaputt = True
    assert mit_cache("b") == b"frisch"
    dbs[2].kaputt = False
    # Nach einem Fehler laesst der Cache die Datenbank eine Weile in Ruhe.
    assert mit_cache("a") == b"frisch" and geholt == ["a", "b", "a"]


# -- Ueber den Vercel-Einstieg ------------------------------------------------------------------

@pytest.fixture
def verbund_app(vercel_app, monkeypatch: pytest.MonkeyPatch):  # noqa: F811
    monkeypatch.setenv("AQUATICY_VERCEL_SECRET", SECRET)
    dbs = vier()
    monkeypatch.setattr(
        vv, "aus_umgebung",
        lambda home, umgebung=None: vv.Verbund(dbs, vercel_blob.secret_key(), home))
    return vercel_app, dbs


def neue_instanz(vercel: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import config

    shutil.rmtree(vercel.HOME, ignore_errors=True)
    monkeypatch.setattr(vercel, "_STATE", vercel.new_state())
    config.reset_settings_cache()


def test_accounts_and_profiles_survive_a_cold_start_through_the_verbund(
        verbund_app, monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import web

    vercel, dbs = verbund_app
    assert call(vercel.app, "/")[0].startswith("200")
    konto = web.AUTH.register("ana@example.org", "ein-langes-Passwort-42", "normal",
                              terms_accepted=True, terms_version="1", ip="198.51.100.7")
    profil = web.AUTH.profile_dir(konto.id)
    profil.mkdir(parents=True, exist_ok=True)
    (profil / "notiz.txt").write_text("hallo", encoding="utf-8")
    vercel.save_if_changed()
    assert "kern" in dbs[0].teile
    assert any(f"konto/{konto.id}" in db.teile for db in (dbs[1], dbs[3]))

    neue_instanz(vercel, monkeypatch)
    assert call(vercel.app, "/")[0].startswith("200")
    assert [k.id for k in web.AUTH.accounts()] == [konto.id]
    assert not (vercel.HOME / ".aquaticy" / "users" / konto.id).exists()
    assert (web.AUTH.profile_dir(konto.id) / "notiz.txt").read_text(encoding="utf-8") == "hallo"


def test_the_first_start_takes_over_the_backup_from_the_blob_store(
        verbund_app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vercel, dbs = verbund_app
    alt = tmp_path / "alt"
    stand_aus_dem_blob(alt)
    archiv = vercel_blob.pack(alt)
    monkeypatch.setattr(vercel_blob, "restore",
                        lambda home, client=None: vercel_blob.unpack(archiv, home))
    assert call(vercel.app, "/")[0].startswith("200")
    assert "kern" in dbs[0].teile
    assert {f"konto/{A}", f"konto/{B}"} <= set(dbs[1].teile) | set(dbs[3].teile)
    # Beim naechsten Kaltstart kommt alles aus dem Verbund -- der Blob wird nicht mehr gefragt.
    monkeypatch.setattr(vercel_blob, "restore",
                        lambda home, client=None: pytest.fail("Blob nicht mehr noetig"))
    neue_instanz(vercel, monkeypatch)
    assert call(vercel.app, "/")[0].startswith("200")
    assert lies(konten_db(vercel.HOME))[0] == "konto-a"


def test_an_unreachable_verbund_stops_the_start_instead_of_starting_empty(
        verbund_app, monkeypatch: pytest.MonkeyPatch) -> None:
    vercel, dbs = verbund_app
    for db in dbs:
        db.kaputt = True
    status, _, inhalt = call(vercel.app, "/")
    assert status.startswith("503")
    assert "Sicherung ließ sich nicht laden" in inhalt.decode("utf-8")


def test_a_failed_start_is_tried_again_after_a_pause(
        verbund_app, monkeypatch: pytest.MonkeyPatch) -> None:
    """16.1.5: Ein kurzer Ausfall beim Kaltstart legt die Instanz nicht fuer immer lahm."""
    vercel, dbs = verbund_app
    for db in dbs:
        db.kaputt = True
    assert call(vercel.app, "/")[0].startswith("503")
    for db in dbs:
        db.kaputt = False
    geladen: list[int] = []
    echt = vv.Verbund.start_laden
    monkeypatch.setattr(vv.Verbund, "start_laden",
                        lambda self: geladen.append(1) or echt(self))
    # Innerhalb der Pause fragt die Instanz den Speicher nicht bei jeder Anfrage neu.
    assert call(vercel.app, "/")[0].startswith("503") and not geladen
    vercel._STATE["error_bis"] = 0.0
    assert call(vercel.app, "/")[0].startswith("200") and geladen == [1]
    assert vercel._STATE["error"] == ""


def test_without_databases_the_blob_backup_works_as_before(vercel_app) -> None:  # noqa: F811
    assert call(vercel_app.app, "/")[0].startswith("200")
    assert vercel_app._STATE["verbund"] is None


def test_public_fetches_go_through_the_shared_cache(
        verbund_app, monkeypatch: pytest.MonkeyPatch) -> None:
    from aquaticy import standard, web

    vercel, dbs = verbund_app
    geholt: list[str] = []

    def holen(url: str) -> Any:
        geholt.append(url)
        return {"ok": True}

    def bild(settings: Any, target: str) -> tuple[int, bytes, str]:
        geholt.append(target)
        return 200, b"PNGDATEN", "image/png"

    monkeypatch.setattr(standard, "holen_json", holen)
    monkeypatch.setattr(web, "media_by_url", bild)
    assert call(vercel.app, "/")[0].startswith("200")
    wetter = "https://api.open-meteo.com/v1/forecast?latitude=1"
    assert standard.holen_json(wetter) == {"ok": True}
    assert standard.holen_json(wetter) == {"ok": True}
    assert web.media_by_url(None, "https://example.org/a.png") == (200, b"PNGDATEN", "image/png")
    assert web.media_by_url(None, "https://example.org/a.png") == (200, b"PNGDATEN", "image/png")
    assert geholt == [wetter, "https://example.org/a.png"], "je einmal geholt, dann aus dem Cache"
    assert len(dbs[2].cache) == 2
    # Ein Dienst ohne Eintrag in der Liste wird nicht gemerkt.
    standard.holen_json("https://unbekannt.example/x")
    standard.holen_json("https://unbekannt.example/x")
    assert geholt.count("https://unbekannt.example/x") == 2


# -- Gegen echtes Postgres ----------------------------------------------------------------------

POSTGRES = os.environ.get("AQUATICY_TEST_POSTGRES", "").strip()


@pytest.mark.skipif(not POSTGRES, reason="AQUATICY_TEST_POSTGRES ist nicht gesetzt")
def test_the_same_flow_against_real_postgres(schluessel: bytes, tmp_path: Path) -> None:
    import psycopg

    for name in ("eins", "zwei", "drei", "vier"):
        with psycopg.connect(POSTGRES + name, autocommit=True) as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {vv.SCHEMA} CASCADE")
    umgebung = {"POSTGRES_URL": POSTGRES + "eins", "STORAGE_POSTGRES_URL": POSTGRES + "zwei",
                "STORAGE2_POSTGRES_URL": POSTGRES + "drei",
                "STORAGE3_POSTGRES_URL": POSTGRES + "vier?supa=base-pooler.x"}
    eins = vv.aus_umgebung(tmp_path / "eins", umgebung)
    assert eins is not None and eins.start_laden() is False
    stand_aus_dem_blob(tmp_path / "eins")
    eins.alles_bekannt()
    assert (eins.sichern(), eins.sichern()) == (3, 0)
    zwei = vv.aus_umgebung(tmp_path / "zwei", umgebung)
    assert zwei is not None and zwei.start_laden() is True
    zwei.konto_laden(A)
    schreibe(chat_db(tmp_path / "zwei", A), "chat-a2")
    assert zwei.sichern() == 1
    assert eins.auffrischen(jetzt=1000.0) == 1
    assert lies(chat_db(tmp_path / "eins", A)) == ["chat-a1", "chat-a2"]
    assert zwei.cache_setzen("bild", "u", b"daten", 60)
    assert eins.cache_holen("bild", "u") == b"daten"
    with psycopg.connect(POSTGRES + "vier", autocommit=True) as conn:
        zeilen = conn.execute(f"SELECT name, daten FROM {vv.SCHEMA}.teile").fetchall()
    assert zeilen and all(bytes(daten).startswith(b"gAAAA") for _, daten in zeilen)
