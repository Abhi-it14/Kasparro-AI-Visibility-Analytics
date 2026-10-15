"""
eligibility.py
--------------
Stage 2: Apply all deterministic eligibility rules from the assignment brief §5.

Produces:
  outputs/runs_clean.csv      — all deduped runs with eligibility flags
  outputs/outcomes_clean.csv  — all valid/normalized outcomes for eligible runs
  outputs/citations_clean.csv — valid canonical citations for eligible runs
  outputs/qa_report.csv       — full reconciliation of counts and exclusions

Key rules implemented:
  5.1 Run eligibility  (8 rules, cascade — any failure excludes the whole run)
  5.2 Outcome rules    (brand resolution, boolean parsing, rank parsing, hierarchy)
  5.3 Citation rules   (URL canonicalization, dedup, owned-status)
"""

import os
import re
import urllib.parse
import pandas as pd
import numpy as np

CANONICAL_BRANDS = ["B001", "B002", "B003", "B004", "B005"]
ALLOWED_PLATFORMS = {"ChatAssist", "SearchAI", "AnswerMind"}
ALLOWED_REPLICATES = {"1", "2", 1, 2}
RANK_SCORE_MAP = {1: 100, 2: 75, 3: 50, 4: 25}  # 5 or unmentioned → 0

# ---------------------------------------------------------------------------
# Boolean parsing
# ---------------------------------------------------------------------------

_TRUE_VALS = {"true", "yes", "1"}
_FALSE_VALS = {"false", "no", "0"}


def parse_bool(val) -> bool | None:
    """
    Parse flexible boolean representations.
    Returns True, False, or None if the value cannot be resolved.
    None signals a structural error in the outcome row.
    """
    if pd.isna(val) or str(val).strip() == "":
        return None
    s = str(val).strip().lower()
    if s in _TRUE_VALS:
        return True
    if s in _FALSE_VALS:
        return False
    return None  # Unrecognised → structural error


# ---------------------------------------------------------------------------
# Rank parsing
# ---------------------------------------------------------------------------

_ORDINAL_MAP = {
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
}


def parse_rank(val) -> int | None:
    """
    Parse rank representations:
      - Integers 1-5
      - Floats that are whole numbers (e.g. 2.0 → 2)
      - Ordinal strings (e.g. "1st", "2nd")
    Returns None if the value is blank/missing.
    Returns -1 if the value cannot be parsed or is outside 1-5 (structural error).
    """
    if pd.isna(val) or str(val).strip() == "":
        return None  # No rank — acceptable for unmentioned brands
    s = str(val).strip().lower()
    if s in _ORDINAL_MAP:
        return _ORDINAL_MAP[s]
    try:
        f = float(s)
        if f == int(f) and 1 <= int(f) <= 5:
            return int(f)
        return -1  # Out of range or non-whole float
    except ValueError:
        return -1  # Cannot parse → structural error


# ---------------------------------------------------------------------------
# Brand alias resolution
# ---------------------------------------------------------------------------

def build_alias_lookup(brand_master: pd.DataFrame) -> dict:
    """
    Build a dict mapping every alias (lower-cased) → brand_id.
    Also maps brand_id itself → brand_id for identity lookups.
    """
    lookup = {}
    for _, row in brand_master.iterrows():
        bid = row["brand_id"]
        for alias in row["alias_list"]:
            lookup[alias.lower()] = bid
        # Map brand_name itself
        lookup[row["brand_name"].lower()] = bid
        # Map brand_id itself
        lookup[bid.lower()] = bid
    return lookup


def resolve_brand(brand_id_raw: str, brand_raw: str, alias_lookup: dict) -> str | None:
    """
    Resolve a raw brand reference to a canonical brand_id.
    Priority: brand_id field first (if non-empty and valid), then alias lookup on brand_raw.
    Returns None if unresolvable.
    """
    if brand_id_raw and str(brand_id_raw).strip() in CANONICAL_BRANDS:
        return str(brand_id_raw).strip()
    if brand_raw and str(brand_raw).strip():
        key = str(brand_raw).strip().lower()
        return alias_lookup.get(key)
    return None


