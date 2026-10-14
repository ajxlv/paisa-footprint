-- Coverage report over a Paisa Footprint snapshot (DuckDB).
-- Run from the repo root after `pf build-snapshot`:
--     duckdb < sql/coverage.sql
-- Only the current fiscal year of each company is counted for coverage.

CREATE OR REPLACE VIEW companies AS
    SELECT * FROM read_parquet('data/snapshots/fixtures/companies.parquet');
CREATE OR REPLACE VIEW validation_report AS
    SELECT * FROM read_parquet('data/snapshots/fixtures/validation_report.parquet');

-- 1. Headline coverage
SELECT
    count(*)                                                          AS companies,
    count(*) FILTER (WHERE scope1_t IS NOT NULL AND scope2_t IS NOT NULL) AS reporting_scope12,
    round(100.0 * count(*) FILTER (WHERE scope1_t IS NOT NULL AND scope2_t IS NOT NULL)
          / count(*), 1)                                              AS pct_reporting_scope12,
    count(*) FILTER (WHERE assured AND scope1_t IS NOT NULL AND scope2_t IS NOT NULL)
                                                                      AS assured,
    round(100.0 * count(*) FILTER (WHERE assured AND scope1_t IS NOT NULL AND scope2_t IS NOT NULL)
          / nullif(count(*) FILTER (WHERE scope1_t IS NOT NULL AND scope2_t IS NOT NULL), 0), 1)
                                                                      AS pct_assured_of_reporting
FROM companies
WHERE is_current;

-- 2. Issues per rule (all filed years)
SELECT rule_id, severity, count(*) AS issues, count(DISTINCT company_key) AS companies
FROM validation_report
GROUP BY rule_id, severity
ORDER BY rule_id, severity;

-- 3. Quality flags, current year
SELECT quality_flag, count(*) AS companies
FROM companies
WHERE is_current
GROUP BY quality_flag
ORDER BY quality_flag;
