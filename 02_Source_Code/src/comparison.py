"""
comparison.py
-------------
Stage 4: Month 1 vs Month 2 comparison using matched cohort.

Produces:
  outputs/month_1_baseline.csv       — M1 reported-period metrics
  outputs/month_comparison_matched.csv — matched-cohort M1 vs M2 movement
"""

import os
import pandas as pd
import metrics as m_mod


def compute_baseline(eligible_runs, outcomes, citations, audit_month="M1") -> dict:
    """Compute all metrics for the reported period of a given month."""
    runs_m = eligible_runs[eligible_runs["audit_month"] == audit_month].copy()
    run_ids_m = set(runs_m["run_id"].tolist())
    outcomes_m = outcomes[outcomes["run_id_clean"].isin(run_ids_m)].copy()
    citations_m = citations[citations["run_id_clean"].isin(run_ids_m)].copy()
    return m_mod.compute_all_metrics(runs_m, outcomes_m, citations_m)


def compute_matched_comparison(
    eligible_runs, outcomes, citations, matched_cells
) -> tuple[dict, dict, pd.DataFrame]:
    """
    Compute metrics for M1 and M2 using only the matched-core cells.

    Returns:
      m1_matched    — M1 metrics on matched cohort
      m2_matched    — M2 metrics on matched cohort
      comparison_df — DataFrame with M1, M2, delta_pp, relative_change_pct
    """
    # Filter to matched cells
    matched_runs = eligible_runs[eligible_runs["cell_key"].isin(matched_cells)].copy()

    m1_runs = matched_runs[matched_runs["audit_month"] == "M1"]
    m2_runs = matched_runs[matched_runs["audit_month"] == "M2"]

    m1_ids = set(m1_runs["run_id"].tolist())
    m2_ids = set(m2_runs["run_id"].tolist())

    m1_out = outcomes[outcomes["run_id_clean"].isin(m1_ids)].copy()
    m2_out = outcomes[outcomes["run_id_clean"].isin(m2_ids)].copy()
    m1_cit = citations[citations["run_id_clean"].isin(m1_ids)].copy()
    m2_cit = citations[citations["run_id_clean"].isin(m2_ids)].copy()

    m1_metrics = m_mod.compute_all_metrics(m1_runs, m1_out, m1_cit)
    m2_metrics = m_mod.compute_all_metrics(m2_runs, m2_out, m2_cit)

    rows = []
    for metric_name in m1_metrics:
        m1_score = m1_metrics[metric_name].get("score")
        m2_score = m2_metrics.get(metric_name, {}).get("score")
        if m1_score is None or m2_score is None:
            continue
        delta = round(float(m2_score) - float(m1_score), 4)
        rel_change = round(
            (delta / float(m1_score) * 100) if float(m1_score) != 0 else 0.0, 4
        )
        rows.append({
            "metric": metric_name,
            "M1": m1_score,
            "M2": m2_score,
            "delta_pp": delta,
            "relative_change_pct": rel_change,
            "matched_cell_count": len(matched_cells),
            "note": m1_metrics[metric_name].get("note", ""),
        })

    return m1_metrics, m2_metrics, pd.DataFrame(rows)


def baseline_to_df(metrics_dict: dict, audit_month: str) -> pd.DataFrame:
    """Convert metrics dict to the required month_1_baseline.csv schema."""
    rows = []
    for name, m in metrics_dict.items():
        rows.append({
            "metric": m.get("metric", name),
            "audit_month": audit_month,
            "score": m.get("score"),
            "numerator": m.get("numerator"),
            "denominator": m.get("denominator"),
            "note": m.get("note", ""),
        })
    return pd.DataFrame(rows)


def calculate_matched_comparison(
    runs_clean: pd.DataFrame,
    outcomes_clean: pd.DataFrame,
    citations_clean: pd.DataFrame,
    prompt_bank: pd.DataFrame,
    output_dir: str
) -> pd.DataFrame:
    """
    Wrapper function to execute matched cohort comparison M1 vs M2.
    Exports month_comparison_matched.csv.
    """
    eligible_runs = runs_clean[runs_clean["eligible"]].copy()
    matched_runs = eligible_runs[eligible_runs["in_matched_cohort"]].copy()
    matched_cells = set(matched_runs["cell_key"])

    m1_metrics, m2_metrics, comparison_df = compute_matched_comparison(
        eligible_runs, outcomes_clean, citations_clean, matched_cells
    )

    os.makedirs(output_dir, exist_ok=True)
    comparison_df.to_csv(os.path.join(output_dir, "month_comparison_matched.csv"), index=False)

    return comparison_df

