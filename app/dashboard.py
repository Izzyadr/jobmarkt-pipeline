"""Streamlit-Dashboard. Start mit:  uv run streamlit run app/dashboard.py"""

from pathlib import Path

import altair as alt
import duckdb
import streamlit as st

DB_PFAD = Path(__file__).resolve().parents[1] / "data" / "jobs.duckdb"
BA_LINK = "https://www.arbeitsagentur.de/jobsuche/jobdetail/"
LEVEL = ["Junior", "Mid", "Senior", "Lead", "unbekannt"]
REMOTE = ["vor Ort", "hybrid", "remote", "unbekannt"]

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


# Alle Anzeigen mit Analyse. "Essen, Ruhr" wird zu "Essen".
ALLE = """SELECT s.refnr, s.titel, s.arbeitgeber, s.veroeffentlicht,
                 split_part(s.ort, ',', 1) AS stadt, a.*
          FROM analysen a JOIN stellen s USING (refnr)"""

# ---------- Filter in der Seitenleiste ----------
st.sidebar.header("Filter")
rollen = lade("SELECT DISTINCT rolle FROM analysen ORDER BY 1")["rolle"].tolist()
# "Sonstiges" sind fachfremde Treffer der Suche, darum standardmäßig aus
rolle = st.sidebar.multiselect(
    "Rolle", rollen, default=[r for r in rollen if r != "Sonstiges"]
)
level = st.sidebar.multiselect("Level", LEVEL, placeholder="Alle")
remote = st.sidebar.multiselect("Arbeitsort", REMOTE, placeholder="Alle")
staedte = lade(f"SELECT stadt FROM ({ALLE}) GROUP BY stadt ORDER BY count(*) DESC")
stadt = st.sidebar.multiselect("Stadt", staedte["stadt"].dropna(), placeholder="Alle")
tool_liste = lade(
    "SELECT tool FROM (SELECT unnest(tools) AS tool FROM analysen) "
    "GROUP BY tool ORDER BY count(*) DESC, tool"
)
tool = st.sidebar.selectbox(
    "Tool gefordert", tool_liste["tool"], index=None, placeholder="Alle Tools"
)

if not rolle:
    st.warning("Bitte mindestens eine Rolle auswählen.")
    st.stop()

# Aus den Filtern eine WHERE-Bedingung bauen. Werte immer als Parameter (?),
# nie direkt in den SQL-Text: Das schützt vor SQL-Injection.
bedingungen, params = [], []
for spalte, werte in [
    ("rolle", rolle),
    ("level", level),
    ("remote", remote),
    ("stadt", stadt),
]:
    if werte:
        bedingungen.append(f"{spalte} IN ({', '.join('?' * len(werte))})")
        params.extend(werte)
if tool:
    bedingungen.append("list_contains(tools, ?)")
    params.append(tool)
# Gefilterte Anzeigen, in allen folgenden Abfragen als Tabelle "g" nutzbar
G = f"g AS (SELECT * FROM ({ALLE}) WHERE {' AND '.join(bedingungen)})"

# ---------- Kennzahlen ----------
kpi = lade(
    f"""WITH {G}
        SELECT count(*) AS anzeigen,
               avg(CASE WHEN remote IN ('remote', 'hybrid') THEN 1 ELSE 0 END)
                   AS remote_anteil,
               count(DISTINCT arbeitgeber) AS arbeitgeber,
               median(erfahrung_jahre) AS erfahrung,
               count(erfahrung_jahre) AS mit_erfahrung,
               max(extrahiert_am) AS stand
        FROM g""",
    params,
).iloc[0]
if kpi["anzeigen"] == 0:
    st.info("Keine Anzeigen für diese Filter gefunden.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Analysierte Anzeigen", int(kpi["anzeigen"]))
k2.metric("Remote oder hybrid", f"{kpi['remote_anteil']:.0%}")
k3.metric("Arbeitgeber", int(kpi["arbeitgeber"]))
k4.metric(
    "Geforderte Erfahrung (Median)",
    f"{kpi['erfahrung']:.0f} Jahr{'' if kpi['erfahrung'] == 1 else 'e'}"
    if kpi["mit_erfahrung"]
    else "–",
    help=f"Nur Anzeigen mit konkreter Jahresangabe ({int(kpi['mit_erfahrung'])})",
)
st.caption(f"Stand der Daten: {kpi['stand']:%d.%m.%Y}")

tabs = st.tabs(
    [
        "Überblick",
        "Arbeitgeber",
        "Rollen im Vergleich",
        "Skills & Sprachen",
        "Städte",
        "Anzeigen",
    ]
)
tab_ueberblick, tab_firmen, tab_rollen, tab_skills, tab_orte, tab_anzeigen = tabs

