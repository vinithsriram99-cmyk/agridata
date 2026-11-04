"""Step 1 + 2: clean the ICRISAT district data with pandas and load it into a normalized SQL database.

Usage:  python clean_and_load.py ICRISAT-District_Level_Data.csv
Creates: agri.db (SQLite) and the powerbi/ folder with clean CSV files for Power BI.
"""
import os
import re
import sys
import numpy as np
import pandas as pd
from db import DB_PATH, connect

ID_RENAME = {"Dist Code": "dist_code", "Year": "year", "State Code": "state_code",
             "State Name": "state_name", "Dist Name": "dist_name"}
METRIC = {"AREA": "area_1000ha", "PRODUCTION": "production_1000t", "YIELD": "yield_kg_ha"}

SCHEMA = """
DROP VIEW IF EXISTS v_crop_stats;
DROP TABLE IF EXISTS crop_stats; DROP TABLE IF EXISTS crops;
DROP TABLE IF EXISTS districts;  DROP TABLE IF EXISTS states;
CREATE TABLE states    (state_code INTEGER PRIMARY KEY, state_name TEXT NOT NULL);
CREATE TABLE districts (dist_code  INTEGER PRIMARY KEY, dist_name TEXT NOT NULL,
                        state_code INTEGER NOT NULL REFERENCES states(state_code));
CREATE TABLE crops     (crop_id    INTEGER PRIMARY KEY, crop_name TEXT NOT NULL UNIQUE);
CREATE TABLE crop_stats (
    dist_code        INTEGER NOT NULL REFERENCES districts(dist_code),
    crop_id          INTEGER NOT NULL REFERENCES crops(crop_id),
    year             INTEGER NOT NULL,
    area_1000ha      REAL,
    production_1000t REAL,
    yield_kg_ha      REAL,
    PRIMARY KEY (dist_code, crop_id, year)
);
CREATE INDEX idx_stats_crop_year ON crop_stats (crop_id, year);
CREATE INDEX idx_stats_dist      ON crop_stats (dist_code);
CREATE VIEW v_crop_stats AS
SELECT s.state_code, s.state_name, d.dist_code, d.dist_name, c.crop_name,
       f.year, f.area_1000ha, f.production_1000t, f.yield_kg_ha
FROM crop_stats f
JOIN districts d ON d.dist_code = f.dist_code
JOIN states    s ON s.state_code = d.state_code
JOIN crops     c ON c.crop_id   = f.crop_id;
"""


