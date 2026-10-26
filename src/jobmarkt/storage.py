"""Speicherung in DuckDB: eine Tabelle für Anzeigen, eine für LLM-Ergebnisse."""

from pathlib import Path

import duckdb

from jobmarkt import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS stellen (
    refnr           VARCHAR PRIMARY KEY,
    titel           VARCHAR,
    beruf           VARCHAR,
    arbeitgeber     VARCHAR,
    ort             VARCHAR,
    region          VARCHAR,
    veroeffentlicht DATE,
    suchbegriff     VARCHAR,
    beschreibung    VARCHAR,
    abgerufen_am    TIMESTAMP DEFAULT current_timestamp
);
CREATE TABLE IF NOT EXISTS analysen (
    refnr           VARCHAR PRIMARY KEY,
    rolle           VARCHAR,
    level           VARCHAR,
    tools           VARCHAR[],
    skills          VARCHAR[],
    sprachen        VARCHAR[],
    remote          VARCHAR,
    erfahrung_jahre INTEGER,
    extrahiert_am   TIMESTAMP DEFAULT current_timestamp
);
"""


def verbinde(pfad: Path = config.DB_PFAD) -> duckdb.DuckDBPyConnection:
    """Öffnet die Datenbank und legt die Tabellen an, falls nötig."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(pfad))
    con.execute(SCHEMA)
    return con


def ist_bekannt(con, refnr: str) -> bool:
    return (
        con.execute("SELECT 1 FROM stellen WHERE refnr = ?", [refnr]).fetchone()
        is not None
    )


def ist_dublette(con, titel: str | None, arbeitgeber: str | None) -> bool:
    """Gibt es schon eine Anzeige mit gleichem Titel und Arbeitgeber?

    Firmen schalten dieselbe Stelle oft neu, mit neuer Referenznummer.
    Groß-/Kleinschreibung und Leerzeichen am Rand zählen nicht.
    """
    if not titel or not arbeitgeber:
        return False
    return (
        con.execute(
            """
            SELECT 1 FROM stellen
            WHERE lower(trim(titel)) = lower(trim(?))
              AND lower(trim(arbeitgeber)) = lower(trim(?))
            LIMIT 1
            """,
            [titel, arbeitgeber],
        ).fetchone()
        is not None
    )


def entferne_dubletten(con) -> int:
    """Löscht neu geschaltete Kopien bereits gespeicherter Anzeigen.

    Pro Titel und Arbeitgeber bleibt die zuerst veröffentlichte Anzeige.
    Gibt die Anzahl gelöschter Anzeigen zurück.
    """
    doppelt = [
        zeile[0]
        for zeile in con.execute(
            """
            SELECT refnr FROM (
                SELECT refnr, row_number() OVER (
                    PARTITION BY lower(trim(titel)), lower(trim(arbeitgeber))
                    ORDER BY veroeffentlicht, abgerufen_am, refnr
                ) AS nr
                FROM stellen
                WHERE titel IS NOT NULL AND arbeitgeber IS NOT NULL
            ) WHERE nr > 1
            """
        ).fetchall()
    ]
    for refnr in doppelt:
        con.execute("DELETE FROM analysen WHERE refnr = ?", [refnr])
        con.execute("DELETE FROM stellen WHERE refnr = ?", [refnr])
    return len(doppelt)


def speichere_stelle(con, stelle: dict) -> None:
    """Speichert eine Anzeige. Bereits vorhandene refnr werden ignoriert."""
    con.execute(
        """
        INSERT OR IGNORE INTO stellen
            (refnr, titel, beruf, arbeitgeber, ort, region,
             veroeffentlicht, suchbegriff, beschreibung)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            stelle["refnr"],
            stelle["titel"],
            stelle["beruf"],
            stelle["arbeitgeber"],
            stelle["ort"],
            stelle["region"],
            stelle["veroeffentlicht"],
            stelle["suchbegriff"],
            stelle.get("beschreibung"),
        ],
    )


def offene_analysen(con, limit: int) -> list[tuple]:
    """Anzeigen mit Beschreibung, die noch nicht analysiert wurden."""
    return con.execute(
        """
        SELECT s.refnr, s.titel, s.beschreibung
        FROM stellen s
        LEFT JOIN analysen a USING (refnr)
        WHERE a.refnr IS NULL AND s.beschreibung IS NOT NULL
        ORDER BY s.veroeffentlicht DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()


def speichere_analyse(con, refnr: str, analyse: dict) -> None:
    con.execute(
        """
        INSERT OR REPLACE INTO analysen
            (refnr, rolle, level, tools, skills, sprachen, remote, erfahrung_jahre)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            refnr,
            analyse["rolle"],
            analyse["level"],
            analyse["tools"],
            analyse["skills"],
            analyse["sprachen"],
            analyse["remote"],
            analyse["erfahrung_jahre"],
        ],
    )


def alle_listen(con) -> list[tuple]:
    """Tools und Skills aller Analysen (für die Bereinigung)."""
    return con.execute("SELECT refnr, tools, skills FROM analysen").fetchall()


def aktualisiere_listen(con, refnr: str, tools: list[str], skills: list[str]) -> None:
    con.execute(
        "UPDATE analysen SET tools = ?, skills = ? WHERE refnr = ?",
        [tools, skills, refnr],
    )
