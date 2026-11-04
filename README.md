# AgriData Explorer: Understanding Indian Agriculture with EDA

Python + SQL + Plotly/Streamlit (+ Power BI) analysis of ICRISAT district-level crop data
(311 districts, 20 states, 1966-2017, 29 crops).

## Files
| File | Purpose |
|---|---|
| `clean_and_load.py` | Cleans the raw CSV (pandas) and loads a normalized SQL database; also exports Power BI files |
| `db.py` | Database connection (SQLite) |
| `queries.py` / `sql_queries.sql` | The 10 SQL questions from the brief |
| `app.py` | Interactive dashboard: overview + filters, 15 EDA charts, SQL answers, simple yield forecast |
| `cleaning_report.txt` | What the cleaning step changed (generated) |
| `powerbi/` | Clean CSVs for Power BI (star schema + one flat table) |
| `POWERBI_GUIDE.md` | Step-by-step Power BI build with DAX measures |
| `RESULTS_SUMMARY.md` | Answers to the 10 SQL questions from the real data |

## Run
```bash
pip install -r requirements.txt
python clean_and_load.py ICRISAT-District_Level_Data.csv
streamlit run app.py
```

## Database design (normalized)
`states` (PK state_code) <- `districts` (PK dist_code, FK state_code) <- `crop_stats` (PK dist_code+crop_id+year, FKs to districts and crops) -> `crops` (PK crop_id).
View `v_crop_stats` joins them for easy querying. Indexes on (crop_id, year) and dist_code.

## Cleaning decisions
1. `-1` in the raw file means missing -> NULL (13,132 values).
2. Wide table (80 columns) reshaped to long format: one row per district / year / crop.
3. Missing yield recalculated as production / area x 1000 where possible.
4. Rows where a crop has no area and no production (not grown) were dropped.
5. The ready-made OILSEEDS total was empty or zero for many district-years (almost all of 2016-17), so it was rebuilt from the individual oilseed crops where missing.
6. `Orissa` renamed `Odisha`; names follow 2017 state boundaries.

## Definitions used in the SQL
- "Last 5 years" = 2013-2017, compared with 2008-2012 (averages, so one bad year cannot distort the answer).
- State / national yield = total production / total area (weighted), not an average of district yields.
- Q4 correlation is Pearson's r per district and crop, using years with data (at least 10).

## Limitations
- Growth percentages are large when the starting base is tiny (e.g. Jharkhand oilseeds).
- The forecast page is a straight-line trend, a teaching model, not an accurate prediction.
- Production values that were missing in the source stay missing; totals can be understated in those years.