# ---------------------------------------------------------------------------
# AsterVale alias presence check
# ---------------------------------------------------------------------------

def astervale_mentioned_in_text(response_text: str, av_aliases: list) -> bool:
    """
    Check if any AsterVale alias appears in the response text (case-insensitive).
    Used to validate consistency with the 'mentioned' code.
    """
    if not response_text:
        return False
    text_lower = str(response_text).lower()
    return any(alias.lower() in text_lower for alias in av_aliases)


# ---------------------------------------------------------------------------
# URL canonicalization
# ---------------------------------------------------------------------------

def canonicalize_url(raw_url: str) -> str | None:
    """
    Apply the 6-step URL canonicalization algorithm from §5.3.
    Returns None if the URL is invalid (not HTTP/HTTPS with host).
    """
    if not raw_url or pd.isna(raw_url):
        return None
    raw = str(raw_url).strip()

    # Step 1: Parse and require HTTP or HTTPS
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return None
    if parsed.scheme.lower() not in ("http", "https"):
        return None
    if not parsed.hostname:
        return None

    # Step 2: Lowercase scheme and host; remove leading www.
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    if host.startswith("www."):
        host = host[4:]

    # Step 3: Collapse repeated path slashes; remove trailing slash except root
    path = parsed.path
    path = re.sub(r"/+", "/", path)  # Collapse repeated slashes
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Step 4: Remove fragment (ignore parsed.fragment)

    # Step 5: Remove utm_*, gclid, fbclid from query; alphabetically sort the rest
    DROP_PARAMS = {"gclid", "fbclid"}
    if parsed.query:
        params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        kept = [(k, v) for k, v in params
                if not k.lower().startswith("utm_")
                and k.lower() not in DROP_PARAMS]
        kept_sorted = sorted(kept, key=lambda x: x[0].lower())
        query_str = urllib.parse.urlencode(kept_sorted)
    else:
        query_str = ""

    # Reconstruct canonical URL
    canonical = urllib.parse.urlunparse((scheme, host, path, "", query_str, ""))
    return canonical


# ---------------------------------------------------------------------------
# Core eligibility pipeline
# ---------------------------------------------------------------------------

