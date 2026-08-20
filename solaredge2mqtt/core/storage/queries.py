EXCLUDED_POWER_FIELDS = ("inverter_power", "grid_power", "battery_power")

_EXCLUDED_POWER_FIELDS_SQL = ", ".join(f"'{field}'" for field in EXCLUDED_POWER_FIELDS)

AGGREGATE_MINMAXMEAN_POWERFLOW = f"""
SELECT s.field AS field,
       t.tag_value AS unit,
       (p.ts / 3600) * 3600 AS bucket,
       MIN(p.value) AS agg_min,
       MAX(p.value) AS agg_max,
       AVG(p.value) AS agg_mean
FROM point AS p
JOIN series AS s ON s.series_id = p.series_id
LEFT JOIN series_tag AS t
    ON t.series_id = s.series_id AND t.tag_key = 'unit'
WHERE s.measurement = 'powerflow_raw'
  AND s.field NOT IN ({_EXCLUDED_POWER_FIELDS_SQL})
  AND p.ts >= :start
GROUP BY s.field, t.tag_value, bucket
"""

AGGREGATE_MINMAXMEAN_BATTERY = """
SELECT s.field AS field,
       t.tag_value AS unit,
       (p.ts / 3600) * 3600 AS bucket,
       MIN(p.value) AS agg_min,
       MAX(p.value) AS agg_max,
       AVG(p.value) AS agg_mean
FROM point AS p
JOIN series AS s ON s.series_id = p.series_id
LEFT JOIN series_tag AS t
    ON t.series_id = s.series_id AND t.tag_key = 'unit'
WHERE s.measurement = 'battery_raw'
  AND p.ts >= :start
GROUP BY s.field, t.tag_value, bucket
"""

AGGREGATE_ENERGY = f"""
WITH src AS (
    SELECT s.field AS field,
           t.tag_value AS unit,
           p.ts AS ts,
           p.value AS value,
           (p.ts / 3600) * 3600 AS bucket
    FROM point AS p
    JOIN series AS s ON s.series_id = p.series_id
    LEFT JOIN series_tag AS t
        ON t.series_id = s.series_id AND t.tag_key = 'unit'
    WHERE s.measurement = 'powerflow_raw'
      AND s.field NOT IN ({_EXCLUDED_POWER_FIELDS_SQL})
      AND p.ts >= :start
),
paired AS (
    SELECT field,
           unit,
           bucket,
           ts,
           value,
           LEAD(ts) OVER w AS next_ts,
           LEAD(value) OVER w AS next_value
    FROM src
    WINDOW w AS (PARTITION BY field, unit, bucket ORDER BY ts)
)
SELECT field,
       unit,
       bucket,
       SUM((next_ts - ts) * (value + next_value) / 2.0) / 3600.0 / 1000.0
           AS energy_kwh
FROM paired
WHERE next_ts IS NOT NULL
GROUP BY field, unit, bucket
"""

PRODUCTION_LAST_HOUR = """
WITH src AS (
    SELECT p.ts AS ts, p.value AS value
    FROM point AS p
    JOIN series AS s ON s.series_id = p.series_id
    LEFT JOIN series_tag AS t
        ON t.series_id = s.series_id AND t.tag_key = 'unit'
    WHERE s.measurement = 'powerflow_raw'
      AND s.field = 'pv_production'
      AND (t.tag_value IS NULL OR t.tag_value = 'cumulated')
      AND p.ts >= :start
      AND p.ts < :stop
),
paired AS (
    SELECT ts,
           value,
           LEAD(ts) OVER (ORDER BY ts) AS next_ts,
           LEAD(value) OVER (ORDER BY ts) AS next_value
    FROM src
)
SELECT :start AS ts,
       SUM((next_ts - ts) * (value + next_value) / 2.0) / 3600.0 AS energy,
       (SELECT AVG(value) FROM src) AS power
FROM paired
WHERE next_ts IS NOT NULL
HAVING COUNT(*) > 0
"""

PERIOD_SUM = """
SELECT t.tag_value AS unit,
       s.field AS field,
       SUM(p.value) AS value
FROM point AS p
JOIN series AS s ON s.series_id = p.series_id
LEFT JOIN series_tag AS t
    ON t.series_id = s.series_id AND t.tag_key = 'unit'
WHERE s.measurement = :measurement
  AND p.ts >= :start
  AND p.ts < :stop
GROUP BY t.tag_value, s.field
"""

PIVOT_BY_TIME = """
SELECT p.ts AS ts, s.field AS field, p.value AS value
FROM point AS p
JOIN series AS s ON s.series_id = p.series_id
WHERE s.measurement = :measurement
  AND p.ts >= :start
  AND (:stop IS NULL OR p.ts < :stop)
ORDER BY p.ts, s.field
"""

DELETE_POINTS_BEFORE = """
DELETE FROM point WHERE series_id = :series_id AND ts < :cutoff
"""

COUNT_POINTS_BEFORE = """
SELECT COUNT(*) FROM point WHERE series_id = :series_id AND ts < :cutoff
"""

#: The module series that lost their tag shape to a change in the monitoring
#: API, mapped onto the series that carries the newest point for that serial.
MODULE_SERIES_MERGE_PLAN = """
WITH module_series AS (
    SELECT s.series_id,
           s.field,
           (SELECT tag_value FROM series_tag
             WHERE series_id = s.series_id
               AND tag_key = 'serialnumber') AS serialnumber,
           (SELECT MAX(ts) FROM point WHERE series_id = s.series_id) AS last_ts
    FROM series s
    WHERE s.measurement = 'modules'
),
newest AS (
    SELECT serialnumber, field, series_id,
           ROW_NUMBER() OVER (
               PARTITION BY serialnumber, field
               ORDER BY last_ts DESC, series_id DESC
           ) AS position
    FROM module_series
    WHERE serialnumber IS NOT NULL AND last_ts IS NOT NULL
)
SELECT module_series.series_id AS source_id, newest.series_id AS target_id
FROM module_series
JOIN newest ON newest.serialnumber = module_series.serialnumber
           AND newest.field = module_series.field
           AND newest.position = 1
WHERE module_series.series_id <> newest.series_id
"""

#: Points the target already holds win -- the older shape came from the
#: release that got the tags wrong, and may hold an incomplete snapshot.
MERGE_SERIES_POINTS = """
INSERT INTO point (series_id, ts, value)
SELECT :target_id, ts, value FROM point WHERE series_id = :source_id
ON CONFLICT (series_id, ts) DO NOTHING
"""

DELETE_SERIES = """
DELETE FROM series WHERE series_id = :series_id
"""
