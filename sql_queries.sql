-- AgriData Explorer: the 10 SQL questions (SQLite syntax). Table/view: v_crop_stats
-- Note: SQRT is built in for PostgreSQL/MySQL; with SQLite it is registered from db.py.

-- Q1  Rice production trend of the top 3 states
WITH top3 AS (
    SELECT state_name FROM v_crop_stats WHERE crop_name = 'Rice'
    GROUP BY state_name ORDER BY SUM(production_1000t) DESC LIMIT 3)
SELECT year, state_name, ROUND(SUM(production_1000t), 1) AS rice_production_1000t
FROM v_crop_stats
WHERE crop_name = 'Rice' AND state_name IN (SELECT state_name FROM top3)
GROUP BY year, state_name
ORDER BY year, state_name;

-- Q2  Top 5 districts by wheat yield increase (last 5 yrs vs previous 5)
WITH recent AS (
    SELECT dist_code, dist_name, state_name, AVG(yield_kg_ha) AS avg_yield
    FROM v_crop_stats WHERE crop_name = 'Wheat' AND yield_kg_ha > 0 AND year > (SELECT MAX(year) FROM crop_stats) - 5
    GROUP BY dist_code, dist_name, state_name),
prev AS (
    SELECT dist_code, AVG(yield_kg_ha) AS avg_yield
    FROM v_crop_stats WHERE crop_name = 'Wheat' AND yield_kg_ha > 0
      AND year BETWEEN (SELECT MAX(year) FROM crop_stats) - 9 AND (SELECT MAX(year) FROM crop_stats) - 5
    GROUP BY dist_code)
SELECT r.state_name, r.dist_name,
       ROUND(p.avg_yield, 1) AS prev_5yr_avg_yield, ROUND(r.avg_yield, 1) AS last_5yr_avg_yield,
       ROUND(r.avg_yield - p.avg_yield, 1) AS yield_increase_kg_ha
FROM recent r JOIN prev p ON p.dist_code = r.dist_code
ORDER BY yield_increase_kg_ha DESC LIMIT 5;

-- Q3  States with highest 5-year growth in oilseed production
WITH yearly AS (
    SELECT state_name, year, SUM(production_1000t) AS prod
    FROM v_crop_stats WHERE crop_name = 'Oilseeds' GROUP BY state_name, year),
recent AS (SELECT state_name, AVG(prod) AS avg_prod FROM yearly
           WHERE year > (SELECT MAX(year) FROM crop_stats) - 5 GROUP BY state_name),
prev AS   (SELECT state_name, AVG(prod) AS avg_prod FROM yearly
           WHERE year BETWEEN (SELECT MAX(year) FROM crop_stats) - 9 AND (SELECT MAX(year) FROM crop_stats) - 5 GROUP BY state_name)
SELECT r.state_name, ROUND(p.avg_prod, 1) AS prev_5yr_avg_1000t, ROUND(r.avg_prod, 1) AS last_5yr_avg_1000t,
       ROUND(100.0 * (r.avg_prod - p.avg_prod) / p.avg_prod, 2) AS growth_pct
FROM recent r JOIN prev p ON p.state_name = r.state_name
WHERE p.avg_prod > 0
ORDER BY growth_pct DESC LIMIT 5;

-- Q4  District-wise correlation: area vs production (Rice, Wheat, Maize)
SELECT state_name, dist_name, crop_name, COUNT(*) AS years_used,
       ROUND((COUNT(*) * SUM(a * p) - SUM(a) * SUM(p)) /
             (SQRT(COUNT(*) * SUM(a * a) - SUM(a) * SUM(a)) *
              SQRT(COUNT(*) * SUM(p * p) - SUM(p) * SUM(p))), 3) AS correlation
FROM (SELECT state_name, dist_code, dist_name, crop_name,
             area_1000ha AS a, production_1000t AS p
      FROM v_crop_stats
      WHERE crop_name IN ('Rice', 'Wheat', 'Maize') AND area_1000ha > 0 AND production_1000t IS NOT NULL) x
GROUP BY dist_code, state_name, dist_name, crop_name
HAVING COUNT(*) >= 10 AND correlation IS NOT NULL
ORDER BY crop_name, correlation DESC;