def build_eligible_runs(
    deduped_runs: pd.DataFrame,
    prompt_bank: pd.DataFrame,
    brand_master: pd.DataFrame,
    outcomes_raw: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Apply §5.1 and §5.2 rules to produce eligible runs and outcomes.

    Returns:
      runs_clean      — all deduped runs with eligibility metadata
      outcomes_clean  — normalized outcomes for eligible runs only
      qa_counts       — dict of counts for QA report
    """
    qa = {}
    alias_lookup = build_alias_lookup(brand_master)

    # AsterVale aliases
    av_row = brand_master[brand_master["brand_id"] == "B001"].iloc[0]
    av_aliases = av_row["alias_list"]

    # Prompt bank index
    locked_prompts = set(
        prompt_bank[prompt_bank["locked_core_prompt"] == 1]["prompt_id"].tolist()
    )
    prompt_info = prompt_bank.set_index("prompt_id")[
        ["prompt_family", "brand_mode", "comparison_eligible"]
    ].to_dict(orient="index")

    # -----------------------------------------------------------------------
    # Stage 1: raw counts
    # -----------------------------------------------------------------------
    qa["runs_raw_total"] = len(deduped_runs)
    m1_raw = deduped_runs[deduped_runs["audit_month"] == "M1"]
    m2_raw = deduped_runs[deduped_runs["audit_month"] == "M2"]
    qa["runs_raw_M1"] = len(m1_raw)
    qa["runs_raw_M2"] = len(m2_raw)

    # -----------------------------------------------------------------------
    # Prepare outcomes: resolve brands and normalize
    # -----------------------------------------------------------------------
    outcomes_norm = _normalize_outcomes(outcomes_raw, alias_lookup)
    qa["outcomes_raw_total"] = len(outcomes_raw)

    # -----------------------------------------------------------------------
    # Stage 2: Apply §5.1 filters to runs
    # -----------------------------------------------------------------------
    runs = deduped_runs.copy()
    runs["exclusion_reason"] = ""
    runs["eligible"] = True

    def _exclude(mask, reason):
        """Mark rows matching mask with reason (accumulate reasons)."""
        existing = runs.loc[mask, "exclusion_reason"]
        runs.loc[mask, "exclusion_reason"] = existing.where(
            existing == "", existing + "; " + reason
        ).where(existing != "", reason)
        runs.loc[mask, "eligible"] = False

    # Rule 1: locked_core_prompt
    non_locked = ~runs["prompt_id"].isin(locked_prompts)
    _exclude(non_locked, "prompt_not_locked_core")
    qa["excluded_not_locked"] = non_locked.sum()

    # Rule 2: allowed platforms
    bad_platform = ~runs["platform"].isin(ALLOWED_PLATFORMS)
    _exclude(bad_platform, "disallowed_platform")
    qa["excluded_bad_platform"] = bad_platform.sum()

    # Rule 3: allowed replicates
    bad_replicate = ~runs["replicate"].astype(str).isin({"1", "2"})
    _exclude(bad_replicate, "disallowed_replicate")
    qa["excluded_bad_replicate"] = bad_replicate.sum()

    # Rule 4: run_status = success
    not_success = runs["run_status"] != "success"
    _exclude(not_success, "run_status_not_success")
    qa["excluded_not_success"] = not_success.sum()

    # For remaining checks, work only on still-eligible runs to avoid false exclusion counts
    eligible_mask = runs["eligible"]

    # -----------------------------------------------------------------------
    # Rules 5–8: outcome-level checks per run (only for currently eligible)
    # -----------------------------------------------------------------------
    # Build outcome index: run_id → {brand_id: normalized_row}
    outcome_index = {}
    for run_id, grp in outcomes_norm.groupby("run_id_clean"):
        outcome_index[run_id] = {row["canonical_brand_id"]: row for _, row in grp.iterrows()}

    exclude_5brand = []
    exclude_structural = []
    exclude_alias = []

    for idx, row in runs[eligible_mask].iterrows():
        run_id = row["run_id"]
        outcomes = outcome_index.get(run_id, {})

        # Rule 5: exactly one outcome per canonical brand
        if set(outcomes.keys()) != set(CANONICAL_BRANDS):
            missing = set(CANONICAL_BRANDS) - set(outcomes.keys())
            extra = set(outcomes.keys()) - set(CANONICAL_BRANDS)
            exclude_5brand.append((idx, f"missing_brands:{missing}|extra:{extra}"))
            continue

        # Rule 6: structural validity of each outcome
        structural_ok = True
        for bid, orow in outcomes.items():
            if not _structural_valid(orow):
                structural_ok = False
                break
        if not structural_ok:
            exclude_structural.append(idx)
            continue

        # Rule 7: AsterVale alias-mentioned consistency
        av_outcome = outcomes.get("B001", {})
        av_mentioned_code = av_outcome.get("mentioned_parsed", None)
        response_text = str(row.get("response_text", ""))
        av_in_text = astervale_mentioned_in_text(response_text, av_aliases)
        # If code says mentioned=True but AV doesn't appear in text, or vice versa
        if av_mentioned_code is not None and av_in_text != av_mentioned_code:
            exclude_alias.append(idx)

    for idx, reason in exclude_5brand:
        runs.loc[idx, "exclusion_reason"] = (
            (runs.loc[idx, "exclusion_reason"] + "; " if runs.loc[idx, "exclusion_reason"] else "")
            + f"incomplete_brand_coverage ({reason})"
        )
        runs.loc[idx, "eligible"] = False

    for idx in exclude_structural:
        runs.loc[idx, "exclusion_reason"] = (
            (runs.loc[idx, "exclusion_reason"] + "; " if runs.loc[idx, "exclusion_reason"] else "")
            + "structural_outcome_failure"
        )
        runs.loc[idx, "eligible"] = False

    for idx in exclude_alias:
        runs.loc[idx, "exclusion_reason"] = (
            (runs.loc[idx, "exclusion_reason"] + "; " if runs.loc[idx, "exclusion_reason"] else "")
            + "av_alias_mentioned_mismatch"
        )
        runs.loc[idx, "eligible"] = False

    qa["excluded_incomplete_5brand"] = len(exclude_5brand)
    qa["excluded_structural"] = len(exclude_structural)
    qa["excluded_av_alias_mismatch"] = len(exclude_alias)

    # -----------------------------------------------------------------------
    # Annotate eligible runs with prompt metadata
    # -----------------------------------------------------------------------
    runs["prompt_family"] = runs["prompt_id"].map(
        lambda pid: prompt_info.get(pid, {}).get("prompt_family", "unknown")
    )
    runs["brand_mode"] = runs["prompt_id"].map(
        lambda pid: prompt_info.get(pid, {}).get("brand_mode", "unknown")
    )
    runs["comparison_eligible"] = runs["prompt_id"].map(
        lambda pid: int(prompt_info.get(pid, {}).get("comparison_eligible", 0))
    )
    runs["cell_key"] = runs["prompt_id"] + "|" + runs["platform"] + "|" + runs["replicate"].astype(str)

    # -----------------------------------------------------------------------
    # QA summary
    # -----------------------------------------------------------------------
    total_eligible = runs["eligible"].sum()
    qa["runs_eligible_total"] = int(total_eligible)
    qa["runs_eligible_M1"] = int(runs[runs["audit_month"] == "M1"]["eligible"].sum())
    qa["runs_eligible_M2"] = int(runs[runs["audit_month"] == "M2"]["eligible"].sum())
    qa["runs_excluded_total"] = int((~runs["eligible"]).sum())

    # -----------------------------------------------------------------------
    # Build outcomes for eligible runs only
    # -----------------------------------------------------------------------
    eligible_run_ids = set(runs[runs["eligible"]]["run_id"].tolist())
    outcomes_eligible = outcomes_norm[outcomes_norm["run_id_clean"].isin(eligible_run_ids)].copy()
    qa["outcomes_eligible_rows"] = len(outcomes_eligible)

    return runs, outcomes_eligible, qa


def _normalize_outcomes(outcomes_raw: pd.DataFrame, alias_lookup: dict) -> pd.DataFrame:
    """
    Normalize raw outcome rows:
    - Resolve canonical brand_id
    - Parse booleans
    - Parse ranks
    - Enforce hierarchy implications
    - Deduplicate by run_id + canonical_brand_id (keep latest coding_timestamp)
    """
    df = outcomes_raw.copy()
    df["run_id_clean"] = df["run_id"].astype(str).str.strip()
    df["coding_ts"] = pd.to_datetime(df["coding_timestamp"], errors="coerce", utc=True)
    df["coding_ts"] = df["coding_ts"].fillna(pd.Timestamp("1970-01-01", tz="UTC"))

    # Resolve canonical brand
    df["canonical_brand_id"] = df.apply(
        lambda r: resolve_brand(r.get("brand_id", ""), r.get("brand_raw", ""), alias_lookup),
        axis=1,
    )

    # Parse booleans
    for col in ["mentioned", "shortlisted", "recommended", "top_choice", "discouraged"]:
        df[f"{col}_parsed"] = df[col].apply(parse_bool)

    # Parse integer quality columns
    for col in ["factual_accuracy", "differentiation_present", "hedged"]:
        df[f"{col}_parsed"] = pd.to_numeric(df[col], errors="coerce")

    # Parse rank
    df["rank_parsed"] = df["rank"].apply(parse_rank)

    # Apply hierarchy: top_choice → recommended → shortlisted → mentioned
    df = _apply_hierarchy(df)

    # Deduplicate: keep latest coding_timestamp per run_id + canonical_brand_id
    df = df.sort_values(["run_id_clean", "canonical_brand_id", "coding_ts"], ascending=[True, True, False])
    df = df.drop_duplicates(subset=["run_id_clean", "canonical_brand_id"], keep="first")

    return df.reset_index(drop=True)


def _apply_hierarchy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enforce hierarchy: top_choice → recommended → shortlisted → mentioned.
    If top_choice=True then recommended, shortlisted, mentioned must also be True.
    """
    df = df.copy()
    top = df["top_choice_parsed"] == True
    rec = df["recommended_parsed"] == True
    short = df["shortlisted_parsed"] == True

    # top_choice implies recommended implies shortlisted implies mentioned
    df.loc[top, "recommended_parsed"] = True
    df.loc[top | rec, "shortlisted_parsed"] = True
    df.loc[top | rec | short, "mentioned_parsed"] = True

    return df


def _structural_valid(orow: pd.Series) -> bool:
    """
    Check structural validity of a single normalized outcome row.
    Returns False if any structural rule is violated.
    """
    # Brand must be resolvable
    if not orow.get("canonical_brand_id"):
        return False

    mentioned = orow.get("mentioned_parsed")
    shortlisted = orow.get("shortlisted_parsed")
    recommended = orow.get("recommended_parsed")
    top_choice = orow.get("top_choice_parsed")
    discouraged = orow.get("discouraged_parsed")
    rank = orow.get("rank_parsed")
    if pd.isna(rank):
        rank = None

    # All boolean fields must parse successfully
    for v in [mentioned, shortlisted, recommended, top_choice, discouraged]:
        if v is None or pd.isna(v):
            return False

    # Rank must parse if present
    if rank == -1:
        return False  # Unparseable rank value

    if not mentioned:
        # Unmentioned brand: rank must be None and all positive flags must be False
        if rank is not None:
            return False
        if shortlisted or recommended or top_choice:
            return False
    else:
        # Mentioned brand: rank must be present
        if rank is None:
            return False
        if not (1 <= rank <= 5):
            return False

    return True



# ---------------------------------------------------------------------------
# Citation eligibility
# ---------------------------------------------------------------------------

def build_eligible_citations(
    citations_raw: pd.DataFrame,
    brand_master: pd.DataFrame,
    eligible_run_ids: set,
) -> tuple[pd.DataFrame, dict]:
    """
    Apply §5.3 rules to produce clean canonical citations.

    Returns:
      citations_clean — valid deduped canonical citations for eligible runs
      qa_cit          — QA counts for citations
    """
    qa_cit = {}
    alias_lookup = build_alias_lookup(brand_master)
    domain_to_brand = {
        row["canonical_domain"].lower(): row["brand_id"]
        for _, row in brand_master.iterrows()
    }

    df = citations_raw.copy()
    qa_cit["citations_raw_total"] = len(df)

    # Filter to eligible runs
    df["run_id_clean"] = df["run_id"].astype(str).str.strip()
    df = df[df["run_id_clean"].isin(eligible_run_ids)].copy()
    qa_cit["citations_for_eligible_runs"] = len(df)

    # Canonicalize URL
    df["canonical_url"] = df["url"].apply(canonicalize_url)
    invalid_url = df["canonical_url"].isna()
    qa_cit["citations_invalid_url"] = int(invalid_url.sum())
    df = df[~invalid_url].copy()

    # Resolve canonical brand
    df["canonical_cited_brand_id"] = df.apply(
        lambda r: resolve_brand(
            r.get("cited_brand_id", ""),
            r.get("cited_brand_raw", ""),
            alias_lookup,
        ),
        axis=1,
    )

    # Determine owned status from canonical URL domain
    def _is_owned(url: str) -> bool:
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.hostname or ""
            return domain in domain_to_brand
        except Exception:
            return False

    df["is_owned"] = df["canonical_url"].apply(_is_owned)

    # Determine which brand owns the cited URL
    def _owning_brand(url: str) -> str | None:
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.hostname or ""
            return domain_to_brand.get(domain)
        except Exception:
            return None

    df["owning_brand_id"] = df["canonical_url"].apply(_owning_brand)

    # Deduplicate by run_id + canonical_cited_brand_id + canonical_url
    df = df.drop_duplicates(
        subset=["run_id_clean", "canonical_cited_brand_id", "canonical_url"],
        keep="first",
    )
    qa_cit["citations_after_dedup"] = len(df)

    return df.reset_index(drop=True), qa_cit


# ---------------------------------------------------------------------------
# Matched cohort
# ---------------------------------------------------------------------------

def build_matched_cohort(runs_clean: pd.DataFrame) -> tuple[pd.DataFrame, set]:
    """
    Identify cell_keys (prompt_id|platform|replicate) that are eligible
    in both M1 and M2. Return the subset of eligible runs for those cells.
    """
    eligible = runs_clean[runs_clean["eligible"]].copy()
    m1_cells = set(eligible[eligible["audit_month"] == "M1"]["cell_key"])
    m2_cells = set(eligible[eligible["audit_month"] == "M2"]["cell_key"])
    matched_cells = m1_cells & m2_cells
    matched = eligible[eligible["cell_key"].isin(matched_cells)].copy()
    matched["in_matched_cohort"] = True
    return matched, matched_cells


# ---------------------------------------------------------------------------
# Master Eligibility Pipeline Orchestrator
# ---------------------------------------------------------------------------

def run_eligibility_pipeline(data_dict: dict, output_dir: str) -> dict:
    """
    Run full Stage 1 & Stage 2 pipeline:
    - Runs eligibility & outcomes filtering
    - Citations canonicalization & deduplication
    - Matched cohort labeling
    - Export clean CSVs and QA report
    """
    brand_master = data_dict['brand_master']
    prompt_bank = data_dict['prompt_bank']
    runs_deduped = data_dict['runs_deduped']
    outcomes_raw = data_dict['outcomes_raw']
    citations_raw = data_dict['citations_raw']

    # 1. Runs & Outcomes eligibility
    runs_clean, outcomes_clean, qa_counts = build_eligible_runs(
        runs_deduped, prompt_bank, brand_master, outcomes_raw
    )

    # 2. Citations
    eligible_run_ids = set(runs_clean[runs_clean["eligible"]]["run_id"])
    citations_clean, qa_cit = build_eligible_citations(
        citations_raw, brand_master, eligible_run_ids
    )

    # 3. Matched cohort
    matched_runs, matched_cells = build_matched_cohort(runs_clean)
    runs_clean["in_matched_cohort"] = (
        runs_clean["eligible"] & runs_clean["cell_key"].isin(matched_cells)
    )

    # 4. Save outputs
    os.makedirs(output_dir, exist_ok=True)
    runs_clean.to_csv(os.path.join(output_dir, "runs_clean.csv"), index=False)
    outcomes_clean.to_csv(os.path.join(output_dir, "outcomes_clean.csv"), index=False)
    citations_clean.to_csv(os.path.join(output_dir, "citations_clean.csv"), index=False)

    # Build QA Report DataFrame
    qa_report_rows = []
    for k, v in qa_counts.items():
        qa_report_rows.append({"metric_category": "runs_qa", "metric_name": k, "metric_value": v})
    for k, v in qa_cit.items():
        qa_report_rows.append({"metric_category": "citations_qa", "metric_name": k, "metric_value": v})

    qa_report_rows.append({
        "metric_category": "matched_cohort_qa",
        "metric_name": "matched_cells_total",
        "metric_value": len(matched_cells)
    })
    qa_report_rows.append({
        "metric_category": "matched_cohort_qa",
        "metric_name": "matched_runs_total",
        "metric_value": len(matched_runs)
    })

    qa_report_df = pd.DataFrame(qa_report_rows)
    qa_report_df.to_csv(os.path.join(output_dir, "qa_report.csv"), index=False)

    return {
        "runs_clean": runs_clean,
        "outcomes_clean": outcomes_clean,
        "citations_clean": citations_clean,
        "prompt_bank": prompt_bank,
        "brand_master": brand_master,
        "qa_report_df": qa_report_df
    }

