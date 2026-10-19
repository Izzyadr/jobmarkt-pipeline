"""Tests ohne Internet und ohne API-Key. Start mit:  uv run pytest"""

import pytest
from pydantic import ValidationError

from jobmarkt import fetch, storage
from jobmarkt.extract import StellenAnalyse, normalisiere

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