-- Q5  Yearly cotton production growth in the top 5 cotton states
WITH top5 AS (
    SELECT state_name FROM v_crop_stats WHERE crop_name = 'Cotton'
    GROUP BY state_name ORDER BY SUM(production_1000t) DESC LIMIT 5),
yearly AS (
    SELECT state_name, year, SUM(production_1000t) AS prod
    FROM v_crop_stats WHERE crop_name = 'Cotton' AND state_name IN (SELECT state_name FROM top5)
    GROUP BY state_name, year)
SELECT state_name, year, ROUND(prod, 1) AS cotton_production_1000t,
       ROUND(100.0 * (prod - LAG(prod) OVER (PARTITION BY state_name ORDER BY year))
             / NULLIF(LAG(prod) OVER (PARTITION BY state_name ORDER BY year), 0), 2) AS yoy_growth_pct
FROM yearly ORDER BY state_name, year;

-- Q6  Districts with the highest groundnut production in 2017
SELECT state_name, dist_name, production_1000t AS groundnut_production_1000t,
       area_1000ha, yield_kg_ha
FROM v_crop_stats WHERE crop_name = 'Groundnut' AND year = 2017
ORDER BY production_1000t DESC LIMIT 10;

-- Q7  Annual average maize yield by state
SELECT year, state_name, ROUND(1000.0 * SUM(production_1000t) / SUM(area_1000ha), 1) AS maize_yield_kg_ha
FROM v_crop_stats
WHERE crop_name = 'Maize' AND area_1000ha > 0 AND production_1000t IS NOT NULL
GROUP BY year, state_name ORDER BY year DESC, maize_yield_kg_ha DESC;

-- Q7b Annual maize yield across ALL states (national)
SELECT year, ROUND(1000.0 * SUM(production_1000t) / SUM(area_1000ha), 1) AS national_maize_yield_kg_ha,
       COUNT(DISTINCT state_name) AS states_reporting
FROM v_crop_stats
WHERE crop_name = 'Maize' AND area_1000ha > 0 AND production_1000t IS NOT NULL
GROUP BY year ORDER BY year;

-- Q8  Total oilseeds area in each state
SELECT state_name,
       ROUND(SUM(area_1000ha), 1) AS total_area_all_years_1000ha,
       ROUND(SUM(area_1000ha) / COUNT(DISTINCT year), 1) AS avg_annual_area_1000ha,
       ROUND(SUM(CASE WHEN year = (SELECT MAX(year) FROM crop_stats) THEN area_1000ha END), 1) AS latest_year_area_1000ha
FROM v_crop_stats WHERE crop_name = 'Oilseeds'
GROUP BY state_name ORDER BY total_area_all_years_1000ha DESC;

-- Q9  Districts with the highest rice yield
SELECT state_name, dist_name, COUNT(*) AS years_of_data,
       ROUND(1000.0 * SUM(production_1000t) / SUM(area_1000ha), 1) AS rice_yield_kg_ha,
       MAX(yield_kg_ha) AS best_single_year_yield
FROM v_crop_stats
WHERE crop_name = 'Rice' AND area_1000ha > 0 AND production_1000t IS NOT NULL
GROUP BY dist_code, state_name, dist_name
HAVING COUNT(*) >= 10
ORDER BY rice_yield_kg_ha DESC LIMIT 10;

-- Q10 Wheat vs rice production, top 5 states, last 10 years
WITH top5 AS (
    SELECT state_name FROM v_crop_stats
    WHERE crop_name IN ('Wheat', 'Rice') AND year > (SELECT MAX(year) FROM crop_stats) - 10
    GROUP BY state_name ORDER BY SUM(production_1000t) DESC LIMIT 5)
SELECT year, state_name,
       ROUND(SUM(CASE WHEN crop_name = 'Wheat' THEN production_1000t END), 1) AS wheat_1000t,
       ROUND(SUM(CASE WHEN crop_name = 'Rice'  THEN production_1000t END), 1) AS rice_1000t
FROM v_crop_stats
WHERE crop_name IN ('Wheat', 'Rice') AND year > (SELECT MAX(year) FROM crop_stats) - 10
  AND state_name IN (SELECT state_name FROM top5)
GROUP BY year, state_name ORDER BY state_name, year;
