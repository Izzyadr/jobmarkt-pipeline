"""Tests ohne Internet und ohne API-Key. Start mit:  uv run pytest"""

import pytest
from pydantic import ValidationError

from jobmarkt import fetch, pipeline, storage
from jobmarkt.bereinigung import bereinige_tools, normalisiere
from jobmarkt.extract import StellenAnalyse

# So sieht eine Anzeige in der Antwort der BA-API (v6) aus - gekürzt
BEISPIEL = {
    "referenznummer": "10001-123-S",
    "stellenangebotsTitel": "Data Analyst (m/w/d)",
    "hauptberuf": "Data-Analyst/in",
    "firma": "Beispiel GmbH",
    "stellenlokationen": [
        {"adresse": {"ort": "Düsseldorf", "region": "NORDRHEIN_WESTFALEN"}}
    ],
    "datumErsteVeroeffentlichung": "2026-10-15",
}


def test_vereinfache():
    stelle = fetch.vereinfache(BEISPIEL, "Data Analyst")
    assert stelle["refnr"] == "10001-123-S"
    assert stelle["ort"] == "Düsseldorf"
    assert stelle["suchbegriff"] == "Data Analyst"


def test_vereinfache_ohne_ort():
    """Fehlt der Standort, darf nichts abstürzen."""
    stelle = fetch.vereinfache({"referenznummer": "x"}, "Data Analyst")
    assert stelle["ort"] is None


def test_speichern_ohne_dubletten(tmp_path):
    con = storage.verbinde(tmp_path / "test.duckdb")
    stelle = fetch.vereinfache(BEISPIEL, "Data Analyst") | {
        "beschreibung": "SQL, Python"
    }
    storage.speichere_stelle(con, stelle)
    storage.speichere_stelle(con, stelle)  # zweites Mal: wird ignoriert
    assert con.execute("SELECT count(*) FROM stellen").fetchone()[0] == 1
    assert len(storage.offene_analysen(con, 10)) == 1


def test_analyse_speichern(tmp_path):
    con = storage.verbinde(tmp_path / "test.duckdb")
    storage.speichere_stelle(
        con, fetch.vereinfache(BEISPIEL, "x") | {"beschreibung": "..."}
    )
    analyse = StellenAnalyse(
        rolle="Data Analyst",
        level="Junior",
        tools=["Python", "SQL"],
        skills=[],
        sprachen=["Deutsch"],
        remote="hybrid",
        erfahrung_jahre=None,
    )
    storage.speichere_analyse(con, "10001-123-S", analyse.model_dump())
    assert storage.offene_analysen(con, 10) == []


def test_schema_lehnt_falsche_werte_ab():
    with pytest.raises(ValidationError):
        StellenAnalyse(
            rolle="Astronaut",
            level="Junior",
            tools=[],
            skills=[],
            sprachen=[],
            remote="hybrid",
            erfahrung_jahre=None,
        )


def test_normalisiere():
    assert normalisiere([" Python", "python", "SQL", ""]) == ["Python", "SQL"]


def test_bereinige_tools():
    roh = ["Microsoft Azure", "Azure", "MS SQL Server", "GCP", "Python"]
    assert bereinige_tools(roh) == ["Azure", "SQL Server", "Google Cloud", "Python"]


def test_bereinige_tools_begrenzt_auf_10():
    assert len(bereinige_tools([f"Tool {i}" for i in range(15)])) == 10


def test_bereinigung_alter_daten(tmp_path):
    con = storage.verbinde(tmp_path / "test.duckdb")
    analyse = {
        "rolle": "Data Engineer",
        "level": "Mid",
        "tools": ["Apache Spark", "Spark", "Microsoft Fabric"],
        "skills": [],
        "sprachen": [],
        "remote": "hybrid",
        "erfahrung_jahre": 3,
    }
    storage.speichere_analyse(con, "10001-123-S", analyse)
    assert pipeline.schritt_bereinigen(con) == 1
    assert pipeline.schritt_bereinigen(con) == 0  # zweiter Lauf: nichts mehr zu tun
    tools = con.execute("SELECT tools FROM analysen").fetchone()[0]
    assert tools == ["Spark", "Fabric"]


def test_titel_filter():
    assert pipeline.ist_relevant("Data Analyst (m/w/d)")
    assert pipeline.ist_relevant("Senior Controller Unternehmenssteuerung")
    assert pipeline.ist_relevant("Power BI Entwickler")
    assert pipeline.ist_relevant("RPA Developer")
    assert not pipeline.ist_relevant("Turbine Heat Transfer Design Engineer (f/m/d)")
    assert not pipeline.ist_relevant("Director, Sales Operations DACH")
    assert not pipeline.ist_relevant(None)


def test_dublette_erkannt(tmp_path):
    con = storage.verbinde(tmp_path / "test.duckdb")
    storage.speichere_stelle(con, fetch.vereinfache(BEISPIEL, "x"))
    assert storage.ist_dublette(con, " data analyst (m/w/d)", "BEISPIEL GmbH")
    assert not storage.ist_dublette(con, "Data Engineer", "Beispiel GmbH")
    assert not storage.ist_dublette(con, None, "Beispiel GmbH")


def test_entferne_dubletten_behaelt_aelteste(tmp_path):
    con = storage.verbinde(tmp_path / "test.duckdb")
    alt = fetch.vereinfache(BEISPIEL, "x")
    neu = alt | {"refnr": "10001-999-S", "veroeffentlicht": "2026-10-20"}
    storage.speichere_stelle(con, alt)
    storage.speichere_stelle(con, neu)
    storage.speichere_analyse(
        con,
        "10001-999-S",
        {
            "rolle": "Data Analyst",
            "level": "Junior",
            "tools": [],
            "skills": [],
            "sprachen": [],
            "remote": "hybrid",
            "erfahrung_jahre": None,
        },
    )
    assert storage.entferne_dubletten(con) == 1
    assert storage.entferne_dubletten(con) == 0  # zweiter Lauf: nichts mehr zu tun
    assert con.execute("SELECT refnr FROM stellen").fetchall() == [("10001-123-S",)]
    assert con.execute("SELECT count(*) FROM analysen").fetchone()[0] == 0


def test_ohne_beschreibung_nicht_gespeichert(tmp_path, monkeypatch):
    """Fehlt der Volltext, wird die Anzeige beim nächsten Lauf erneut versucht."""
    monkeypatch.setattr(pipeline.config, "SUCHBEGRIFFE", ["Data Analyst"])
    monkeypatch.setattr(pipeline.fetch, "suche_stellen", lambda begriff: [BEISPIEL])
    monkeypatch.setattr(pipeline.fetch, "hole_beschreibung", lambda refnr: None)
    con = storage.verbinde(tmp_path / "test.duckdb")
    assert pipeline.schritt_abrufen(con) == 0
    monkeypatch.setattr(pipeline.fetch, "hole_beschreibung", lambda refnr: "SQL")
    assert pipeline.schritt_abrufen(con) == 1
