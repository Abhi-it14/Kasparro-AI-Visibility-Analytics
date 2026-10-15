"""
metrics.py
----------
Stage 3: Compute all official metrics from the assignment brief §6.

All scores reported on 0–100 scale, rounded to 4 decimal places.

Metric functions accept:
  eligible_runs   — DataFrame of eligible run rows (from runs_clean, eligible==True)
  outcomes        — DataFrame of normalized outcomes (for eligible runs)
  citations       — DataFrame of clean canonical citations (for eligible runs)
  audit_month     — "M1" or "M2" or None (compute over all rows passed)

When calling for matched cohort, pass only the matched-cohort subset.
"""

import pandas as pd
import numpy as np

CANONICAL_BRANDS = ["B001", "B002", "B003", "B004", "B005"]
RANK_SCORE_MAP = {1: 100.0, 2: 75.0, 3: 50.0, 4: 25.0}  # 5 or unmentioned → 0

AV_BRAND_ID = "B001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rank_score(rank) -> float:
    """Convert rank to score. None/NaN or 5+ → 0."""
    if rank is None or pd.isna(rank):
        return 0.0
    try:
        return RANK_SCORE_MAP.get(int(float(rank)), 0.0)
    except (ValueError, TypeError):
        return 0.0



def _safe_div(num: float, den: float) -> float:
    """Division with 0/0 → 0.0."""
    if den == 0:
        return 0.0
    return num / den


def _round4(x: float) -> float:
    return round(float(x), 4)


# ---------------------------------------------------------------------------
# Outcome index helpers
# ---------------------------------------------------------------------------

def _av_outcomes(outcomes: pd.DataFrame) -> pd.DataFrame:
    """Filter outcomes to AsterVale (B001) rows only."""
    return outcomes[outcomes["canonical_brand_id"] == AV_BRAND_ID].copy()


def _filter_month(df: pd.DataFrame, runs_for_month: set) -> pd.DataFrame:
    """Filter a DataFrame to rows whose run_id_clean is in runs_for_month."""
    return df[df["run_id_clean"].isin(runs_for_month)].copy()


def _get_run_ids(eligible_runs: pd.DataFrame, brand_mode: str = None,
                 comparison_eligible: int = None) -> set:
    """Get run_ids matching filters from eligible run rows."""
    mask = pd.Series([True] * len(eligible_runs), index=eligible_runs.index)
    if brand_mode is not None:
        mask &= eligible_runs["brand_mode"] == brand_mode
    if comparison_eligible is not None:
        mask &= eligible_runs["comparison_eligible"] == comparison_eligible
    return set(eligible_runs[mask]["run_id"].tolist())


# ---------------------------------------------------------------------------
# Individual metric computations
# ---------------------------------------------------------------------------

def compute_category_presence(eligible_runs: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    """
    Category Presence:
      Numerator:   AsterVale-mentioned runs among eligible non-branded runs
      Denominator: Eligible non-branded runs
      Score:       (N/D) × 100
    """
    nb_run_ids = _get_run_ids(eligible_runs, brand_mode="non_branded")
    av_out = _av_outcomes(outcomes)
    av_nb = av_out[av_out["run_id_clean"].isin(nb_run_ids)]
    numerator = int(av_nb["mentioned_parsed"].eq(True).sum())
    denominator = len(nb_run_ids)
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "category_presence",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
    }


