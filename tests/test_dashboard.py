"""Rauchtest für das Dashboard: läuft es mit Testdaten ohne Fehler durch?"""

from datetime import date, timedelta
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from jobmarkt import storage

DASHBOARD = str(Path(__file__).resolve().parents[1] / "app" / "dashboard.py")


@pytest.fixture(autouse=True)
def leerer_cache():
    """Das Dashboard speichert Abfragen zwischen. Jeder Test startet frisch."""
    st.cache_data.clear()


def _testdatenbank(pfad: Path) -> None:
    con = storage.verbinde(pfad)
    heute = date.today()
    stellen = [
        ("1-S", "Data Analyst (m/w/d)", "FERCHAU GmbH Niederlassung Köln", "Köln"),
        (
            "2-S",
            "Data Engineer (m/w/d)",
            "FERCHAU GmbH Niederlassung Essen",
            "Essen, Ruhr",
        ),
        ("3-S", "BI Developer (m/w/d)", "Deichmann", "Essen, Ruhr"),
        ("4-S", "Controller (m/w/d)", "Deichmann SE", "Düsseldorf"),
    ]
    for i, (refnr, titel, firma, ort) in enumerate(stellen):
        storage.speichere_stelle(
            con,
            {
                "refnr": refnr,
                "titel": titel,
                "beruf": None,
                "arbeitgeber": firma,
                "ort": ort,
                "region": None,
                "veroeffentlicht": heute - timedelta(days=i * 3),
                "suchbegriff": "Data Analyst",
                "beschreibung": "...",
            },
        )
        storage.speichere_analyse(
            con,
            refnr,
            {
                "rolle": titel.split(" (")[0],
                "level": ["Junior", "Mid", "Senior", "Lead"][i],
                "tools": ["SQL", "Python"] if i % 2 else ["Power BI", "SQL"],
                "skills": ["Datenmodellierung"],
                "sprachen": ["Deutsch"],
                "remote": ["hybrid", "vor Ort", "remote", "unbekannt"][i],
                "erfahrung_jahre": i + 1,
            },
        )
    con.close()


def test_dashboard_laeuft(tmp_path, monkeypatch):
    pfad = tmp_path / "test.duckdb"
    _testdatenbank(pfad)
    monkeypatch.setenv("JOBMARKT_DB", str(pfad))
    app = AppTest.from_file(DASHBOARD, default_timeout=60).run()
    assert not app.exception
    kennzahlen = {m.label: m.value for m in app.metric}
    assert kennzahlen["Analysierte Anzeigen"] == "4"
    # FERCHAU-Niederlassungen und Deichmann/Deichmann SE zählen je als eine Firma
    assert kennzahlen["Arbeitgeber"] == "2"


def test_dashboard_ohne_daten(tmp_path, monkeypatch):
    """Eine leere Datenbank zeigt einen Hinweis statt eines Fehlers."""
    pfad = tmp_path / "leer.duckdb"
    storage.verbinde(pfad).close()
    monkeypatch.setenv("JOBMARKT_DB", str(pfad))
    app = AppTest.from_file(DASHBOARD, default_timeout=60).run()
    assert not app.exception
    assert app.warning
