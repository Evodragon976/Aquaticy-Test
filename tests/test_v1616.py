"""16.1.6 (Aquaticy-Test): Fehler, die die Pruefung von 16.1.5 gefunden hat."""

from __future__ import annotations

import io

from tests.test_vercel_modus import call, vercel_app  # noqa: F401

SCHMUGGEL = "/api/health HTTP/1.1\r\nX-Probe: 1\r\n\r\nGET /api/auth/status HTTP/1.1\r\nY: z"


def roh_von(pfad: str, abfrage: str = "") -> bytes:
    from aquaticy import vercel

    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": pfad, "QUERY_STRING": abfrage,
               "HTTP_HOST": "aquaticy.vercel.app", "wsgi.input": io.BytesIO(b"")}
    return vercel._raw_request(environ, b"")


def test_the_request_line_cannot_carry_a_second_request() -> None:
    """Vercel reicht den Pfad entschluesselt weiter: %0d%0a wird zu einem Zeilenumbruch. Er darf
    die Anfragezeile nicht verlassen -- sonst liesse sich eine zweite Anfrage mit eigenen Kopfzeilen
    (etwa Origin) hineinschmuggeln, die die Cookies des Besuchers mitnimmt.
    """
    roh = roh_von(SCHMUGGEL, "q=1 2\r\nZ: 3")
    kopf, _, rest = roh.partition(b"\r\n\r\n")
    zeile = kopf.split(b"\r\n")[0]
    assert zeile.count(b" ") == 2 and zeile.startswith(b"GET /") and zeile.endswith(b" HTTP/1.1")
    namen = [z.split(b":")[0].lower() for z in kopf.split(b"\r\n")[1:]]
    assert not {b"x-probe", b"y", b"z"} & set(namen), namen
    assert rest == b"", "keine zweite Anfrage im Koerper"


def test_normal_paths_and_queries_stay_as_they_are() -> None:
    for pfad, abfrage, erwartet in (
            ("/", "", b"GET / HTTP/1.1"),
            ("/api/chats", "token=a%2Bb&x=1", b"GET /api/chats?token=a%2Bb&x=1 HTTP/1.1"),
            ("/api/media", "url=https%3A%2F%2Fexample.org%2Fa.png",
             b"GET /api/media?url=https%3A%2F%2Fexample.org%2Fa.png HTTP/1.1"),
            ("/datei mit leerzeichen", "", b"GET /datei%20mit%20leerzeichen HTTP/1.1")):
        assert roh_von(pfad, abfrage).split(b"\r\n")[0] == erwartet


def test_a_smuggled_request_gets_no_second_answer(vercel_app) -> None:  # noqa: F811
    _, _, inhalt = call(vercel_app.app, SCHMUGGEL)
    assert b"HTTP/1." not in inhalt, "nur eine Antwort -- keine zweite im Koerper"


def test_the_google_return_is_saved_like_a_post(vercel_app, monkeypatch) -> None:  # noqa: F811
    """Der Rueckweg von Google (GET /google) speichert die Zugangsdaten. Bis 16.1.5 wurde nur
    nach POST und DELETE gesichert -- die Verbindung zu Gmail war nach dem Kaltstart weg.
    """
    gesichert: list[str] = []
    monkeypatch.setattr(vercel_app, "save_if_changed", lambda: gesichert.append("x"))
    call(vercel_app.app, "/")
    assert gesichert == [], "eine normale Seite loest keine Sicherung aus"
    call(vercel_app.app, "/google")
    assert gesichert == ["x"]


def test_remote_databases_always_use_tls() -> None:
    from aquaticy.vercel_verbund import saubere_adresse

    for modus in ("disable", "allow", "prefer"):
        adresse = saubere_adresse(f"postgres://u:p@db.example.org/x?sslmode={modus}")
        assert "sslmode=require" in adresse and modus not in adresse
    assert "sslmode=verify-full" in saubere_adresse(
        "postgres://u:p@db.example.org/x?sslmode=verify-full")
    assert "sslmode=disable" in saubere_adresse("postgres://u:p@127.0.0.1/x?sslmode=disable")


def test_fetched_addresses_stay_out_of_the_vercel_log(
        vercel_app, monkeypatch) -> None:  # noqa: F811
    """Vercel stellt das Protokoll auf INFO -- httpx schrieb dann jede abgerufene Adresse mit."""
    import logging

    for name in ("httpx", "httpcore"):
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, "level", logging.INFO)
    call(vercel_app.app, "/")
    for name in ("httpx", "httpcore"):
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING
