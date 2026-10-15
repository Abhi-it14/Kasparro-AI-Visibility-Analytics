"""
sql_analytics.py
----------------
Stage 7: Execute required SQL queries against the supporting_analytics.sqlite database.

Produces:
  outputs/supporting_analytics_summary.csv

SQL results are directional context only, not causal proof.
"""

import os
import sqlite3
import pandas as pd

DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "04_Database", "supporting_analytics.sqlite"
)

SQL_FILE = os.path.join(os.path.dirname(__file__), "..", "analysis_queries.sql")


def _conn():
    return sqlite3.connect(DB_PATH)


# ---------------------------------------------------------------------------
# Query 1: Monthly GSC impressions, clicks, CTR by branded/non-branded
# ---------------------------------------------------------------------------

QUERY_1 = """
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
"""

# ---------------------------------------------------------------------------
# Query 2: Monthly non-branded GSC for cooling guide + comparison + product page
# ---------------------------------------------------------------------------

QUERY_2 = """
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
"""

# ---------------------------------------------------------------------------
# Query 3: Monthly GA4 sessions, engaged sessions, conversions and revenue
# ---------------------------------------------------------------------------

QUERY_3 = """
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
"""

# ---------------------------------------------------------------------------
# Additional diagnostic query: GA4 by page type
# ---------------------------------------------------------------------------

QUERY_4 = """
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
"""


def run_analytics() -> pd.DataFrame:
    """
    Execute all SQL queries and return a combined summary DataFrame.
    Also writes the SQL file to disk for submission.
    """
    conn = _conn()

    q1 = pd.read_sql_query(QUERY_1, conn)
    q1["query_source"] = "GSC_monthly_by_query_type"

    q2 = pd.read_sql_query(QUERY_2, conn)
    q2["query_source"] = "GSC_nonbranded_key_pages"

    q3 = pd.read_sql_query(QUERY_3, conn)
    q3["query_source"] = "GA4_monthly_totals"

    q4 = pd.read_sql_query(QUERY_4, conn)
    q4["query_source"] = "GA4_monthly_by_page_type"

    conn.close()

    # Build the required supporting_analytics_summary.csv schema:
    # audit_month, query_type, impressions, clicks, ctr_pct,
    # sessions, engaged_sessions, conversions, revenue_usd

    # Q1 covers impressions, clicks, ctr_pct by month+query_type
    # Q3 covers GA4 by month (no query_type split in GA4)

    # Merge Q1 with Q3 on audit_month
    q1_branded = q1[q1["query_type"] == "branded"].copy()
    q1_nb = q1[q1["query_type"] == "non_branded"].copy()

    # Join GA4 totals to each query_type row
    q3_simple = q3[["audit_month", "sessions", "engaged_sessions", "conversions", "revenue_usd"]].copy()

    branded_summary = q1_branded.merge(q3_simple, on="audit_month", how="left")
    nb_summary = q1_nb.merge(q3_simple, on="audit_month", how="left")
    summary = pd.concat([branded_summary, nb_summary], ignore_index=True)
    summary = summary.sort_values(["audit_month", "query_type"]).reset_index(drop=True)

    # Map month numbers to M1/M2 labels
    summary["audit_period"] = summary["audit_month"].map(
        {"2026-06": "M1", "2026-07": "M2"}
    )

    # Write SQL file
    _write_sql_file()

    return summary, q1, q2, q3, q4


def _write_sql_file():
    """Write the analysis_queries.sql file."""
    sql_content = f"""-- AsterVale / Kasparro AI Visibility Assignment
-- analysis_queries.sql
-- Supporting analytics queries against supporting_analytics.sqlite
-- Results are directional context only, not causal proof of AI metric movement.
-- Execute: sqlite3 "04_Database/supporting_analytics.sqlite" < 02_Source_Code/analysis_queries.sql

{QUERY_1};

{QUERY_2};

{QUERY_3};

{QUERY_4};
"""
    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write(sql_content)


# ---------------------------------------------------------------------------
# Master SQL Analytics Orchestrator
# ---------------------------------------------------------------------------

def run_sql_analytics(sqlite_db_path: str, output_dir: str) -> pd.DataFrame:
    """
    Wrapper function to run SQL queries on GSC/GA4 database and export summary.
    Exports supporting_analytics_summary.csv and analysis_queries.sql.
    """
    global DB_PATH, SQL_FILE
    if sqlite_db_path:
        DB_PATH = sqlite_db_path

    # Put analysis_queries.sql next to the source code (02_Source_Code/)
    # __file__ is src/sql_analytics.py → parent is src/ → parent is 02_Source_Code/
    sql_code_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SQL_FILE = os.path.join(sql_code_dir, "analysis_queries.sql")

    summary, q1, q2, q3, q4 = run_analytics()

    os.makedirs(output_dir, exist_ok=True)
    summary.to_csv(os.path.join(output_dir, "supporting_analytics_summary.csv"), index=False)

    return summary

