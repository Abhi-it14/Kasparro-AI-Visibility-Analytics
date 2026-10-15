"""
ingest.py
---------
Stage 1: Load and deduplicate all raw source files.

Rules applied here:
- Runs: deduplicate by run_id, retaining the row with the latest valid ingested_at.
  (Error-status rows are included for dedup comparison but flagged; success rows take
  priority.  If multiple ingested_at timestamps exist for the same run_id, keep the
  latest regardless of status, then status filter happens downstream in eligibility.)
- Outcomes: raw load; dedup happens in eligibility (keep latest per run_id + brand).
- Citations: raw load; canonicalization and dedup in eligibility.
- All other reference files: load as-is.
"""

import json
import os
import pandas as pd

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "03_Input_Data")


def _data(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)


# ---------------------------------------------------------------------------
# Reference files
# ---------------------------------------------------------------------------

def load_brand_master() -> pd.DataFrame:
    """Load canonical brand list with alias and domain information."""
    df = pd.read_csv(_data("brand_master.csv"), dtype=str)
    # Expand pipe-delimited aliases into a Python list per row
    df["alias_list"] = df["aliases"].fillna("").apply(
        lambda s: [a.strip() for a in s.split("|") if a.strip()]
    )
    return df


def load_prompt_bank() -> pd.DataFrame:
    """Load prompt bank with locked-core and family metadata."""
    df = pd.read_csv(_data("prompt_bank.csv"), dtype=str)
    # Coerce numeric columns
    df["locked_core_prompt"] = pd.to_numeric(df["locked_core_prompt"], errors="coerce").fillna(0).astype(int)
    df["comparison_eligible"] = pd.to_numeric(df["comparison_eligible"], errors="coerce").fillna(0).astype(int)
    df["prompt_weight"] = pd.to_numeric(df["prompt_weight"], errors="coerce").fillna(1.0).astype(float)
    return df


def load_fix_log() -> pd.DataFrame:
    """Load fix deployment log."""
    return pd.read_csv(_data("fix_deployment_log.csv"), dtype=str)


# ---------------------------------------------------------------------------
# Run records
# ---------------------------------------------------------------------------

def _load_jsonl(filepath: str) -> pd.DataFrame:
    """Load a JSONL file into a DataFrame. Each line is one JSON object."""
    records = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    # Malformed line — log and skip
                    print(f"  [WARN] Skipping malformed JSONL line in {filepath}: {line[:80]}")
    return pd.DataFrame(records)


def load_runs_raw() -> pd.DataFrame:
    """Load Month 1 and Month 2 run records and concatenate."""
    m1 = _load_jsonl(_data("month_1_runs.jsonl"))
    m2 = _load_jsonl(_data("month_2_runs.jsonl"))
    combined = pd.concat([m1, m2], ignore_index=True)
    combined["audit_month"] = combined["audit_month"].astype(str).str.strip()
    return combined


def deduplicate_runs(raw_runs: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate run records by run_id.

    Rule: retain the row with the latest valid ingested_at.
    'Valid' means parseable as a datetime. Rows with unparseable ingested_at
    are treated as earliest (NaT → 1970-01-01) so they are displaced by real rows.

    Returns a DataFrame indexed by run_id with the winning row for each run_id.
    The original index is reset; a 'raw_row_count' QA column is NOT added here
    (that is produced in the QA report).
    """
    df = raw_runs.copy()
    df["ingested_at_parsed"] = pd.to_datetime(df["ingested_at"], errors="coerce", utc=True)
    # Replace NaT with epoch so sort works (NaT rows lose the dedup race)
    df["ingested_at_parsed"] = df["ingested_at_parsed"].fillna(
        pd.Timestamp("1970-01-01", tz="UTC")
    )
    # Sort by run_id then by ingested_at descending, keep first
    df = df.sort_values(["run_id", "ingested_at_parsed"], ascending=[True, False])
    deduped = df.drop_duplicates(subset=["run_id"], keep="first").reset_index(drop=True)
    return deduped


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

def load_outcomes_raw() -> pd.DataFrame:
    """Load coded brand outcomes. Raw; cleaning happens in eligibility."""
    df = pd.read_csv(_data("coded_brand_outcomes.csv"), dtype=str, low_memory=False)
    return df


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------

def load_citations_raw() -> pd.DataFrame:
    """Load citation ledger. Raw; canonicalization happens in eligibility."""
    df = pd.read_csv(_data("citations.csv"), dtype=str, low_memory=False)
    return df


# ---------------------------------------------------------------------------
# Master Ingestion Pipeline Orchestrator
# ---------------------------------------------------------------------------

def load_and_ingest_all(data_dir: str = None) -> dict:
    """
    Load all raw datasets and deduplicate runs.
    """
    global DATA_DIR
    if data_dir:
        DATA_DIR = data_dir

    brand_master = load_brand_master()
    prompt_bank = load_prompt_bank()
    fix_log = load_fix_log()
    runs_raw = load_runs_raw()
    runs_deduped = deduplicate_runs(runs_raw)
    outcomes_raw = load_outcomes_raw()
    citations_raw = load_citations_raw()

    return {
        "brand_master": brand_master,
        "prompt_bank": prompt_bank,
        "fix_log": fix_log,
        "runs_raw": runs_raw,
        "runs_deduped": runs_deduped,
        "outcomes_raw": outcomes_raw,
        "citations_raw": citations_raw,
    }

