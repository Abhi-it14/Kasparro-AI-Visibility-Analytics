-- AsterVale / Kasparro AI Visibility Assignment
-- analysis_queries.sql
-- Supporting analytics queries against supporting_analytics.sqlite
-- Results are directional context only, not causal proof of AI metric movement.
-- Execute: sqlite3 "04_Database/supporting_analytics.sqlite" < 02_Source_Code/analysis_queries.sql


-- Query 1: Monthly GSC performance by query type (branded vs non-branded)
SELECT
    SUBSTR(date, 1, 7)          AS audit_month,
    query_type,
    SUM(impressions)            AS impressions,
    SUM(clicks)                 AS clicks,
    ROUND(
        CASE WHEN SUM(impressions) > 0
             THEN CAST(SUM(clicks) AS REAL) / SUM(impressions) * 100
             ELSE 0 END,
        4
    )                           AS ctr_pct,
    ROUND(AVG(avg_position), 2) AS avg_position
FROM gsc_daily
GROUP BY audit_month, query_type
ORDER BY audit_month, query_type
;


-- Query 2: Monthly non-branded GSC for key content pages
-- (cooling guide, comparison page, cooling product page)
SELECT
    SUBSTR(date, 1, 7)          AS audit_month,
    page_type,
    landing_page,
    SUM(impressions)            AS impressions,
    SUM(clicks)                 AS clicks,
    ROUND(
        CASE WHEN SUM(impressions) > 0
             THEN CAST(SUM(clicks) AS REAL) / SUM(impressions) * 100
             ELSE 0 END,
        4
    )                           AS ctr_pct,
    ROUND(AVG(avg_position), 2) AS avg_position
FROM gsc_daily
WHERE query_type = 'non_branded'
  AND page_type IN ('guide', 'comparison', 'product')
GROUP BY audit_month, page_type, landing_page
ORDER BY audit_month, page_type
;


-- Query 3: Monthly GA4 sessions, engaged sessions, conversions and revenue
SELECT
    SUBSTR(date, 1, 7)           AS audit_month,
    SUM(sessions)                AS sessions,
    SUM(engaged_sessions)        AS engaged_sessions,
    ROUND(
        CASE WHEN SUM(sessions) > 0
             THEN CAST(SUM(engaged_sessions) AS REAL) / SUM(sessions) * 100
             ELSE 0 END,
        4
    )                            AS engagement_rate_pct,
    SUM(conversions)             AS conversions,
    ROUND(SUM(revenue_usd), 2)   AS revenue_usd,
    ROUND(
        CASE WHEN SUM(sessions) > 0
             THEN SUM(revenue_usd) / SUM(sessions)
             ELSE 0 END,
        4
    )                            AS revenue_per_session
FROM ga4_daily
GROUP BY audit_month
ORDER BY audit_month
;


-- Query 4 (supplementary): Monthly GA4 by page type
SELECT
    SUBSTR(date, 1, 7)          AS audit_month,
    page_type,
    SUM(sessions)               AS sessions,
    SUM(engaged_sessions)       AS engaged_sessions,
    SUM(conversions)            AS conversions,
    ROUND(SUM(revenue_usd), 2)  AS revenue_usd
FROM ga4_daily
GROUP BY audit_month, page_type
ORDER BY audit_month, page_type
;
