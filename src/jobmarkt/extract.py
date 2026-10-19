"""LLM-Extraktion: macht aus Freitext ein festes, prüfbares Datenschema."""

from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from jobmarkt import config
from jobmarkt.bereinigung import bereinige_skills, bereinige_tools


class StellenAnalyse(BaseModel):
    """Das Schema, das das LLM für jede Anzeige ausfüllen muss."""

    rolle: Literal[
        "Data Analyst",
        "Data Engineer",
        "Data Scientist",
        "BI Developer",
        "Automation Engineer",
        "Controller",
        "Sonstiges",
    ]
    level: Literal["Junior", "Mid", "Senior", "Lead", "unbekannt"]
    tools: list[str] = Field(
        description="Konkrete Software/Tools, z. B. Python, SQL, Power BI"
    )
    skills: list[str] = Field(
        description="Fachliche Fähigkeiten, z. B. Datenmodellierung"
    )
    sprachen: list[str] = Field(
        description="Geforderte Sprachen, z. B. Deutsch, Englisch"
    )
    remote: Literal["vor Ort", "hybrid", "remote", "unbekannt"]
    erfahrung_jahre: int | None = Field(
        description="Mindestjahre Erfahrung, sonst null"
    )


ANWEISUNG = """Du analysierst deutsche Stellenanzeigen. Regeln:
- Nutze nur Informationen, die wirklich in der Anzeige stehen. Nichts erfinden.
- Lies die ganze Anzeige, auch Abschnitte wie "Wir bieten" oder "Benefits".

remote:
- "hybrid": Die Anzeige erwähnt Homeoffice, mobiles Arbeiten, Remote-Anteile oder flexible Arbeitsorte, zusätzlich zum Büro.
- "remote": vollständig oder überwiegend von zu Hause / ortsunabhängig.
- "vor Ort": ausdrücklich nur vor Ort, oder die Tätigkeit ist klar an einen Ort gebunden (z. B. Werk, Labor, Baustelle).
- "unbekannt": nur wenn nichts davon erkennbar ist.

level:
- "Junior": Berufseinsteiger, Absolventen, erste Berufserfahrung, Werkstudent, Trainee.
- "Mid": mehrjährige Berufserfahrung (etwa 2-5 Jahre) ohne Senior-Bezeichnung.
- "Senior": "Senior" im Titel oder umfangreiche/langjährige Erfahrung (etwa 5+ Jahre), Experte.
- "Lead": Teamleitung, Head of, Lead, Führungsverantwortung.
- "unbekannt": nur wenn nichts davon erkennbar ist.

tools:
- Nur konkrete Software, Programmiersprachen, Plattformen. Keine Fähigkeiten oder Methoden.
- Einheitliche Schreibweise: Lass "Microsoft" und "MS" vor Produktnamen weg ("Azure", "Excel", "Fabric", "Power BI", "SQL Server").
- Alle anderen Produktnamen bleiben vollständig, z. B. "SAP BW", "SAP S/4HANA", "SAP Analytics Cloud", "Google Cloud", "AWS".
- Höchstens 10 Tools und 8 Skills, die wichtigsten zuerst.

Wenn etwas nicht erkennbar ist: "unbekannt", leere Liste oder null."""

_client = None


def _hole_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # liest ANTHROPIC_API_KEY aus der Umgebung
    return _client


def analysiere(titel: str, beschreibung: str) -> StellenAnalyse:
    """Schickt eine Anzeige an das LLM und bekommt ein geprüftes Ergebnis zurück."""
    text = beschreibung[: config.MAX_ZEICHEN_BESCHREIBUNG]
    antwort = _hole_client().messages.parse(
        model=config.LLM_MODELL,
        max_tokens=2048,
        system=ANWEISUNG,
        messages=[{"role": "user", "content": f"Titel: {titel}\n\n{text}"}],
        output_format=StellenAnalyse,  # Antwort muss genau diesem Schema folgen
        output_config={"effort": "low"},  # einfache Aufgabe: wenig Nachdenken reicht
    )
    analyse = antwort.parsed_output
    if analyse is None:  # z. B. Antwort abgebrochen oder abgelehnt
        raise ValueError(f"Keine gültige Antwort (stop_reason={antwort.stop_reason})")
    analyse.tools = bereinige_tools(analyse.tools)
    analyse.skills = bereinige_skills(analyse.skills)
    return analyse
