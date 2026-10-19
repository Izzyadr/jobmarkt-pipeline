"""Einstiegspunkt: ruft alle Schritte nacheinander auf.

Start mit:  uv run python -m jobmarkt.pipeline
"""

import argparse
import logging

from jobmarkt import bereinigung, config, fetch, storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")


def schritt_abrufen(con) -> int:
    """Phase 1: neue Anzeigen holen und speichern."""
    neu = 0
    for begriff in config.SUCHBEGRIFFE:
        for anzeige in fetch.suche_stellen(begriff):
            stelle = fetch.vereinfache(anzeige, begriff)
            if not stelle["refnr"] or storage.ist_bekannt(con, stelle["refnr"]):
                continue
            stelle["beschreibung"] = fetch.hole_beschreibung(stelle["refnr"])
            storage.speichere_stelle(con, stelle)
            neu += 1
    return neu


def schritt_analysieren(con) -> int:
    """Phase 2: offene Anzeigen per LLM strukturieren."""
    # Erst hier importieren: Phase 1 braucht keinen API-Key
    import anthropic
    from pydantic import ValidationError

    from jobmarkt import extract

    fertig = 0
    offen = storage.offene_analysen(con, config.MAX_EXTRAKTIONEN_PRO_LAUF)
    for refnr, titel, beschreibung in offen:
        try:
            analyse = extract.analysiere(titel, beschreibung)
            storage.speichere_analyse(con, refnr, analyse.model_dump())
            fertig += 1
        # Eine fehlerhafte Anzeige darf den ganzen Lauf nicht stoppen
        except (anthropic.APIError, ValidationError, ValueError) as fehler:
            log.error("Analyse fehlgeschlagen für %s: %s", refnr, fehler)
    return fertig


def schritt_bereinigen(con) -> int:
    """Phase 3: aktuelle Bereinigungsregeln auf alle Analysen anwenden.

    So profitieren auch ältere Daten von neuen Regeln, ohne neue LLM-Kosten.
    """
    geaendert = 0
    for refnr, tools, skills in storage.alle_listen(con):
        neue_tools = bereinigung.bereinige_tools(tools)
        neue_skills = bereinigung.bereinige_skills(skills)
        if neue_tools != tools or neue_skills != skills:
            storage.aktualisiere_listen(con, refnr, neue_tools, neue_skills)
            geaendert += 1
    return geaendert


def main() -> None:
    parser = argparse.ArgumentParser(description="Job-Markt-Pipeline")
    parser.add_argument("--ohne-llm", action="store_true", help="nur Daten abrufen")
    args = parser.parse_args()

    con = storage.verbinde()
    neu = schritt_abrufen(con)
    log.info("Neue Anzeigen gespeichert: %s", neu)
    if not args.ohne_llm:
        log.info("Analysiert: %s", schritt_analysieren(con))
    log.info("Bereinigte Analysen: %s", schritt_bereinigen(con))
    gesamt = con.execute("SELECT count(*) FROM stellen").fetchone()[0]
    log.info("Anzeigen in der Datenbank: %s", gesamt)
    con.close()


if __name__ == "__main__":
    main()
