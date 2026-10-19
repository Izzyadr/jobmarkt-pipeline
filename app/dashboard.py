"""Streamlit-Dashboard. Start mit:  uv run streamlit run app/dashboard.py"""

from pathlib import Path

import duckdb
import streamlit as st

DB_PFAD = Path(__file__).resolve().parents[1] / "data" / "jobs.duckdb"

st.set_page_config(page_title="Job-Markt NRW", layout="wide")
st.title("Was verlangt der Job-Markt für Data-Rollen?")
st.caption(
    "Stellenanzeigen der Bundesagentur für Arbeit im Umkreis von 100 km um "
    "Düsseldorf, täglich automatisch per LLM ausgewertet"
)


@st.cache_data(ttl=3600)
def lade(sql: str, params: list | None = None):
    with duckdb.connect(str(DB_PFAD), read_only=True) as con:
        return con.execute(sql, params or []).df()


# Filter in der Seitenleiste: "Sonstiges" (fachfremde Treffer) standardmäßig aus
rollen = lade("SELECT DISTINCT rolle FROM analysen ORDER BY 1")["rolle"].tolist()
standard = [r for r in rollen if r != "Sonstiges"]
auswahl = st.sidebar.multiselect("Rolle", rollen, default=standard)
if not auswahl:
    st.warning("Bitte mindestens eine Rolle auswählen.")
    st.stop()
platzhalter = ", ".join("?" * len(auswahl))
filter_sql = f"a.rolle IN ({platzhalter})"

# Kennzahlen
kpi = lade(
    f"""SELECT count(*) AS anzeigen,
               avg(CASE WHEN remote IN ('remote', 'hybrid') THEN 1 ELSE 0 END)
                   AS remote_anteil,
               count(DISTINCT s.arbeitgeber) AS arbeitgeber,
               max(a.extrahiert_am) AS stand
        FROM analysen a JOIN stellen s USING (refnr) WHERE {filter_sql}""",
    auswahl,
).iloc[0]
k1, k2, k3 = st.columns(3)
k1.metric("Analysierte Anzeigen", int(kpi["anzeigen"]))
k2.metric("Remote oder hybrid", f"{kpi['remote_anteil']:.0%}")
k3.metric("Arbeitgeber", int(kpi["arbeitgeber"]))
st.caption(f"Stand der Daten: {kpi['stand']:%d.%m.%Y}")

# Top-Tools
links, rechts = st.columns(2)
tools = lade(
    f"""SELECT tool, count(*) AS anzahl
        FROM (SELECT unnest(tools) AS tool FROM analysen a WHERE {filter_sql})
        GROUP BY tool ORDER BY anzahl DESC LIMIT 15""",
    auswahl,
)
links.subheader("Meistgefragte Tools")
links.bar_chart(tools, x="tool", y="anzahl", horizontal=True, sort="-anzahl")

# Level-Verteilung in fester Reihenfolge
level = lade(
    f"""SELECT level, count(*) AS anzahl FROM analysen a WHERE {filter_sql}
        GROUP BY level
        ORDER BY list_position(['Junior', 'Mid', 'Senior', 'Lead', 'unbekannt'], level)""",
    auswahl,
)
rechts.subheader("Erfahrungslevel")
rechts.bar_chart(level, x="level", y="anzahl", sort=False)

# Entwicklung über die Zeit: nur die letzten 12 Wochen, weil manche Anzeigen
# seit Monaten immer wieder neu geschaltet werden (Datum der Erstveröffentlichung)
trend = lade(
    f"""SELECT date_trunc('week', s.veroeffentlicht) AS woche, count(*) AS anzeigen
        FROM analysen a JOIN stellen s USING (refnr)
        WHERE {filter_sql} AND s.veroeffentlicht >= current_date - INTERVAL 84 DAY
        GROUP BY woche ORDER BY woche""",
    auswahl,
)
st.subheader("Neue Anzeigen pro Woche (letzte 12 Wochen)")
st.line_chart(trend, x="woche", y="anzeigen")

# Detailtabelle (ohne Volltexte - nur eigene Auswertung zeigen)
st.subheader("Letzte Anzeigen")
st.dataframe(
    lade(
        f"""SELECT s.veroeffentlicht, s.titel, s.arbeitgeber, s.ort,
                   a.rolle, a.level, a.remote, a.tools
            FROM analysen a JOIN stellen s USING (refnr) WHERE {filter_sql}
            ORDER BY s.veroeffentlicht DESC LIMIT 50""",
        auswahl,
    ),
    width="stretch",
    hide_index=True,
)
