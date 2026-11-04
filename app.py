"""AgriData Explorer - Streamlit + Plotly dashboard.   Run:  streamlit run app.py"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from db import connect
from queries import QUERIES

st.set_page_config(page_title="AgriData Explorer", page_icon="🌾", layout="wide")


@st.cache_data(ttl=600)
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    con = connect()
    try:
        return pd.read_sql(sql, con, params=params)
    finally:
        con.close()


# ---------------------------------------------------------------- helpers
def top_states(crop, n, last_years=None):
    cond = f"AND year > (SELECT MAX(year) FROM crop_stats) - {last_years}" if last_years else ""
    return q(f"""SELECT state_name, ROUND(SUM(production_1000t), 1) AS production_1000t
                 FROM v_crop_stats WHERE crop_name = ? {cond}
                 GROUP BY state_name ORDER BY 2 DESC LIMIT {n}""", (crop,))


def yearly(crop, state=None, years=None):
    sql = "SELECT year, SUM(production_1000t) AS production_1000t, SUM(area_1000ha) AS area_1000ha FROM v_crop_stats WHERE crop_name = ?"
    params = [crop]
    if state:
        sql += " AND state_name = ?"; params.append(state)
    if years:
        sql += f" AND year > (SELECT MAX(year) FROM crop_stats) - {years}"
    return q(sql + " GROUP BY year ORDER BY year", tuple(params))


def bar(df, x, y, title, **kw):
    return px.bar(df, x=x, y=y, title=title, text_auto=".3s", **kw)


STATES = q("SELECT state_name FROM states ORDER BY 1").state_name.tolist()
CROPS = q("SELECT crop_name FROM crops ORDER BY 1").crop_name.tolist()
YMIN, YMAX = q("SELECT MIN(year) a, MAX(year) b FROM crop_stats").iloc[0]
YMIN, YMAX = int(YMIN), int(YMAX)

st.sidebar.title("🌾 AgriData Explorer")
page = st.sidebar.radio("Menu", ["Overview", "EDA charts", "SQL answers", "Yield forecast", "About the data"])

# ---------------------------------------------------------------- Overview
if page == "Overview":
    st.title("🌾 Indian Agriculture - Overview")
    c1, c2, c3 = st.columns(3)
    crop = c1.selectbox("Crop", CROPS, index=CROPS.index("Rice"))
    states = c2.multiselect("State (empty = all)", STATES)
    years = c3.slider("Years", YMIN, YMAX, (YMIN, YMAX))
    where, params = "crop_name = ? AND year BETWEEN ? AND ?", [crop, years[0], years[1]]
    if states:
        where += f" AND state_name IN ({','.join('?' * len(states))})"; params += states
    base = q(f"""SELECT state_name, dist_name, year, area_1000ha, production_1000t
                 FROM v_crop_stats WHERE {where}""", tuple(params))
    if base.empty:
        st.warning("No data for this selection."); st.stop()
    area, prod = base.area_1000ha.sum(), base.production_1000t.sum()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total production (1000 t)", f"{prod:,.0f}")
    k2.metric("Total area (1000 ha-years)", f"{area:,.0f}")
    k3.metric("Weighted yield (kg/ha)", f"{1000 * prod / area:,.0f}" if area else "n/a")
    k4.metric("Districts covered", base.dist_name.nunique())
    left, right = st.columns(2)
    trend = base.groupby("year", as_index=False).production_1000t.sum()
    left.plotly_chart(px.line(trend, x="year", y="production_1000t", title=f"{crop} production over time (1000 t)"),
                      use_container_width=True)
    bys = base.groupby("state_name", as_index=False).production_1000t.sum().nlargest(10, "production_1000t")
    right.plotly_chart(bar(bys, "state_name", "production_1000t", "Top states by production (1000 t)"),
                       use_container_width=True)
    heat = base.groupby(["state_name", "year"], as_index=False).production_1000t.sum()
    st.plotly_chart(px.density_heatmap(heat, x="year", y="state_name", z="production_1000t", histfunc="sum",
                                       title="Heatmap: production by state and year"), use_container_width=True)

# ---------------------------------------------------------------- EDA
elif page == "EDA charts":
    st.title("📈 Exploratory Data Analysis")
    names = ["1. Top 7 rice-producing states", "2. Top 5 wheat states (bar + share %)",
             "3. Oilseed production - top 5 states", "4. Top 7 sunflower states",
             "5. Sugarcane production - last 50 years", "6. Rice vs wheat production - last 50 years",
             "7. Rice production by West Bengal districts", "8. Top 10 wheat years in Uttar Pradesh",
             "9. Millet production - last 50 years", "10. Sorghum (Kharif vs Rabi) by state",
             "11. Top 7 groundnut states", "12. Soybean: top 5 states and yield efficiency",
             "13. Oilseed production in major states over time", "14. Area vs production (rice, wheat, maize)",
             "15. Rice vs wheat yield across states"]
    pick = st.selectbox("Choose a chart", names)
    n = int(pick.split(".")[0])
    if n == 1:
        st.plotly_chart(bar(top_states("Rice", 7), "state_name", "production_1000t", "Top 7 rice states - total production (1000 t)"), use_container_width=True)
    elif n == 2:
        d = top_states("Wheat", 5)
        a, b = st.columns(2)
        a.plotly_chart(bar(d, "state_name", "production_1000t", "Top 5 wheat states (1000 t)"), use_container_width=True)
        b.plotly_chart(px.pie(d, names="state_name", values="production_1000t", title="Share among the top 5 (%)"), use_container_width=True)
    elif n == 3:
        st.plotly_chart(bar(top_states("Oilseeds", 5), "state_name", "production_1000t", "Oilseed production - top 5 states (1000 t)"), use_container_width=True)
    elif n == 4:
        st.plotly_chart(bar(top_states("Sunflower", 7), "state_name", "production_1000t", "Top 7 sunflower states (1000 t)"), use_container_width=True)
    elif n == 5:
        st.plotly_chart(px.line(yearly("Sugarcane", years=50), x="year", y="production_1000t", title="India - sugarcane production, last 50 years (1000 t)"), use_container_width=True)
    elif n == 6:
        r, w = yearly("Rice", years=50), yearly("Wheat", years=50)
        fig = go.Figure([go.Scatter(x=r.year, y=r.production_1000t, name="Rice"), go.Scatter(x=w.year, y=w.production_1000t, name="Wheat")])
        fig.update_layout(title="Rice vs wheat production, last 50 years (1000 t)")
        st.plotly_chart(fig, use_container_width=True)
    elif n == 7:
        d = q("""SELECT dist_name, ROUND(SUM(production_1000t), 1) AS production_1000t FROM v_crop_stats
                 WHERE crop_name = 'Rice' AND state_name = 'West Bengal' GROUP BY dist_name ORDER BY 2 DESC""")
        st.plotly_chart(bar(d, "dist_name", "production_1000t", "Rice production by West Bengal district (all years, 1000 t)"), use_container_width=True)
    elif n == 8:
        d = yearly("Wheat", "Uttar Pradesh").nlargest(10, "production_1000t")
        d["year"] = d.year.astype(str)
        st.plotly_chart(bar(d, "year", "production_1000t", "Top 10 wheat production years - Uttar Pradesh (1000 t)"), use_container_width=True)
    elif n == 9:
        fig = go.Figure()
        for c in ["Pearl Millet", "Finger Millet"]:
            d = yearly(c, years=50); fig.add_trace(go.Scatter(x=d.year, y=d.production_1000t, name=c))
        fig.update_layout(title="Millet production, last 50 years (1000 t)")
        st.plotly_chart(fig, use_container_width=True)
    elif n == 10:
        d = q("""SELECT state_name, crop_name, ROUND(SUM(production_1000t), 1) AS production_1000t FROM v_crop_stats
                 WHERE crop_name IN ('Kharif Sorghum', 'Rabi Sorghum') GROUP BY state_name, crop_name""")
        order = d.groupby("state_name").production_1000t.sum().nlargest(10).index
        st.plotly_chart(px.bar(d[d.state_name.isin(order)], x="state_name", y="production_1000t", color="crop_name",
                               barmode="group", title="Sorghum production by state: Kharif vs Rabi (1000 t)"), use_container_width=True)
    elif n == 11:
        st.plotly_chart(bar(top_states("Groundnut", 7), "state_name", "production_1000t", "Top 7 groundnut states (1000 t)"), use_container_width=True)
    elif n == 12:
        d = q("""SELECT state_name, ROUND(SUM(production_1000t), 1) AS production_1000t,
                        ROUND(1000.0 * SUM(production_1000t) / SUM(area_1000ha), 1) AS yield_kg_ha
                 FROM v_crop_stats WHERE crop_name = 'Soyabean' AND area_1000ha > 0 AND production_1000t IS NOT NULL
                 GROUP BY state_name ORDER BY 2 DESC LIMIT 5""")
        a, b = st.columns(2)
        a.plotly_chart(bar(d, "state_name", "production_1000t", "Soybean production - top 5 states (1000 t)"), use_container_width=True)
        b.plotly_chart(bar(d, "state_name", "yield_kg_ha", "Yield efficiency (kg/ha)"), use_container_width=True)
    elif n == 13:
        top = top_states("Oilseeds", 5).state_name.tolist()
        d = q(f"""SELECT year, state_name, SUM(production_1000t) AS production_1000t FROM v_crop_stats
                  WHERE crop_name = 'Oilseeds' AND state_name IN ({','.join('?' * len(top))}) GROUP BY year, state_name""", tuple(top))
        st.plotly_chart(px.line(d, x="year", y="production_1000t", color="state_name", title="Oilseed production in the major states (1000 t)"), use_container_width=True)
    elif n == 14:
        crop = st.radio("Crop", ["Rice", "Wheat", "Maize"], horizontal=True)
        d = q("""SELECT state_name, dist_name, year, area_1000ha, production_1000t FROM v_crop_stats
                 WHERE crop_name = ? AND area_1000ha > 0 AND production_1000t > 0""", (crop,))
        d = d.sample(min(len(d), 4000), random_state=1)
        fig = px.scatter(d, x="area_1000ha", y="production_1000t", color="state_name", opacity=0.6,
                         hover_data=["dist_name", "year"], title=f"{crop}: area vs production (each dot = one district-year)")
        slope, icpt = np.polyfit(d.area_1000ha, d.production_1000t, 1)
        xs = np.array([0, d.area_1000ha.max()])
        fig.add_trace(go.Scatter(x=xs, y=slope * xs + icpt, mode="lines", name="trend line", line=dict(color="black")))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Correlation between area and production: {d.area_1000ha.corr(d.production_1000t):.2f}")
    elif n == 15:
        d = q("""SELECT state_name, crop_name, ROUND(1000.0 * SUM(production_1000t) / SUM(area_1000ha), 1) AS yield_kg_ha
                 FROM v_crop_stats WHERE crop_name IN ('Rice', 'Wheat') AND area_1000ha > 0 AND production_1000t IS NOT NULL
                 GROUP BY state_name, crop_name""")
        st.plotly_chart(px.bar(d, x="state_name", y="yield_kg_ha", color="crop_name", barmode="group",
                               title="Rice vs wheat yield across states (kg/ha)"), use_container_width=True)

# ---------------------------------------------------------------- SQL answers
elif page == "SQL answers":
    st.title("🧠 SQL questions from the brief")
    name = st.selectbox("Question", list(QUERIES))
    sql = QUERIES[name].strip()
    with st.expander("Show the SQL", expanded=False):
        st.code(sql, language="sql")
    df = q(sql)
    st.caption(f"{len(df)} rows")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if name.startswith("Q1 "):
        st.plotly_chart(px.line(df, x="year", y="rice_production_1000t", color="state_name"), use_container_width=True)
    elif name.startswith("Q5"):
        st.plotly_chart(px.line(df, x="year", y="cotton_production_1000t", color="state_name"), use_container_width=True)
    elif name.startswith("Q7b"):
        st.plotly_chart(px.line(df, x="year", y="national_maize_yield_kg_ha"), use_container_width=True)
    elif name.startswith("Q10"):
        st.plotly_chart(px.bar(df.melt(["year", "state_name"], ["wheat_1000t", "rice_1000t"]), x="year", y="value",
                               color="variable", facet_row="state_name", barmode="group"), use_container_width=True)
    elif name.startswith(("Q2", "Q3", "Q6", "Q8", "Q9")):
        x = "dist_name" if "dist_name" in df else "state_name"
        y = df.select_dtypes("number").columns[-1] if not name.startswith("Q8") else "total_area_all_years_1000ha"
        st.plotly_chart(bar(df, x, y, name), use_container_width=True)

# ---------------------------------------------------------------- Forecast
elif page == "Yield forecast":
    st.title("🔮 Simple yield forecast")
    c1, c2, c3 = st.columns(3)
    crop = c1.selectbox("Crop", ["Rice", "Wheat", "Maize", "Groundnut", "Sugarcane", "Cotton"])
    state = c2.selectbox("State", STATES, index=STATES.index("Punjab"))
    ahead = c3.slider("Years to forecast", 1, 10, 5)
    d = q("""SELECT year, 1000.0 * SUM(production_1000t) / SUM(area_1000ha) AS yield_kg_ha FROM v_crop_stats
             WHERE crop_name = ? AND state_name = ? AND area_1000ha > 0 AND production_1000t IS NOT NULL
             GROUP BY year ORDER BY year""", (crop, state))
    d = d[d.year >= YMAX - 25]
    if len(d) < 8:
        st.warning("Not enough data for this crop/state.")
    else:
        slope, icpt = np.polyfit(d.year, d.yield_kg_ha, 1)
        fy = np.arange(YMAX + 1, YMAX + ahead + 1)
        fig = go.Figure([go.Scatter(x=d.year, y=d.yield_kg_ha, name="Actual"),
                         go.Scatter(x=fy, y=slope * fy + icpt, name="Forecast (linear trend)", line=dict(dash="dash"))])
        fig.update_layout(title=f"{crop} yield in {state} (kg/ha)")
        st.plotly_chart(fig, use_container_width=True)
        st.info(f"Trend: yield changes by about {slope:,.0f} kg/ha per year. This is a straight-line trend fitted on the last "
                f"{len(d)} years - a simple teaching model, not an accurate prediction (weather, prices and policy are not included).")

# ---------------------------------------------------------------- About
else:
    st.title("ℹ️ About the data")
    st.write(open("cleaning_report.txt").read().replace("\n", "  \n"))
    st.markdown("""
* **Source:** ICRISAT district-level data (311 districts, 20 states, 1966-2017).
* **-1** in the raw file means *missing*; it was converted to NULL.
* **State names** follow the 2017 boundaries (Telangana, Chhattisgarh, Jharkhand, Uttarakhand exist for all years). *Orissa* was renamed *Odisha*.
* **State / national yield** = total production / total area (weighted), not an average of district yields.
* **Oilseeds** totals were rebuilt from the individual oilseed crops where the ready-made total was empty or zero.
""")
