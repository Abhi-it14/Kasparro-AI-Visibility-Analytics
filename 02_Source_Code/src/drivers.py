"""
drivers.py
----------
Stage 5: Decompose metric movement by prompt family and platform.

Produces:
  outputs/prompt_family_deltas.csv
  outputs/platform_deltas.csv

For each slice, computes M1 and M2 values for the primary metrics
using the matched-core runs only (primary movement claim).
"""

import os
import pandas as pd
import metrics as m_mod


def _compute_slice_metrics(eligible_runs, outcomes, citations):
    """Compute a compact set of metrics for a slice of runs."""
    run_ids = set(eligible_runs["run_id"].tolist())
    out = outcomes[outcomes["run_id_clean"].isin(run_ids)].copy()
    cit = citations[citations["run_id_clean"].isin(run_ids)].copy()
    result = m_mod.compute_all_metrics(eligible_runs, out, cit)
    return result


def compute_family_deltas(
    eligible_runs: pd.DataFrame,
    outcomes: pd.DataFrame,
    citations: pd.DataFrame,
    matched_cells: set,
) -> pd.DataFrame:
    """
    For each prompt family, compute M1 and M2 primary metrics
    using matched-core runs, and show delta.
    """
    matched_runs = eligible_runs[eligible_runs["cell_key"].isin(matched_cells)].copy()
    families = matched_runs["prompt_family"].dropna().unique()

    rows = []
    for family in sorted(families):
        fam_m1 = matched_runs[(matched_runs["prompt_family"] == family) & (matched_runs["audit_month"] == "M1")]
        fam_m2 = matched_runs[(matched_runs["prompt_family"] == family) & (matched_runs["audit_month"] == "M2")]

        if len(fam_m1) == 0 and len(fam_m2) == 0:
            continue

        # Compute per-family metrics
        metrics_m1 = _compute_slice_metrics(fam_m1, outcomes, citations) if len(fam_m1) > 0 else {}
        metrics_m2 = _compute_slice_metrics(fam_m2, outcomes, citations) if len(fam_m2) > 0 else {}

        row = {
            "prompt_family": family,
            "eligible_runs_m1": len(fam_m1),
            "eligible_runs_m2": len(fam_m2),
        }
        for metric_name in [
            "category_presence", "ai_share_of_voice", "comparison_standing",
            "nb_owned_citation_rate", "branded_recommendation_rate",
            "branded_presence_quality", "branded_prominence",
            "nb_discovery_score", "branded_performance_score", "final_asv_score",
        ]:
            m1_val = metrics_m1.get(metric_name, {}).get("score") if metrics_m1 else None
            m2_val = metrics_m2.get(metric_name, {}).get("score") if metrics_m2 else None
            row[f"{metric_name}_m1"] = m1_val
            row[f"{metric_name}_m2"] = m2_val
            if m1_val is not None and m2_val is not None:
                row[f"{metric_name}_delta"] = round(float(m2_val) - float(m1_val), 4)
            else:
                row[f"{metric_name}_delta"] = None
        rows.append(row)

    return pd.DataFrame(rows)


def compute_platform_deltas(
    eligible_runs: pd.DataFrame,
    outcomes: pd.DataFrame,
    citations: pd.DataFrame,
    matched_cells: set,
) -> pd.DataFrame:
    """
    For each platform, compute M1 and M2 primary metrics
    using matched-core runs, and show delta.
    """
    matched_runs = eligible_runs[eligible_runs["cell_key"].isin(matched_cells)].copy()
    platforms = matched_runs["platform"].dropna().unique()

    rows = []
    for platform in sorted(platforms):
        plat_m1 = matched_runs[(matched_runs["platform"] == platform) & (matched_runs["audit_month"] == "M1")]
        plat_m2 = matched_runs[(matched_runs["platform"] == platform) & (matched_runs["audit_month"] == "M2")]

        if len(plat_m1) == 0 and len(plat_m2) == 0:
            continue

        metrics_m1 = _compute_slice_metrics(plat_m1, outcomes, citations) if len(plat_m1) > 0 else {}
        metrics_m2 = _compute_slice_metrics(plat_m2, outcomes, citations) if len(plat_m2) > 0 else {}

        row = {
            "platform": platform,
            "eligible_runs_m1": len(plat_m1),
            "eligible_runs_m2": len(plat_m2),
        }
        for metric_name in [
            "category_presence", "ai_share_of_voice", "comparison_standing",
            "nb_owned_citation_rate", "branded_recommendation_rate",
            "branded_presence_quality", "branded_prominence",
            "nb_discovery_score", "branded_performance_score", "final_asv_score",
        ]:
            m1_val = metrics_m1.get(metric_name, {}).get("score") if metrics_m1 else None
            m2_val = metrics_m2.get(metric_name, {}).get("score") if metrics_m2 else None
            row[f"{metric_name}_m1"] = m1_val
            row[f"{metric_name}_m2"] = m2_val
            if m1_val is not None and m2_val is not None:
                row[f"{metric_name}_delta"] = round(float(m2_val) - float(m1_val), 4)
            else:
                row[f"{metric_name}_delta"] = None
        rows.append(row)

    return pd.DataFrame(rows)


def calculate_driver_breakdowns(
    runs_clean: pd.DataFrame,
    outcomes_clean: pd.DataFrame,
    citations_clean: pd.DataFrame,
    prompt_bank: pd.DataFrame,
    output_dir: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Wrapper function to execute prompt family and platform deltas.
    Exports prompt_family_deltas.csv and platform_deltas.csv.
    """
    eligible_runs = runs_clean[runs_clean["eligible"]].copy()
    matched_runs = eligible_runs[eligible_runs["in_matched_cohort"]].copy()
    matched_cells = set(matched_runs["cell_key"])

    family_deltas = compute_family_deltas(eligible_runs, outcomes_clean, citations_clean, matched_cells)
    platform_deltas = compute_platform_deltas(eligible_runs, outcomes_clean, citations_clean, matched_cells)

    os.makedirs(output_dir, exist_ok=True)
    family_deltas.to_csv(os.path.join(output_dir, "prompt_family_deltas.csv"), index=False)
    platform_deltas.to_csv(os.path.join(output_dir, "platform_deltas.csv"), index=False)

    return family_deltas, platform_deltas