# ---------- Tab: Überblick ----------
with tab_ueberblick:
    links, rechts = st.columns(2)
    tools = lade(
        f"""WITH {G}
            SELECT tool, count(*) AS anzahl
            FROM (SELECT unnest(tools) AS tool FROM g)
            GROUP BY tool ORDER BY anzahl DESC LIMIT 15""",
        params,
    )
    links.subheader("Meistgefragte Tools")
    links.bar_chart(tools, x="tool", y="anzahl", horizontal=True, sort="-anzahl")

    level_daten = lade(
        f"""WITH {G}
            SELECT level, count(*) AS anzahl FROM g GROUP BY level
            ORDER BY list_position(?, level)""",
        params + [LEVEL],
    )
    rechts.subheader("Erfahrungslevel")
    rechts.bar_chart(level_daten, x="level", y="anzahl", sort=False)

    # Nur die letzten 12 Wochen, weil manche Anzeigen seit Monaten
    # immer wieder neu geschaltet werden (Datum der Erstveröffentlichung)
    trend = lade(
        f"""WITH {G}
            SELECT date_trunc('week', veroeffentlicht) AS woche, count(*) AS anzeigen
            FROM g WHERE veroeffentlicht >= current_date - INTERVAL 84 DAY
            GROUP BY woche ORDER BY woche""",
        params,
    )
    st.subheader("Neue Anzeigen pro Woche (letzte 12 Wochen)")
    st.line_chart(trend, x="woche", y="anzeigen")

# ---------- Tab: Arbeitgeber ----------
with tab_firmen:
    st.subheader("Wer sucht gerade am meisten?")
    tage = st.segmented_control(
        "Veröffentlicht in den letzten",
        [30, 60, 90],
        default=30,
        format_func=lambda t: f"{t} Tagen",
    )
    tage = tage or 30  # falls die Auswahl abgewählt wurde
    firmen = lade(
        f"""WITH {G}
            SELECT arbeitgeber, count(*) AS anzeigen
            FROM g WHERE veroeffentlicht >= current_date - to_days(?::INTEGER)
            GROUP BY arbeitgeber ORDER BY anzeigen DESC, arbeitgeber LIMIT 15""",
        params + [tage],
    )
    if firmen.empty:
        st.info("Keine Anzeigen in diesem Zeitraum.")
    else:
        # Klick auf einen Balken zeigt darunter die Anzeigen dieser Firma
        klick = alt.selection_point(fields=["arbeitgeber"], name="firma")
        diagramm = (
            alt.Chart(firmen)
            .mark_bar()
            .encode(
                x=alt.X("anzeigen:Q", title="Anzeigen", axis=alt.Axis(tickMinStep=1)),
                y=alt.Y("arbeitgeber:N", title=None, sort="-x"),
                opacity=alt.condition(klick, alt.value(1.0), alt.value(0.4)),
                tooltip=["arbeitgeber", "anzeigen"],
            )
            .add_params(klick)
        )
        ereignis = st.altair_chart(diagramm, on_select="rerun", width="stretch")
        gewaehlt = [p["arbeitgeber"] for p in ereignis.selection.get("firma", [])]
        st.caption(
            "Klick auf einen Balken zeigt die Anzeigen der Firma. "
            "Ob eine Stelle noch offen ist, siehst du über den Link."
        )
        if gewaehlt:
            st.dataframe(
                lade(
                    f"""WITH {G}
                        SELECT veroeffentlicht, titel, stadt, level, remote,
                               ? || refnr AS link
                        FROM g WHERE arbeitgeber = ?
                          AND veroeffentlicht >= current_date - to_days(?::INTEGER)
                        ORDER BY veroeffentlicht DESC""",
                    params + [BA_LINK, gewaehlt[0], tage],
                ),
                width="stretch",
                hide_index=True,
                column_config={
                    "veroeffentlicht": st.column_config.DateColumn(
                        "Datum", format="DD.MM.YYYY"
                    ),
                    "titel": "Titel",
                    "stadt": "Stadt",
                    "level": "Level",
                    "remote": "Arbeitsort",
                    "link": st.column_config.LinkColumn(
                        "Anzeige", display_text="öffnen"
                    ),
                },
            )