def compute_ai_share_of_voice(eligible_runs: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    """
    AI Share of Voice:
      Visibility credit per brand per run = mentioned + shortlisted + recommended + top_choice
      If discouraged=True → credit = 0
      Numerator:   AsterVale total visibility credits across non-branded runs
      Denominator: All-brand total visibility credits across non-branded runs
      Score:       (N/D) × 100
    """
    nb_run_ids = _get_run_ids(eligible_runs, brand_mode="non_branded")
    nb_outcomes = outcomes[outcomes["run_id_clean"].isin(nb_run_ids)].copy()

    def vis_credit(row):
        if row.get("discouraged_parsed") is True:
            return 0
        credit = 0
        for col in ["mentioned_parsed", "shortlisted_parsed", "recommended_parsed", "top_choice_parsed"]:
            if row.get(col) is True:
                credit += 1
        return credit

    nb_outcomes["vis_credit"] = nb_outcomes.apply(vis_credit, axis=1)

    av_credits = float(nb_outcomes[nb_outcomes["canonical_brand_id"] == AV_BRAND_ID]["vis_credit"].sum())
    all_credits = float(nb_outcomes["vis_credit"].sum())

    score = _round4(_safe_div(av_credits, all_credits) * 100)
    return {
        "metric": "ai_share_of_voice",
        "numerator": av_credits,
        "denominator": all_credits,
        "score": score,
    }


def compute_comparison_standing(eligible_runs: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    """
    Comparison Standing:
      Cohort: comparison-eligible non-branded runs
      Numerator:   Sum of AsterVale rank scores across those runs
      Denominator: Count of those runs × 100
      Score:       N/D (already expressed 0–100 since each run can contribute max 100)
    """
    comp_run_ids = _get_run_ids(eligible_runs, brand_mode="non_branded", comparison_eligible=1)
    av_comp = _av_outcomes(outcomes)
    av_comp = av_comp[av_comp["run_id_clean"].isin(comp_run_ids)]

    # For each comparison run, AV rank score (0 if unmentioned)
    # We need one row per run; the eligible_runs has one row per run
    # av_comp may be missing some runs (where AV was not mentioned / outcome absent)
    all_comp_runs = len(comp_run_ids)

    # Build rank score for runs where AV appears
    av_comp["rank_score"] = av_comp["rank_parsed"].apply(_rank_score)

    # For mentioned=False, rank score is 0 already
    # For runs with no av_comp row at all, score is 0
    numerator = float(av_comp["rank_score"].sum())
    denominator = all_comp_runs * 100
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "comparison_standing",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
        "n_comparison_runs": all_comp_runs,
    }


def compute_nb_owned_citation_rate(eligible_runs: pd.DataFrame,
                                    outcomes: pd.DataFrame,
                                    citations: pd.DataFrame) -> dict:
    """
    Non-Branded Owned Citation Rate:
      Cohort: AsterVale-mentioned non-branded runs
      Numerator:   Those runs with at least one AsterVale-owned canonical citation
      Denominator: AsterVale-mentioned non-branded runs
      Score:       (N/D) × 100
    """
    nb_run_ids = _get_run_ids(eligible_runs, brand_mode="non_branded")
    av_nb = _av_outcomes(outcomes)
    av_nb = av_nb[av_nb["run_id_clean"].isin(nb_run_ids) & av_nb["mentioned_parsed"].eq(True)]
    av_mentioned_nb_runs = set(av_nb["run_id_clean"].tolist())

    # AsterVale-owned citations: owning_brand_id == B001
    av_cit = citations[
        (citations["run_id_clean"].isin(av_mentioned_nb_runs)) &
        (citations["owning_brand_id"] == AV_BRAND_ID)
    ]
    runs_with_owned_cit = set(av_cit["run_id_clean"].tolist())
    numerator = len(runs_with_owned_cit)
    denominator = len(av_mentioned_nb_runs)
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "nb_owned_citation_rate",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
    }


def compute_nb_recommendation_rate(eligible_runs: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    """
    Non-Branded Recommendation Rate (Diagnostic):
      Numerator:   AV-recommended runs among non-branded eligible runs
      Denominator: Eligible non-branded runs
    """
    nb_run_ids = _get_run_ids(eligible_runs, brand_mode="non_branded")
    av_nb = _av_outcomes(outcomes)
    av_nb = av_nb[av_nb["run_id_clean"].isin(nb_run_ids)]
    numerator = int(av_nb["recommended_parsed"].eq(True).sum())
    denominator = len(nb_run_ids)
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "nb_recommendation_rate",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
        "note": "diagnostic_only",
    }