def clean(path):
    rep = []
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=ID_RENAME)
    rep.append(f"Raw file: {df.shape[0]} rows x {df.shape[1]} columns, years {df.year.min()}-{df.year.max()}")

    # text columns
    df["state_name"] = df["state_name"].astype(str).str.strip().replace({"Orissa": "Odisha"})
    df["dist_name"] = df["dist_name"].astype(str).str.strip()

    # the dataset uses -1 as a "missing" marker
    value_cols = [c for c in df.columns if c not in ID_RENAME.values()]
    n_missing = int((df[value_cols] == -1).sum().sum())
    df[value_cols] = df[value_cols].replace(-1, np.nan)
    rep.append(f"Replaced {n_missing} values of -1 (missing marker) with NULL")
    rep.append(f"Duplicate district-year rows: {int(df.duplicated(['dist_code', 'year']).sum())}")

    # wide -> long: one row per district / year / crop
    crops = {}
    for col in value_cols:
        m = re.match(r"^(.+) (AREA|PRODUCTION|YIELD) \(", col)
        crops.setdefault(m.group(1).title(), {})[METRIC[m.group(2)]] = col
    frames = []
    for crop, cols in crops.items():
        sub = df[["dist_code", "year", "state_code", "state_name", "dist_name"]].copy()
        sub["crop_name"] = crop
        for metric in METRIC.values():
            sub[metric] = df[cols[metric]] if metric in cols else np.nan
        frames.append(sub)
    long = pd.concat(frames, ignore_index=True)
    rep.append(f"{len(crops)} crops / crop groups found; long table before filtering: {len(long)} rows")

    # the ready-made OILSEEDS total is empty/zero for many district-years (e.g. almost all of 2016-17,
    # Tamil Nadu 2009-12) although the individual oilseed crops are present -> rebuild it from the components
    parts = ["Groundnut", "Sesamum", "Rapeseed And Mustard", "Safflower", "Castor", "Linseed", "Sunflower", "Soyabean"]
    comp = (long[long.crop_name.isin(parts)].groupby(["dist_code", "year"])[["area_1000ha", "production_1000t"]]
            .sum(min_count=1))
    oil = long.crop_name == "Oilseeds"
    key = pd.MultiIndex.from_frame(long.loc[oil, ["dist_code", "year"]])
    n_fix = 0
    for col in ["area_1000ha", "production_1000t"]:
        est = comp[col].reindex(key).to_numpy()
        cur = long.loc[oil, col].to_numpy()
        bad = (np.isnan(cur) | (cur == 0)) & (est > 0)
        cur = np.where(bad, est, cur)
        long.loc[oil, col] = cur
        n_fix += int(bad.sum())
    long.loc[oil, "yield_kg_ha"] = np.where(long.loc[oil, "yield_kg_ha"].isna() | (long.loc[oil, "yield_kg_ha"] == 0),
                                            np.nan, long.loc[oil, "yield_kg_ha"])
    rep.append(f"Oilseeds area/production rebuilt from component crops for {n_fix} empty/zero values")

    # fill missing yield where it can be calculated: yield (kg/ha) = production(1000t) / area(1000ha) * 1000
    can = long.yield_kg_ha.isna() & (long.area_1000ha > 0) & long.production_1000t.notna()
    long.loc[can, "yield_kg_ha"] = (long.production_1000t / long.area_1000ha * 1000).round(2)
    rep.append(f"Yield calculated from production/area for {int(can.sum())} rows")
    long.loc[long.area_1000ha == 0, "yield_kg_ha"] = np.nan  # no area -> yield is meaningless

    # drop rows where the crop was not grown / not recorded (area and production both empty or zero)
    nothing = (long.area_1000ha.fillna(0) == 0) & (long.production_1000t.fillna(0) == 0)
    rep.append(f"Dropped {int(nothing.sum())} rows where area and production are both empty/zero (crop not grown)")
    long = long[~nothing].reset_index(drop=True)
    rep.append(f"Final long table: {len(long)} rows, {long.dist_code.nunique()} districts, "
               f"{long.state_name.nunique()} states, years {long.year.min()}-{long.year.max()}")
    return long, rep


def load(long):
    states = long[["state_code", "state_name"]].drop_duplicates().sort_values("state_code")
    districts = long[["dist_code", "dist_name", "state_code"]].drop_duplicates("dist_code").sort_values("dist_code")
    crops = pd.DataFrame({"crop_name": sorted(long.crop_name.unique())})
    crops.insert(0, "crop_id", range(1, len(crops) + 1))
    fact = long.merge(crops, on="crop_name")[["dist_code", "crop_id", "year", "area_1000ha",
                                              "production_1000t", "yield_kg_ha"]]
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = connect()
    con.executescript(SCHEMA)
    states.to_sql("states", con, if_exists="append", index=False)
    districts.to_sql("districts", con, if_exists="append", index=False)
    crops.to_sql("crops", con, if_exists="append", index=False)
    fact.to_sql("crop_stats", con, if_exists="append", index=False, chunksize=20000)
    con.commit()
    con.close()

    os.makedirs("powerbi", exist_ok=True)           # star-schema CSVs for Power BI
    states.to_csv("powerbi/dim_state.csv", index=False)
    districts.to_csv("powerbi/dim_district.csv", index=False)
    crops.to_csv("powerbi/dim_crop.csv", index=False)
    fact.to_csv("powerbi/fact_crop_stats.csv", index=False)
    long.to_csv("powerbi/agri_clean_long.csv", index=False)  # one flat table (easiest for Power BI)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "ICRISAT-District_Level_Data.csv"
    long, report = clean(src)
    load(long)
    report.append(f"Database written to {DB_PATH}; Power BI files written to powerbi/")
    open("cleaning_report.txt", "w").write("\n".join(report))
    print("\n".join(report))