# ---------- Tab: Rollen im Vergleich ----------
with tab_rollen:
    st.subheader("Welche Tools braucht welche Rolle?")
    st.caption("Anteil der Anzeigen einer Rolle, die das Tool nennen")
    vergleich = lade(
        f"""WITH {G},
            paare AS (SELECT rolle, unnest(tools) AS tool FROM g),
            top AS (SELECT tool FROM paare GROUP BY tool
                    ORDER BY count(*) DESC, tool LIMIT 12),
            n AS (SELECT rolle, count(*) AS anzeigen FROM g GROUP BY rolle)
            SELECT p.rolle || ' (' || n.anzeigen || ')' AS rolle, p.tool,
                   count(*) / any_value(n.anzeigen) AS anteil
            FROM paare p JOIN top USING (tool) JOIN n USING (rolle)
            GROUP BY p.rolle, n.anzeigen, p.tool""",
        params,
    )
    reihenfolge = vergleich.groupby("tool")["anteil"].sum().sort_values().index
    basis = alt.Chart(vergleich).encode(
        x=alt.X("rolle:N", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("tool:N", title=None, sort=list(reversed(reihenfolge))),
    )
    heatmap = basis.mark_rect().encode(
        color=alt.Color("anteil:Q", title="Anteil", legend=alt.Legend(format="%")),
        tooltip=["rolle", "tool", alt.Tooltip("anteil:Q", format=".0%")],
    )
    werte = basis.mark_text().encode(
        text=alt.Text("anteil:Q", format=".0%"),
        color=alt.condition(
            "datum.anteil > 0.4", alt.value("white"), alt.value("black")
        ),
    )
    st.altair_chart(heatmap + werte, width="stretch")
    st.caption(
        "In Klammern: Anzahl der Anzeigen. Bei wenigen Anzeigen sind die Anteile unsicher."
    )

# ---------- Tab: Skills & Sprachen ----------
with tab_skills:
    links, rechts = st.columns(2)
    skills = lade(
        f"""WITH {G}
            SELECT skill, count(*) AS anzahl
            FROM (SELECT unnest(skills) AS skill FROM g)
            GROUP BY skill ORDER BY anzahl DESC LIMIT 15""",
        params,
    )
    links.subheader("Meistgefragte Skills")
    links.bar_chart(skills, x="skill", y="anzahl", horizontal=True, sort="-anzahl")

    sprachen = lade(
        f"""WITH {G}
            SELECT sprache, count(*) / (SELECT count(*) FROM g) AS anteil
            FROM (SELECT unnest(sprachen) AS sprache FROM g)
            WHERE sprache <> 'unbekannt'
            GROUP BY sprache ORDER BY anteil DESC LIMIT 8""",
        params,
    )
    rechts.subheader("Geforderte Sprachen")
    rechts.altair_chart(
        alt.Chart(sprachen)
        .mark_bar()
        .encode(
            x=alt.X("anteil:Q", title="Anteil der Anzeigen", axis=alt.Axis(format="%")),
            y=alt.Y("sprache:N", title=None, sort="-x"),
            tooltip=["sprache", alt.Tooltip("anteil:Q", format=".0%")],
        ),
        width="stretch",
    )

# ---------- Tab: Städte ----------
with tab_orte:
    st.subheader("Wo gibt es die meisten Stellen?")
    orte = lade(
        f"""WITH {G}
            SELECT stadt, count(*) AS anzeigen,
                   avg(CASE WHEN remote IN ('remote', 'hybrid') THEN 1 ELSE 0 END)
                       AS remote_anteil
            FROM g WHERE stadt IS NOT NULL
            GROUP BY stadt ORDER BY anzeigen DESC LIMIT 15""",
        params,
    )
    st.bar_chart(orte, x="stadt", y="anzeigen", horizontal=True, sort="-anzeigen")
    st.dataframe(
        orte,
        hide_index=True,
        column_config={
            "stadt": "Stadt",
            "anzeigen": "Anzeigen",
            "remote_anteil": st.column_config.ProgressColumn(
                "Remote oder hybrid", format="percent", min_value=0, max_value=1
            ),
        },
    )

# ---------- Tab: Anzeigen ----------
with tab_anzeigen:
    st.subheader("Anzeigen")
    st.dataframe(
        lade(
            f"""WITH {G}
                SELECT veroeffentlicht, titel, arbeitgeber, stadt, rolle, level,
                       remote, tools, ? || refnr AS link
                FROM g ORDER BY veroeffentlicht DESC LIMIT 200""",
            params + [BA_LINK],
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "veroeffentlicht": st.column_config.DateColumn(
                "Datum", format="DD.MM.YYYY"
            ),
            "titel": "Titel",
            "arbeitgeber": "Arbeitgeber",
            "stadt": "Stadt",
            "rolle": "Rolle",
            "level": "Level",
            "remote": "Arbeitsort",
            "tools": "Tools",
            "link": st.column_config.LinkColumn("Anzeige", display_text="öffnen"),
        },
    )
    st.caption(
        "Die neuesten 200 Anzeigen. Der Link führt zur Original-Anzeige bei der Bundesagentur."
    )
