"""
run_visibility_analysis.py
--------------------------
Master entry point for the AsterVale / Kasparro AI Visibility Analysis Pipeline.

Executes all pipeline stages:
1. Ingestion & Pre-cleaning          (src/ingest.py)
2. Structural QA & Eligibility       (src/eligibility.py)  -> runs_clean, outcomes_clean, citations_clean, data_quality_validation_report
3. Metric Calculation - M1 Baseline  (src/metrics.py)      -> month_1_baseline_metrics
4. Matched Cohort Comparison M1/M2   (src/comparison.py)   -> month_over_month_visibility_comparison
5. Driver Analysis by Family/Platform(src/drivers.py)      -> prompt_family_metric_deltas, platform_metric_deltas
6. Content Fix Assessment F01-F07    (src/fix_assessment.py) -> content_fix_impact_assessment, month_3_sprint_recommendations
7. SQL Analytics on GSC/GA4 database (src/sql_analytics.py) -> gsc_ga4_analytics_summary
8. Executive Memo PDF Generation     (src/memo.py)          -> astervale_ai_visibility_executive_report.pdf

Run from the AsterVale_Assignment_Organized/ root:
    python 02_Source_Code/run_visibility_analysis.py

Input data:   03_Input_Data/
Database:     04_Database/supporting_analytics.sqlite
CSV outputs:  05_Analysis_Outputs/
PDF report:   06_Final_Deliverables/astervale_ai_visibility_executive_report.pdf
"""

import os
import sys
import logging

# Ensure src directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ingest import load_and_ingest_all
from eligibility import run_eligibility_pipeline
from metrics import calculate_month_baseline
from comparison import calculate_matched_comparison
from drivers import calculate_driver_breakdowns
from fix_assessment import assess_fixes_and_generate_sprint_plan
from sql_analytics import run_sql_analytics
from memo import generate_executive_memo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AsterValePipeline")


def main():
    # 02_Source_Code/ → AsterVale_Assignment_Organized/
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    data_dir   = os.path.join(project_root, "03_Input_Data")
    output_dir = os.path.join(project_root, "05_Analysis_Outputs")
    db_path    = os.path.join(project_root, "04_Database", "supporting_analytics.sqlite")
    pdf_path   = os.path.join(project_root, "06_Final_Deliverables",
                              "astervale_ai_visibility_executive_report.pdf")

    os.makedirs(output_dir, exist_ok=True)

    logger.info("==================================================")
    logger.info("  STARTING ASTERVALE AI VISIBILITY ANALYSIS PIPELINE  ")
    logger.info("==================================================")

    # Stage 1 & 2: Ingestion & Eligibility
    logger.info("\n--- Stage 1 & 2: Ingest & Eligibility ---")
    data_dict   = load_and_ingest_all(data_dir)
    qa_results  = run_eligibility_pipeline(data_dict, output_dir)

    runs_clean     = qa_results['runs_clean']
    outcomes_clean = qa_results['outcomes_clean']
    citations_clean= qa_results['citations_clean']
    prompt_bank    = qa_results['prompt_bank']
    brand_master   = qa_results['brand_master']  # noqa: F841 (used implicitly downstream)

    # Stage 3: Month 1 Baseline
    logger.info("\n--- Stage 3: Month 1 Baseline Metrics ---")
    calculate_month_baseline(runs_clean, outcomes_clean, citations_clean, prompt_bank, output_dir)

    # Stage 4: Matched Cohort Comparison
    logger.info("\n--- Stage 4: Matched Cohort Comparison (M1 vs M2) ---")
    calculate_matched_comparison(runs_clean, outcomes_clean, citations_clean, prompt_bank, output_dir)

    # Stage 5: Driver Analysis
    logger.info("\n--- Stage 5: Driver Analysis (Prompt Family & Platform) ---")
    calculate_driver_breakdowns(runs_clean, outcomes_clean, citations_clean, prompt_bank, output_dir)

    # Stage 6: Fix Assessment & Sprint Plan
    logger.info("\n--- Stage 6: Fix Assessment & Sprint Planning ---")
    assess_fixes_and_generate_sprint_plan(
        data_dict['fix_log'],
        runs_clean,
        outcomes_clean,
        citations_clean,
        prompt_bank,
        db_path,
        output_dir
    )

    # Stage 7: SQL Analytics
    logger.info("\n--- Stage 7: SQL Analytics (GSC & GA4) ---")
    run_sql_analytics(db_path, output_dir)

    # Stage 8: Executive Memo PDF
    logger.info("\n--- Stage 8: Generating Executive Memo PDF ---")
    generate_executive_memo(output_dir, pdf_path)

    logger.info("\n==================================================")
    logger.info("  PIPELINE EXECUTION COMPLETE SUCCESSFULLY!  ")
    logger.info(f"  CSV outputs:      {output_dir}")
    logger.info(f"  Executive report: {pdf_path}")
    logger.info("==================================================")


if __name__ == "__main__":
    main()
