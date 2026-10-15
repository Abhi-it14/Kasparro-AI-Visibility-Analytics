# AI Usage Declaration

This document details the usage of Artificial Intelligence tools in the completion of the AsterVale / Kasparro AI Visibility Data Analyst Assignment, in strict accordance with submission requirements.

---

## 1. AI Tools & Models Employed

- **Primary AI Assistant**: Antigravity Pair-Programming Agent (powered by Gemini 3.6 Flash / Claude 3.7 Sonnet).
- **Python Libraries Used**: `pandas`, `numpy`, `sqlite3`, `reportlab`, `urllib.parse`, `re`.

---

## 2. Scope of AI Involvement

| Task / Domain | AI Role | Human / Automated Verification |
|---|---|---|
| **Data Ingestion & Cleaning (`ingest.py`, `eligibility.py`)** | Synthesized deterministic cleaning rules (deduplication by latest `ingested_at`, boolean normalization, 6-step URL canonicalization algorithm). | Verified against `qa_report.csv` counts (750 eligible runs out of 782 total raw runs; 366 matched cells). |
| **Metric Engine (`metrics.py`)** | Implemented exact mathematical formulas for all 11 metrics and composite scores (ASV, Non-Branded Discovery, Branded Performance). | Verified against test calculations and cross-checked against Data Dictionary specification rules. |
| **Comparative Engine (`comparison.py`, `drivers.py`)** | Built matched cohort comparison logic and prompt family / platform breakdown calculations. | Audited matched cohort filter logic (`cell_key = prompt_id | platform | replicate`). |
| **Content Fix Evaluation (`fix_assessment.py`)** | Evaluated fixes F01–F07 against observed metric deltas; applied rule-based classification (`consistent_with_improvement`, `mixed`, `no_observable_support`, `not_evaluable_month_2`). | Verified timing constraints (e.g. F06 deployed 2026-08-05 post-M2 window → `not_evaluable_month_2`). |
| **Executive Memo PDF (`memo.py`)** | Programmed ReportLab script for generating 3-page executive presentation PDF with dynamic numerical binding. | Inspected visual PDF output layout, page count boundaries (max 3 pages), table formatting, and data fidelity. |

---

## 3. Data Integrity & Anti-Hallucination Guarantees

1. **Zero Hardcoded Metrics**: All numbers reported in the executive memo, CSV reports, and documentation are programmatically derived from the raw underlying datasets (`month_1_runs.jsonl`, `month_2_runs.jsonl`, `coded_brand_outcomes.csv`, `citations.csv`, `supporting_analytics.sqlite`) by executing `run_analysis.py`.
2. **Deterministic Rules**: No LLM text generation was used to guess, impute, or invent metrics, business causes, or search trends.
3. **Causation Caveat Enforced**: Every report explicitly notes that temporal movement between M1 and M2 does not establish direct causation.
