"""Bereinigung der LLM-Ergebnisse.

Feste Regeln stehen hier im Code statt im Prompt: Code hält sie immer ein,
das LLM nur meistens.
"""

MAX_TOOLS = 10
MAX_SKILLS = 8

# Andere Schreibweisen (klein geschrieben) -> einheitlicher Name
TOOL_ALIASE = {
    "microsoft azure": "Azure",
    "ms azure": "Azure",
    "azure databricks": "Databricks",
    "microsoft fabric": "Fabric",
    "ms fabric": "Fabric",
    "microsoft power bi": "Power BI",
    "ms power bi": "Power BI",
    "powerbi": "Power BI",
    "microsoft excel": "Excel",
    "ms excel": "Excel",
    "microsoft sql server": "SQL Server",
    "ms sql server": "SQL Server",
    "mssql": "SQL Server",
    "ms office": "Microsoft Office",
    "apache spark": "Spark",
    "apache airflow": "Airflow",
    "apache kafka": "Kafka",
    "gcp": "Google Cloud",
    "google cloud platform": "Google Cloud",
    "amazon web services": "AWS",
    "sac": "SAP Analytics Cloud",
    "postgres": "PostgreSQL",
}


def normalisiere(liste: list[str]) -> list[str]:
    """Entfernt Leerzeichen und Dubletten, behält die Reihenfolge."""
    gesehen, ergebnis = set(), []
    for eintrag in liste:
        sauber = eintrag.strip()
        if sauber and sauber.lower() not in gesehen:
            gesehen.add(sauber.lower())
            ergebnis.append(sauber)
    return ergebnis


def bereinige_tools(tools: list[str]) -> list[str]:
    """Vereinheitlicht Tool-Namen, entfernt Dubletten, begrenzt die Anzahl."""
    einheitlich = [TOOL_ALIASE.get(t.strip().lower(), t) for t in tools]
    return normalisiere(einheitlich)[:MAX_TOOLS]


def bereinige_skills(skills: list[str]) -> list[str]:
    return normalisiere(skills)[:MAX_SKILLS]
