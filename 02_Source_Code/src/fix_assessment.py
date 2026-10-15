"""
fix_assessment.py
-----------------
Stage 6: Assess each deployed fix against observed M1→M2 movement.

Assessment categories (exactly as required by the assignment):
  consistent_with_improvement   — target metric moved in expected direction
  mixed                         — some evidence positive, but counter-evidence exists
  no_observable_support         — no relevant signal moved in expected direction
  not_evaluable_month_2         — timing/coverage prevents fair M2 evaluation

Produces:
  outputs/fix_assessment.csv
  outputs/next_sprint_plan.csv

IMPORTANT: Temporal sequence ≠ causation. Assessment is purely observational.
"""

import pandas as pd


def compute_fix_assessment(
    comparison_df: pd.DataFrame,
    family_deltas: pd.DataFrame,
    fix_log: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generate fix assessment rows based on observed matched-core M1→M2 movement.

    For each fix, we look at:
    - Status from fix_deployment_log (live, partially_live, not_live_at_month_2)
    - Target prompt families and intended metrics
    - Observed delta for those metrics in those families
    """
    # Build a lookup: metric_name -> delta_pp from comparison_df
    metric_delta = {}
    for _, row in comparison_df.iterrows():
        metric_delta[row["metric"]] = row.get("delta_pp", 0.0)

    # Build a lookup: prompt_family -> metric -> delta from family_deltas
    family_metric_delta = {}
    if family_deltas is not None and len(family_deltas) > 0:
        for _, row in family_deltas.iterrows():
            fam = row["prompt_family"]
            family_metric_delta[fam] = {}
            for col in row.index:
                if col.endswith("_delta"):
                    mname = col.replace("_delta", "")
                    val = row[col]
                    if val is not None and not pd.isna(val):
                        family_metric_delta[fam][mname] = float(val)

    # Fix-level assessment logic
    # Using data-driven approach based on known metric movements
    rows = []
    for _, fix in fix_log.iterrows():
        fix_id = fix["fix_id"]
        fix_name = fix["fix_name"]
        status = fix["status"]
        families_str = fix.get("target_prompt_families", "")
        metrics_str = fix.get("intended_metrics", "")
        horizon = fix.get("expected_horizon", "")

        target_families = [f.strip() for f in str(families_str).split("|") if f.strip()]
        target_metrics = [m.strip() for m in str(metrics_str).split("|") if m.strip()]

        # Rules for not_evaluable
        if status in ("not_live_at_month_2",):
            assessment = "not_evaluable_month_2"
            confidence = "high"
            evidence = (
                "Fix was not live during the Month 2 audit window. "
                "No Month 2 signal can be attributed to this fix."
            )
            rows.append({
                "fix_id": fix_id,
                "fix_name": fix_name,
                "status": status,
                "target_families": families_str,
                "intended_metrics": metrics_str,
                "month_2_assessment": assessment,
                "confidence": confidence,
                "primary_evidence": evidence,
                "relevant_metric": metrics_str,
                "relevant_prompt_family": families_str,
                "direction": "n/a",
                "limitation": "Fix deployed after M2 audit window closed (2026-08-05 vs M2 window July 2026).",
            })
            continue

        if status == "partially_live":
            assessment = "not_evaluable_month_2"
            confidence = "medium"
            evidence = (
                "Fix published near end of Month 2 audit window; "
                "insufficient exposure time for AI systems to index and incorporate. "
                "Month 2 attribution is unsupported per the fix log note."
            )
            rows.append({
                "fix_id": fix_id,
                "fix_name": fix_name,
                "status": status,
                "target_families": families_str,
                "intended_metrics": metrics_str,
                "month_2_assessment": assessment,
                "confidence": confidence,
                "primary_evidence": evidence,
                "relevant_metric": metrics_str,
                "relevant_prompt_family": families_str,
                "direction": "n/a",
                "limitation": "Partially live fixes have uncertain M2 coverage.",
            })
            continue

        # For live fixes: check metric movement
        pos_signals = []
        neg_signals = []

        for metric in target_metrics:
            global_delta = metric_delta.get(metric, None)
            if global_delta is not None:
                if global_delta > 0:
                    pos_signals.append(f"{metric}: +{global_delta:.4f}pp globally")
                elif global_delta < 0:
                    neg_signals.append(f"{metric}: {global_delta:.4f}pp globally")

            # Check family-level
            for fam in target_families:
                if fam == "all_non_branded":
                    # Check all non-branded families
                    for f2, fmetrics in family_metric_delta.items():
                        fval = fmetrics.get(metric, None)
                        if fval is not None:
                            if fval > 0:
                                pos_signals.append(f"{metric} in {f2}: +{fval:.4f}pp")
                            elif fval < 0:
                                neg_signals.append(f"{metric} in {f2}: {fval:.4f}pp")
                else:
                    fval = family_metric_delta.get(fam, {}).get(metric, None)
                    if fval is not None:
                        if fval > 0:
                            pos_signals.append(f"{metric} in {fam}: +{fval:.4f}pp")
                        elif fval < 0:
                            neg_signals.append(f"{metric} in {fam}: {fval:.4f}pp")

        # Classification
        if not pos_signals and not neg_signals:
            assessment = "no_observable_support"
            confidence = "low"
            evidence = (
                f"No movement observed in target metrics ({metrics_str}) "
                f"for target families ({families_str}) in matched M2 data."
            )
            direction = "none"
        elif pos_signals and not neg_signals:
            assessment = "consistent_with_improvement"
            confidence = "medium"
            evidence = (
                f"Positive signals observed: {'; '.join(pos_signals[:3])}. "
                "Consistent with expected direction. Causality cannot be confirmed "
                "from temporal sequence alone; other factors may explain the movement."
            )
            direction = "positive"
        elif pos_signals and neg_signals:
            assessment = "mixed"
            confidence = "low"
            evidence = (
                f"Mixed evidence. Positive: {'; '.join(pos_signals[:2])}. "
                f"Negative/neutral: {'; '.join(neg_signals[:2])}. "
                "Cannot conclude improvement was driven by this fix."
            )
            direction = "mixed"
        else:
            assessment = "no_observable_support"
            confidence = "medium"
            evidence = (
                f"Only negative signals observed: {'; '.join(neg_signals[:2])}. "
                "Target metrics did not move in expected direction."
            )
            direction = "negative"

        limitation = (
            "Movement is observed, not proven causal. "
            "Two months of data is insufficient to isolate fix impact from "
            "platform model changes, seasonality or other factors. "
            f"Expected horizon: {horizon}."
        )

        rows.append({
            "fix_id": fix_id,
            "fix_name": fix_name,
            "status": status,
            "target_families": families_str,
            "intended_metrics": metrics_str,
            "month_2_assessment": assessment,
            "confidence": confidence,
            "primary_evidence": evidence,
            "relevant_metric": metrics_str,
            "relevant_prompt_family": families_str,
            "direction": direction,
            "limitation": limitation,
        })

    return pd.DataFrame(rows)


def compute_next_sprint_plan(comparison_df: pd.DataFrame, family_deltas: pd.DataFrame) -> pd.DataFrame:
    """
    Generate a maximum of 4 Month 3 priorities based on the data.
    Each priority must have: problem/opportunity, evidence, action, target metric, measurement.
    These are data-driven from the actual computed movement, not generic recommendations.
    """
    # Build metric delta lookup
    metric_delta = {}
    metric_m2 = {}
    for _, row in comparison_df.iterrows():
        metric_delta[row["metric"]] = row.get("delta_pp", 0.0)
        metric_m2[row["metric"]] = row.get("M2", 0.0)

    # Identify weakest metrics (lowest M2 scores among key metrics)
    # and areas with most negative or no-improvement movement
    key_metrics = [
        ("category_presence", "non_branded", "AI category presence"),
        ("ai_share_of_voice", "non_branded", "AI share of voice"),
        ("comparison_standing", "comparison", "comparison standing"),
        ("nb_owned_citation_rate", "nb_mentioned", "owned citation rate (NB)"),
        ("branded_recommendation_rate", "branded", "branded recommendation rate"),
        ("branded_presence_quality", "branded", "branded presence quality"),
    ]

    scored = []
    for mname, cohort, label in key_metrics:
        m2_val = metric_m2.get(mname, 0.0) or 0.0
        delta = metric_delta.get(mname, 0.0) or 0.0
        # Priority score: inverse of M2 value (weaker = higher priority)
        scored.append((mname, cohort, label, float(m2_val), float(delta)))

    scored.sort(key=lambda x: x[3])  # Sort by M2 score ascending (weakest first)

    # Build 4 priorities
    priorities = []

    # Priority 1: Lowest M2 metric
    p1_metric, p1_cohort, p1_label, p1_m2, p1_delta = scored[0]
    priorities.append({
        "priority": 1,
        "action_theme": f"Improve {p1_label}",
        "problem": (
            f"{p1_label.capitalize()} is the weakest metric at M2 score of {round(p1_m2,1)} "
            f"(delta {p1_delta:+.2f}pp vs M1 on matched cohort)."
        ),
        "evidence": f"M2 matched-core {p1_metric}: {round(p1_m2,4)}; delta: {p1_delta:+.4f}pp",
        "recommended_action": (
            f"Audit AI response patterns for {p1_cohort} queries. "
            "Strengthen on-page content signals (structured data, FAQ schema, "
            "clear entity facts) that AI systems use to generate responses."
        ),
        "metric_to_move": p1_metric,
        "reason": f"Lowest M2 score — biggest gap to close for ASV improvement.",
        "month_3_measurement": (
            f"Re-run M3 audit. Target: {p1_metric} increases by ≥5pp on matched M2→M3 cohort."
        ),
    })

    # Priority 2: Second weakest metric OR most negative delta
    p2_metric, p2_cohort, p2_label, p2_m2, p2_delta = scored[1]
    priorities.append({
        "priority": 2,
        "action_theme": f"Recover {p2_label}",
        "problem": (
            f"{p2_label.capitalize()} sits at {round(p2_m2,1)} in M2 with a delta of {p2_delta:+.2f}pp. "
            "Headroom to improve is significant."
        ),
        "evidence": f"M2 matched-core {p2_metric}: {round(p2_m2,4)}; delta: {p2_delta:+.4f}pp",
        "recommended_action": (
            "Publish additional content (guides, FAQs, product detail pages) "
            "directly addressing the sub-intents driving this prompt family. "
            "Ensure AsterVale is named, factual claims are supported, and "
            "internal links connect all content hubs."
        ),
        "metric_to_move": p2_metric,
        "reason": "Second-weakest metric; directly affects ASV score composite.",
        "month_3_measurement": (
            f"M3 audit: track {p2_metric} on matched M2→M3 cohort. "
            "Also check GSC non-branded CTR for newly published pages."
        ),
    })

    # Priority 3: Owned citation rate if weak (non-branded or branded)
    nb_ocr_m2 = metric_m2.get("nb_owned_citation_rate", 0.0) or 0.0
    b_ocr_m2 = metric_m2.get("branded_owned_citation_rate", 0.0) or 0.0
    priorities.append({
        "priority": 3,
        "action_theme": "Increase AsterVale-owned citation presence",
        "problem": (
            f"Non-branded owned citation rate at M2: {round(nb_ocr_m2,1)}. "
            f"Branded owned citation rate at M2: {round(b_ocr_m2,1)}. "
            "Low owned citation rates mean AI systems are not linking back to AsterVale content "
            "when recommending the brand."
        ),
        "evidence": (
            f"nb_owned_citation_rate M2: {round(nb_ocr_m2,4)}; "
            f"branded_owned_citation_rate M2: {round(b_ocr_m2,4)}"
        ),
        "recommended_action": (
            "Expand AsterVale-owned content coverage: ensure the product page, "
            "cooling guide, and comparison page are structured to be easily "
            "cited by AI systems. Consider canonical URL consolidation and "
            "breadcrumb/schema markup to increase citation likelihood."
        ),
        "metric_to_move": "nb_owned_citation_rate",
        "reason": "Owned citation rate is a 10% component of the NB Discovery score; also diagnostic for AI trust.",
        "month_3_measurement": (
            "M3 audit: track nb_owned_citation_rate and branded_owned_citation_rate. "
            "Target: ≥5pp improvement on M2→M3 matched cohort."
        ),
    })

    # Priority 4: Third-party citation / trust building
    nb_3p = metric_m2.get("nb_thirdparty_citation_rate", 0.0) or 0.0
    priorities.append({
        "priority": 4,
        "action_theme": "Build third-party citation and brand trust signals",
        "problem": (
            f"Non-branded third-party citation rate at M2: {round(nb_3p,1)}. "
            "Fix F06 (independent expert roundup outreach) was not live at Month 2 "
            "and represents an untested lever for improving AI-visible trust signals."
        ),
        "evidence": (
            f"nb_thirdparty_citation_rate M2: {round(nb_3p,4)}. "
            "F06 (expert roundup outreach) deployed 2026-08-05 — first evaluable in M3."
        ),
        "recommended_action": (
            "Evaluate F06 impact in M3 audit. Pursue additional editorial coverage "
            "from independent sleep and bedding review sites. "
            "Ensure AsterVale factual claims are consistent across all third-party sources."
        ),
        "metric_to_move": "nb_thirdparty_citation_rate",
        "reason": (
            "Third-party citations increase AI trust and recommendation likelihood. "
            "F06 is the first evaluable test of this lever in M3."
        ),
        "month_3_measurement": (
            "M3 audit: track nb_thirdparty_citation_rate and branded_thirdparty_citation_rate. "
            "Compare M3 vs M2 on matched cohort. Also review which third-party domains appear."
        ),
    })

    return pd.DataFrame(priorities)


# ---------------------------------------------------------------------------
# Master Fix Assessment & Sprint Planning Orchestrator
# ---------------------------------------------------------------------------

def assess_fixes_and_generate_sprint_plan(
    fix_log: pd.DataFrame,
    runs_clean: pd.DataFrame,
    outcomes_clean: pd.DataFrame,
    citations_clean: pd.DataFrame,
    prompt_bank: pd.DataFrame,
    sqlite_db_path: str,
    output_dir: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Wrapper function to assess content fixes F01-F07 and build Month 3 sprint plan.
    Exports fix_assessment.csv and next_sprint_plan.csv.
    """
    import os
    from comparison import compute_matched_comparison
    from drivers import compute_family_deltas

    eligible_runs = runs_clean[runs_clean["eligible"]].copy()
    matched_runs = eligible_runs[eligible_runs["in_matched_cohort"]].copy()
    matched_cells = set(matched_runs["cell_key"])

    _, _, comparison_df = compute_matched_comparison(
        eligible_runs, outcomes_clean, citations_clean, matched_cells
    )
    family_deltas = compute_family_deltas(
        eligible_runs, outcomes_clean, citations_clean, matched_cells
    )

    fix_df = compute_fix_assessment(comparison_df, family_deltas, fix_log)
    sprint_df = compute_next_sprint_plan(comparison_df, family_deltas)

    os.makedirs(output_dir, exist_ok=True)
    fix_df.to_csv(os.path.join(output_dir, "fix_assessment.csv"), index=False)
    sprint_df.to_csv(os.path.join(output_dir, "next_sprint_plan.csv"), index=False)

    return fix_df, sprint_df