def compute_nb_thirdparty_citation_rate(eligible_runs: pd.DataFrame,
                                          outcomes: pd.DataFrame,
                                          citations: pd.DataFrame) -> dict:
    """
    Non-Branded Third-Party Citation Rate (Diagnostic):
      Cohort: AV-mentioned non-branded runs
      Numerator: Runs with at least one non-owned citation associated with AV
      Denominator: AV-mentioned non-branded runs
    """
    nb_run_ids = _get_run_ids(eligible_runs, brand_mode="non_branded")
    av_nb = _av_outcomes(outcomes)
    av_nb = av_nb[av_nb["run_id_clean"].isin(nb_run_ids) & av_nb["mentioned_parsed"].eq(True)]
    av_mentioned_nb_runs = set(av_nb["run_id_clean"].tolist())

    # Non-owned AV citations: cited_brand_id == B001 but owning_brand_id != B001
    # "Associated with AV" means the citation is linked to AV's entry (cited_brand_id == B001)
    av_cit = citations[
        (citations["run_id_clean"].isin(av_mentioned_nb_runs)) &
        (citations["canonical_cited_brand_id"] == AV_BRAND_ID) &
        (citations["is_owned"] == False)
    ]
    runs_with_tp_cit = set(av_cit["run_id_clean"].tolist())
    numerator = len(runs_with_tp_cit)
    denominator = len(av_mentioned_nb_runs)
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "nb_thirdparty_citation_rate",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
        "note": "diagnostic_only",
    }


def compute_branded_presence_quality(eligible_runs: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    """
    Branded Presence Quality:
      Cohort: Branded eligible runs
      Per-run quality score for AV = 40×factual_accuracy + 30×differentiation_present + 30×(1-hedged)
      Unmentioned AV = 0
      Numerator:   Sum of per-run quality scores
      Denominator: Eligible branded runs × 100
      Score:       N/D (expressed 0–100)
    """
    b_run_ids = _get_run_ids(eligible_runs, brand_mode="branded")
    av_b = _av_outcomes(outcomes)
    av_b = av_b[av_b["run_id_clean"].isin(b_run_ids)].copy()

    def quality_score(row):
        if row.get("mentioned_parsed") is not True:
            return 0.0
        fa = row.get("factual_accuracy_parsed")
        dp = row.get("differentiation_present_parsed")
        hg = row.get("hedged_parsed")
        if pd.isna(fa) or pd.isna(dp) or pd.isna(hg):
            return 0.0  # Missing quality data → 0
        return 40 * float(fa) + 30 * float(dp) + 30 * (1 - float(hg))

    av_b["quality_score"] = av_b.apply(quality_score, axis=1)

    # Runs not in av_b (AV not mentioned / no outcome) score 0
    numerator = float(av_b["quality_score"].sum())
    n_branded = len(b_run_ids)
    denominator = n_branded * 100
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "branded_presence_quality",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
        "n_branded_runs": n_branded,
    }


def compute_branded_recommendation_rate(eligible_runs: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    """
    Branded Recommendation Rate:
      Numerator:   AV-recommended runs among branded eligible runs
      Denominator: Eligible branded runs
    """
    b_run_ids = _get_run_ids(eligible_runs, brand_mode="branded")
    av_b = _av_outcomes(outcomes)
    av_b = av_b[av_b["run_id_clean"].isin(b_run_ids)]
    numerator = int(av_b["recommended_parsed"].eq(True).sum())
    denominator = len(b_run_ids)
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "branded_recommendation_rate",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
    }


def compute_branded_prominence(eligible_runs: pd.DataFrame, outcomes: pd.DataFrame) -> dict:
    """
    Branded Prominence:
      Cohort: Branded eligible runs
      Numerator:   Sum of AV rank scores (same rank-score scale)
      Denominator: Eligible branded runs × 100
    """
    b_run_ids = _get_run_ids(eligible_runs, brand_mode="branded")
    av_b = _av_outcomes(outcomes)
    av_b = av_b[av_b["run_id_clean"].isin(b_run_ids)].copy()
    av_b["rank_score"] = av_b["rank_parsed"].apply(_rank_score)

    numerator = float(av_b["rank_score"].sum())
    n_branded = len(b_run_ids)
    denominator = n_branded * 100
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "branded_prominence",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
    }


