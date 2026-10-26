# Job-Markt-Analyse NRW

[![Tests](https://github.com/Izzyadr/jobmarkt-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/Izzyadr/jobmarkt-pipeline/actions/workflows/tests.yml)
[![Tägliche Pipeline](https://github.com/Izzyadr/jobmarkt-pipeline/actions/workflows/pipeline.yml/badge.svg)](https://github.com/Izzyadr/jobmarkt-pipeline/actions/workflows/pipeline.yml)

Automatische Pipeline, die täglich Stellenanzeigen für Data-Rollen sammelt,
per LLM in strukturierte Daten verwandelt und als Live-Dashboard veröffentlicht.

**Live-Dashboard:** https://jobmarkt-nrw.streamlit.app

![Dashboard](docs/dashboard.png)

## Ergebnisse (Stand: 26.10.2026)

- **429 Anzeigen** im Umkreis von 100 km um Düsseldorf ausgewertet, davon **201 Data-Rollen** bei 149 Arbeitgebern
- Häufigste Tools in Data-Rollen: **SQL (47 %)**, **Python (40 %)**, **Power BI (32 %)**
- **Data Analyst** (55 Anzeigen): SQL in 56 %, Power BI in 49 %, Python in 31 %
- **Data Engineer** (76 Anzeigen): Python in 68 %, SQL in 57 %, Azure in 37 %, Databricks in 36 %
- **65 %** der Stellen bieten hybrides oder Remote-Arbeiten
- Geforderte Erfahrung: im Median **3 Jahre** (bei 47 Anzeigen mit konkreter Angabe)

![Welche Tools braucht welche Rolle?](docs/rollen-vergleich.png)

Die Daten werden seit dem 19.10.2026 gesammelt. Die Zahlen sind eine
Momentaufnahme und werden mit jedem Tag belastbarer.

## Architektur

```mermaid
flowchart LR
    A[BA-Jobsuche-API] --> B[fetch.py<br>Abruf]
    B --> C[(DuckDB)]
    C <--> D[extract.py<br>LLM + Schema]
    C <--> H[bereinigung.py<br>Regeln im Code]
    C --> E[GitHub-Repo]
    E --> F[Streamlit<br>Dashboard]
    G[GitHub Actions<br>täglich 07:15] -.-> B
```

1. **Abruf:** Täglich werden neue Anzeigen der letzten 7 Tage geholt (mit Pagination und Retry). Bekannte Anzeigen werden über die Referenznummer übersprungen, die Pipeline ist idempotent. Ein Titel-Filter sortiert fachfremde Treffer vor der LLM-Analyse aus (geprüft an 449 Anzeigen: 94 % der passenden bleiben, gut die Hälfte der fachfremden fällt weg). Neu geschaltete Kopien derselben Stelle (gleicher Titel und Arbeitgeber) werden nur einmal gezählt.
2. **Extraktion:** Claude Haiku füllt pro Anzeige ein festes Schema aus (Rolle, Level, Tools, Skills, Sprachen, Remote, Erfahrungsjahre). Structured Outputs und Pydantic garantieren gültige Werte.
3. **Bereinigung:** Feste Regeln im Code vereinheitlichen Tool- und Skill-Namen (z. B. „Microsoft Fabric“ → „Fabric“, „ETL-Prozesse“ → „ETL/ELT“) und begrenzen die Listen. Neue Regeln werden bei jedem Lauf auch auf alte Daten angewendet, ohne neue LLM-Kosten.
4. **Automatisierung:** GitHub Actions führt Tests und Pipeline täglich aus und committet die aktualisierte Datenbank. Jeder Push wird zusätzlich mit ruff und pytest geprüft.
5. **Dashboard:** Streamlit liest die Datenbank direkt aus dem Repository. Filter nach Rolle, Level, Arbeitsort, Stadt und Tool; Vergleich der Rollen, aktivste Arbeitgeber mit Link zur Original-Anzeige. Niederlassungen einer Firma (z. B. „FERCHAU GmbH Niederlassung Köln“) werden zusammengefasst.

## Technik

Python · DuckDB · Anthropic API (Structured Outputs) · Pydantic ·
GitHub Actions · Streamlit · pytest · ruff · uv

## Qualität der KI-Extraktion

Stichprobe von 20 Anzeigen gegen den Originaltext geprüft
([docs/stichprobe.csv](docs/stichprobe.csv)):

| Feld   | Trefferquote |
|--------|--------------|
| Rolle  | 90 %         |
| Level  | 80 %         |
| Remote | 90 %         |
| Tools  | 95 %         |

**Verbesserung durch Prompt-Version 2:** Die erste Version hat Homeoffice-Angaben
im Abschnitt „Wir bieten“ oft übersehen. Ein Abgleich mit dem Anzeigentext zeigte
25 falsche „unbekannt“-Werte. Nach klaren Regeln pro Feld waren es noch 3.

## Projektstruktur

```
src/jobmarkt/
  fetch.py         Abruf über die BA-Jobsuche-API
  extract.py       LLM-Extraktion mit festem Schema
  bereinigung.py   Regeln für Tool- und Skill-Namen
  storage.py       DuckDB-Tabellen, Dubletten-Erkennung
  pipeline.py      Ablauf: Abruf → Filter → Analyse → Bereinigung
app/dashboard.py   Streamlit-Dashboard
tests/             pytest (ohne Internet und API-Key), inkl. Dashboard-Rauchtest
```

## Lokal ausführen

```bash
uv sync
cp .env.example .env   # ANTHROPIC_API_KEY eintragen
uv run pytest
uv run python -m jobmarkt.pipeline
uv run streamlit run app/dashboard.py
```

## Was ich gelernt habe

- **Inoffizielle APIs ändern sich:** Während des Projekts hat die Bundesagentur die
  Suche von v4 auf v6 umgestellt (neue Feldnamen). Tests auf die Feldzuordnung
  machen solche Änderungen sofort sichtbar.
- **LLM-Ergebnisse muss man messen:** Erst die Stichprobe hat gezeigt, wo der
  Prompt ungenau war.
- **Erst filtern, dann bezahlen:** Über die Hälfte der Suchtreffer war fachfremd.
  Ein einfacher Titel-Filter, an den vorhandenen Daten geprüft, spart diese
  LLM-Aufrufe, ohne nennenswert passende Anzeigen zu verlieren.
- **Feste Regeln gehören in den Code:** Vorgaben wie „höchstens 10 Tools“ befolgt
  das LLM nicht immer zuverlässig, Code dagegen schon.

## Nächste Schritte

- Level- und Remote-Regeln weiter schärfen und die Qualität neu messen
- Titel-Filter regelmäßig an neuen Daten nachprüfen
- Vergleich weiterer Regionen (z. B. Berlin, München)
- Auswertung von Gehaltsangaben

## Datenquelle

Stellenanzeigen der [Bundesagentur für Arbeit](https://www.arbeitsagentur.de/jobsuche/),
Zugang dokumentiert vom Projekt [bundesAPI](https://github.com/bundesAPI/jobsuche-api).
Nicht-kommerzielles Lernprojekt. Es werden nur eigene Auswertungen veröffentlicht,
keine vollständigen Anzeigentexte.
