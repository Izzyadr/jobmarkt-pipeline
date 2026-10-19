"""Abruf von Stellenanzeigen über die Jobsuche-API der Bundesagentur."""

import base64
import logging
import time

import requests

from jobmarkt import config

log = logging.getLogger(__name__)
HEADERS = {"X-API-Key": config.BA_API_KEY}


def _get(pfad: str, params: dict | None = None) -> requests.Response:
    """GET-Anfrage mit bis zu 3 Versuchen (bei Überlastung oder Verbindungsfehler)."""
    url = f"{config.BA_BASIS_URL}{pfad}"
    for versuch in range(1, 4):
        wartezeit = 2**versuch
        try:
            antwort = requests.get(url, headers=HEADERS, params=params, timeout=30)
        except requests.ConnectionError:
            log.warning("Verbindungsfehler, neuer Versuch in %s s", wartezeit)
            time.sleep(wartezeit)
            continue
        if antwort.status_code in (429, 500, 502, 503):
            log.warning(
                "Status %s, neuer Versuch in %s s", antwort.status_code, wartezeit
            )
            time.sleep(wartezeit)
            continue
        return antwort
    # Nach 3 Fehlversuchen: letzter Versuch ohne Abfangen, damit der Fehler sichtbar wird
    return requests.get(url, headers=HEADERS, params=params, timeout=30)


def suche_stellen(was: str) -> list[dict]:
    """Sucht Stellen zu einem Suchbegriff und gibt die Trefferliste zurück."""
    alle = []
    for seite in range(1, config.MAX_SEITEN + 1):
        params = {
            "was": was,
            "wo": config.ORT,
            "umkreis": config.UMKREIS_KM,
            "angebotsart": 1,  # 1 = Arbeit (keine Ausbildung/Praktika)
            "veroeffentlichtseit": config.TAGE_ZURUECK,
            "page": seite,
            "size": config.SEITEN_GROESSE,
        }
        antwort = _get("/pc/v6/jobs", params)
        antwort.raise_for_status()
        treffer = antwort.json().get("ergebnisliste", [])
        alle.extend(treffer)
        log.info("'%s' Seite %s: %s Treffer", was, seite, len(treffer))
        if len(treffer) < config.SEITEN_GROESSE:
            break  # letzte Seite erreicht
        time.sleep(0.5)  # höflich bleiben
    return alle


def hole_beschreibung(refnr: str) -> str | None:
    """Holt den Volltext einer Anzeige. Die refnr muss Base64-kodiert werden."""
    code = base64.b64encode(refnr.encode()).decode()
    antwort = _get(f"/pc/v4/jobdetails/{code}")
    if antwort.status_code != 200:
        log.warning("Keine Details für %s (Status %s)", refnr, antwort.status_code)
        return None
    return antwort.json().get("stellenangebotsBeschreibung")


def vereinfache(anzeige: dict, suchbegriff: str) -> dict:
    """Reduziert die API-Antwort auf die Felder, die wir speichern."""
    lokationen = anzeige.get("stellenlokationen") or [{}]
    adresse = lokationen[0].get("adresse") or {}
    return {
        "refnr": anzeige.get("referenznummer"),
        "titel": anzeige.get("stellenangebotsTitel"),
        "beruf": anzeige.get("hauptberuf"),
        "arbeitgeber": anzeige.get("firma"),
        "ort": adresse.get("ort"),
        "region": adresse.get("region"),
        "veroeffentlicht": anzeige.get("datumErsteVeroeffentlichung"),
        "suchbegriff": suchbegriff,
    }