def compute_branded_owned_citation_rate(eligible_runs: pd.DataFrame,
                                          outcomes: pd.DataFrame,
                                          citations: pd.DataFrame) -> dict:
    """
    Branded Owned Citation Rate:
      Cohort: AV-mentioned branded runs
      Numerator: Runs with at least one AV-owned canonical citation
      Denominator: AV-mentioned branded runs
    """
    b_run_ids = _get_run_ids(eligible_runs, brand_mode="branded")
    av_b = _av_outcomes(outcomes)
    av_b = av_b[av_b["run_id_clean"].isin(b_run_ids) & av_b["mentioned_parsed"].eq(True)]
    av_mentioned_b_runs = set(av_b["run_id_clean"].tolist())

    av_cit = citations[
        (citations["run_id_clean"].isin(av_mentioned_b_runs)) &
        (citations["owning_brand_id"] == AV_BRAND_ID)
    ]
    runs_with_owned_cit = set(av_cit["run_id_clean"].tolist())
    numerator = len(runs_with_owned_cit)
    denominator = len(av_mentioned_b_runs)
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "branded_owned_citation_rate",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
    }


def compute_branded_thirdparty_citation_rate(eligible_runs: pd.DataFrame,
                                               outcomes: pd.DataFrame,
                                               citations: pd.DataFrame) -> dict:
    """
    Branded Third-Party Citation Rate (Diagnostic):
      Cohort: AV-mentioned branded runs
      Numerator: Runs with at least one non-owned citation associated with AV
    """
    b_run_ids = _get_run_ids(eligible_runs, brand_mode="branded")
    av_b = _av_outcomes(outcomes)
    av_b = av_b[av_b["run_id_clean"].isin(b_run_ids) & av_b["mentioned_parsed"].eq(True)]
    av_mentioned_b_runs = set(av_b["run_id_clean"].tolist())

    av_cit = citations[
        (citations["run_id_clean"].isin(av_mentioned_b_runs)) &
        (citations["canonical_cited_brand_id"] == AV_BRAND_ID) &
        (citations["is_owned"] == False)
    ]
    runs_with_tp_cit = set(av_cit["run_id_clean"].tolist())
    numerator = len(runs_with_tp_cit)
    denominator = len(av_mentioned_b_runs)
    score = _round4(_safe_div(numerator, denominator) * 100)
    return {
        "metric": "branded_thirdparty_citation_rate",
        "numerator": numerator,
        "denominator": denominator,
        "score": score,
        "note": "diagnostic_only",
    }


# ---------------------------------------------------------------------------
# Composite scores
# ---------------------------------------------------------------------------

def compute_composites(metrics_dict: dict) -> dict:
    """
    Compute Non-Branded Discovery, Branded Performance and Final ASV Score.
    Input: dict of metric_name → metric result dict (with 'score' key)
    """
    def s(name):
        return metrics_dict.get(name, {}).get("score", 0.0)

    nb_discovery = _round4(
        0.40 * s("ai_share_of_voice")
        + 0.30 * s("category_presence")
        + 0.20 * s("comparison_standing")
        + 0.10 * s("nb_owned_citation_rate")
    )

    branded_performance = _round4(
        0.30 * s("branded_presence_quality")
        + 0.40 * s("branded_recommendation_rate")
        + 0.20 * s("branded_prominence")
        + 0.10 * s("branded_owned_citation_rate")
    )

    final_asv = _round4(
        0.60 * nb_discovery
        + 0.40 * branded_performance
    )

    return {
        "nb_discovery_score": {
            "metric": "nb_discovery_score",
            "numerator": None,
            "denominator": None,
            "score": nb_discovery,
            "note": "composite: 0.40 ASOV + 0.30 CP + 0.20 CS + 0.10 NB_OCR",
        },
        "branded_performance_score": {
            "metric": "branded_performance_score",
            "numerator": None,
            "denominator": None,
            "score": branded_performance,
            "note": "composite: 0.30 BPQ + 0.40 BRR + 0.20 BP + 0.10 B_OCR",
        },
        "final_asv_score": {
            "metric": "final_asv_score",
            "numerator": None,
            "denominator": None,
            "score": final_asv,
            "note": "composite: 0.60 NB_Discovery + 0.40 Branded_Performance",
        },
    }


