-- Control queries for the bronze/silver layers.
-- Run against the arca database to sanity-check pipeline results.

-- 1. Observations per station (silver).
SELECT station_code, COUNT(*) AS n
FROM silver.observations
GROUP BY station_code
ORDER BY station_code;

-- 2. Potential duplicates: same station/date/hour seen more than once.
--    Should be empty while the unique key (station_code, fecha, hora, source_sha256) holds.
SELECT station_code, fecha, hora, COUNT(*) AS n
FROM silver.observations
GROUP BY station_code, fecha, hora
HAVING COUNT(*) > 1;

-- 3. Rows per source file (idempotency check: reruns must not grow this).
SELECT source_sha256, COUNT(*) AS n
FROM silver.observations
GROUP BY source_sha256
ORDER BY n DESC;