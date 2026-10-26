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

# Gleiche Skills in verschiedenen Schreibweisen (klein geschrieben) -> ein Name
SKILL_ALIASE = {
    "etl": "ETL/ELT",
    "etl-prozesse": "ETL/ELT",
    "etl/elt-prozesse": "ETL/ELT",
    "etl-pipelines": "ETL/ELT",
    "etl/elt-pipelines": "ETL/ELT",
    "data pipelines": "Datenpipelines",
    "stakeholder management": "Stakeholder-Management",
    "infrastructure-as-code": "Infrastructure as Code",
    "cloud-architekturen": "Cloud-Architektur",
    "lakehouse-architekturen": "Lakehouse-Architektur",
    "software-architektur": "Softwarearchitektur",
    "kommunikationsstärke": "Kommunikation",
    "kommunikationsfähigkeit": "Kommunikation",
    "analytische fähigkeiten": "Analytisches Denken",
    "analytisches denkvermögen": "Analytisches Denken",
    "performanceoptimierung": "Performance-Optimierung",
    "performance-tuning": "Performance-Optimierung",
    "generative ki": "Generative AI",
    "data warehouse": "Data Warehousing",
    "datenqualitätssicherung": "Datenqualität",
    "datenqualitätsmanagement": "Datenqualität",
    "datenqualitätsprüfung": "Datenqualität",
    "dashboards": "Dashboard-Entwicklung",
    "dashboard-erstellung": "Dashboard-Entwicklung",
    "reporting und dashboards": "Reporting",
    "dashboards und reporting": "Reporting",
    "moderation von workshops": "Workshop-Moderation",
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
    """Vereinheitlicht Skill-Namen, entfernt Dubletten, begrenzt die Anzahl."""
    einheitlich = [SKILL_ALIASE.get(s.strip().lower(), s) for s in skills]
    return normalisiere(einheitlich)[:MAX_SKILLS]