# ---------------------------------------------------------------------------
# Compute all metrics for a given eligible subset
# ---------------------------------------------------------------------------

def compute_all_metrics(
    eligible_runs: pd.DataFrame,
    outcomes: pd.DataFrame,
    citations: pd.DataFrame,
) -> dict:
    """
    Compute every metric in the framework for the given eligible run/outcome/citation sets.
    Returns a dict: metric_name → result dict.
    """
    metrics = {}

    metrics["category_presence"] = compute_category_presence(eligible_runs, outcomes)
    metrics["ai_share_of_voice"] = compute_ai_share_of_voice(eligible_runs, outcomes)
    metrics["comparison_standing"] = compute_comparison_standing(eligible_runs, outcomes)
    metrics["nb_owned_citation_rate"] = compute_nb_owned_citation_rate(eligible_runs, outcomes, citations)
    metrics["nb_recommendation_rate"] = compute_nb_recommendation_rate(eligible_runs, outcomes)
    metrics["nb_thirdparty_citation_rate"] = compute_nb_thirdparty_citation_rate(eligible_runs, outcomes, citations)
    metrics["branded_presence_quality"] = compute_branded_presence_quality(eligible_runs, outcomes)
    metrics["branded_recommendation_rate"] = compute_branded_recommendation_rate(eligible_runs, outcomes)
    metrics["branded_prominence"] = compute_branded_prominence(eligible_runs, outcomes)
    metrics["branded_owned_citation_rate"] = compute_branded_owned_citation_rate(eligible_runs, outcomes, citations)
    metrics["branded_thirdparty_citation_rate"] = compute_branded_thirdparty_citation_rate(eligible_runs, outcomes, citations)

    composites = compute_composites(metrics)
    metrics.update(composites)

    return metrics


def metrics_to_dataframe(metrics: dict, label: str = "") -> pd.DataFrame:
    """Convert metrics dict to a flat DataFrame suitable for output."""
    rows = []
    for name, m in metrics.items():
        rows.append({
            "metric": m.get("metric", name),
            "label": label,
            "score": m.get("score"),
            "numerator": m.get("numerator"),
            "denominator": m.get("denominator"),
            "note": m.get("note", ""),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Month 1 Baseline Calculation
# ---------------------------------------------------------------------------

def calculate_month_baseline(
    runs_clean: pd.DataFrame,
    outcomes_clean: pd.DataFrame,
    citations_clean: pd.DataFrame,
    prompt_bank: pd.DataFrame,
    output_dir: str
) -> pd.DataFrame:
    """
    Compute Month 1 baseline metrics over all eligible M1 runs.
    Exports month_1_baseline.csv.
    """
    m1_runs = runs_clean[(runs_clean["eligible"]) & (runs_clean["audit_month"] == "M1")].copy()
    m1_run_ids = set(m1_runs["run_id"])
    m1_outcomes = outcomes_clean[outcomes_clean["run_id_clean"].isin(m1_run_ids)].copy()
    m1_citations = citations_clean[citations_clean["run_id_clean"].isin(m1_run_ids)].copy()

    m1_metrics = compute_all_metrics(m1_runs, m1_outcomes, m1_citations)
    m1_df = metrics_to_dataframe(m1_metrics, label="M1_Baseline")

    import os
    os.makedirs(output_dir, exist_ok=True)
    m1_df.to_csv(os.path.join(output_dir, "month_1_baseline.csv"), index=False)

    return m1_df

