# Power BI guide (Power BI Desktop runs on Windows only)

**Mac users:** Power BI Desktop is not available for macOS. Options: (1) use a Windows PC or a friend's laptop for 1-2 hours,
(2) a Windows virtual machine, (3) Power BI Service in the browser (needs a work or school account; personal Gmail is not accepted).
Ask in the Guvi doubt session (Mon-Sat 4-5 PM, book before 12 PM) whether the Plotly/Streamlit dashboard is accepted if you cannot use Desktop.

## Steps
1. Copy the `powerbi/` folder to the Windows PC.
2. Power BI Desktop -> **Get data -> Text/CSV** -> load `agri_clean_long.csv` (easiest: one flat table).
   (Optional star schema: load dim_state, dim_district, dim_crop, fact_crop_stats and link state_code, dist_code, crop_id in Model view.)
3. In Power Query check column types: year = Whole number, area/production/yield = Decimal number.
4. **Measures** (Modeling -> New measure):
```
Total Production = SUM(agri_clean_long[production_1000t])
Total Area = SUM(agri_clean_long[area_1000ha])
Weighted Yield = DIVIDE([Total Production], [Total Area]) * 1000
Prev Year Production = CALCULATE([Total Production], FILTER(ALL(agri_clean_long[year]), agri_clean_long[year] = MAX(agri_clean_long[year]) - 1))
YoY Growth % = DIVIDE([Total Production] - [Prev Year Production], [Prev Year Production])
```
5. **Slicers:** crop_name, state_name, year (slider).
6. **Visuals:** cards (Total Production, Total Area, Weighted Yield); line chart (year x Total Production); bar chart (state_name x Total Production, Top N filter);
   scatter (Total Area vs Total Production by dist_name); filled map by state_name (Odisha is spelled correctly); matrix heatmap (state x year, conditional formatting).
7. Dynamic title: `Title = "Production of " & SELECTEDVALUE(agri_clean_long[crop_name], "all crops")`.
8. Save as `AgriData_Explorer.pbix`, take screenshots of each page, and upload both to GitHub.
