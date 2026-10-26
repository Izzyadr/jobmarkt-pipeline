"""Zentrale Einstellungen der Pipeline."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # liest die .env-Datei (ANTHROPIC_API_KEY)

# Projektordner = zwei Ebenen über dieser Datei (src/jobmarkt/config.py)
PROJEKT_ORDNER = Path(__file__).resolve().parents[2]
DB_PFAD = PROJEKT_ORDNER / "data" / "jobs.duckdb"

# Bundesagentur für Arbeit - Jobsuche-API
BA_BASIS_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
BA_API_KEY = "jobboerse-jobsuche"  # öffentlicher Client-Key, kein Geheimnis

# Was soll gesucht werden?
SUCHBEGRIFFE = [
    "Data Analyst",
    "Data Engineer",
    "Business Intelligence",
    "Prozessautomatisierung",
]
# Nur Anzeigen, deren Titel eines dieser Muster enthält, werden gespeichert
# und per LLM analysiert. Ohne Filter war über die Hälfte fachfremd
# (z. B. "Turbine Design Engineer"). Geprüft an 449 Anzeigen: 94 % der
# passenden bleiben, 54 % der fachfremden fallen weg.
TITEL_MUSTER = (
    r"data|daten|analy|\bbi\b|business intelligence|power ?bi|reporting|"
    r"controll|steuerung|forecast|prognose|planning|fi/co|automati|\brpa\b|"
    r"etl|\bsql\b|python|machine learning|\bml\b|\bki\b|\bai\b|statisti|"
    r"dashboard|database|insights|data warehouse|sap bw|datasphere|tableau|qlik"
)
ORT = "Düsseldorf"
UMKREIS_KM = 100
TAGE_ZURUECK = 7  # nur Anzeigen der letzten 7 Tage
MAX_SEITEN = 4  # pro Suchbegriff höchstens 4 Seiten
SEITEN_GROESSE = 50  # Anzeigen pro Seite

# LLM-Einstellungen
LLM_MODELL = "claude-haiku-5-5"
MAX_EXTRAKTIONEN_PRO_LAUF = 60  # Kostenbremse
MAX_ZEICHEN_BESCHREIBUNG = 6000
