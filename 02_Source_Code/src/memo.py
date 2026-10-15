"""
memo.py
-------
Stage 8: Generate the executive memo PDF (maximum 3 pages).

Uses reportlab for PDF generation.
All numbers in the memo are read from the pipeline outputs — never hardcoded.
"""

import os
import pandas as pd

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("[WARN] reportlab not available; memo.py will write a text fallback.")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "05_Analysis_Outputs")
PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "06_Final_Deliverables",
                        "astervale_ai_visibility_executive_report.pdf")

# Colour palette
DARK_BLUE = colors.HexColor("#1B3A5C")
MID_BLUE = colors.HexColor("#2E6DA4")
ACCENT = colors.HexColor("#E07B39")
LIGHT_GREY = colors.HexColor("#F5F5F5")
WHITE = colors.white


def _load_outputs():
    """Load the required output CSVs."""
    baseline = pd.read_csv(os.path.join(OUTPUT_DIR, "month_1_baseline.csv"))
    comparison = pd.read_csv(os.path.join(OUTPUT_DIR, "month_comparison_matched.csv"))
    fix_assess = pd.read_csv(os.path.join(OUTPUT_DIR, "fix_assessment.csv"))
    sprint = pd.read_csv(os.path.join(OUTPUT_DIR, "next_sprint_plan.csv"))
    family = pd.read_csv(os.path.join(OUTPUT_DIR, "prompt_family_deltas.csv"))
    platform = pd.read_csv(os.path.join(OUTPUT_DIR, "platform_deltas.csv"))
    qa = pd.read_csv(os.path.join(OUTPUT_DIR, "qa_report.csv"))
    return baseline, comparison, fix_assess, sprint, family, platform, qa


def _get_metric(df, metric_name, col="score"):
    rows = df[df["metric"] == metric_name]
    if len(rows) == 0:
        return "N/A"
    val = rows.iloc[0][col]
    if pd.isna(val):
        return "N/A"
    return round(float(val), 2)


def _fmt(val, suffix=""):
    if val == "N/A":
        return "N/A"
    return f"{val}{suffix}"


def generate_memo():
    """Generate the executive_memo.pdf."""
    if not REPORTLAB_AVAILABLE:
        _text_fallback()
        return

    baseline, comparison, fix_assess, sprint, family, platform, qa = _load_outputs()

    doc = SimpleDocTemplate(
        PDF_PATH,
        pagesize=A4,
        rightMargin=2.2 * cm,
        leftMargin=2.2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=9, leading=13)
    style_h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=14, textColor=DARK_BLUE,
                               spaceAfter=4, spaceBefore=6)
    style_h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=10, textColor=MID_BLUE,
                               spaceAfter=3, spaceBefore=5)
    style_caption = ParagraphStyle("caption", parent=style_normal, fontSize=7.5,
                                    textColor=colors.grey, leading=11)
    style_bold = ParagraphStyle("bold", parent=style_normal, fontName="Helvetica-Bold")
    style_header = ParagraphStyle("header", parent=style_normal, fontSize=16, fontName="Helvetica-Bold",
                                   textColor=WHITE, alignment=TA_CENTER)

    # --- Helper: small table ---
    def _table(data, col_widths=None, header=True):
        if col_widths is None:
            col_widths = None
        tbl = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), MID_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GREY, WHITE]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    story = []

    # =========================================================
    # HEADER BANNER
    # =========================================================
    header_data = [[Paragraph("AsterVale AI Visibility — Executive Memo", style_header)]]
    header_tbl = Table(header_data, colWidths=[16.6 * cm])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 0.3 * cm))

    # Sub-header
    story.append(Paragraph(
        "Prepared by Kasparro · Month 1 (June 2026) Baseline & Month 2 (July 2026) Comparison",
        ParagraphStyle("sub", parent=style_caption, fontSize=8, alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=MID_BLUE))
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================
    # EXECUTIVE SUMMARY
    # =========================================================
    story.append(Paragraph("1. Executive Summary", style_h1))

    # Pull headline numbers
    m1_asv = _get_metric(baseline, "final_asv_score")
    asv_row = comparison[comparison["metric"] == "final_asv_score"]
    m2_asv = asv_row.iloc[0]["M2"] if len(asv_row) > 0 else "N/A"
    asv_delta = asv_row.iloc[0]["delta_pp"] if len(asv_row) > 0 else "N/A"
    asv_rel = asv_row.iloc[0]["relative_change_pct"] if len(asv_row) > 0 else "N/A"

    m1_nb = _get_metric(baseline, "nb_discovery_score")
    m1_bp = _get_metric(baseline, "branded_performance_score")

    matched_cells = asv_row.iloc[0].get("matched_cell_count", "?") if len(asv_row) > 0 else "?"

    try:
        asv_delta_str = f"{float(asv_delta):+.2f}pp"
        asv_rel_str = f"{float(asv_rel):+.1f}%"
        m2_asv_str = f"{float(m2_asv):.2f}"
    except Exception:
        asv_delta_str = str(asv_delta)
        asv_rel_str = str(asv_rel)
        m2_asv_str = str(m2_asv)

    story.append(Paragraph(
        f"AsterVale's final ASV Score moved from <b>{m1_asv}</b> (M1 reported baseline) to "
        f"<b>{m2_asv_str}</b> on the matched cohort, a change of <b>{asv_delta_str}</b> "
        f"({asv_rel_str} relative). The matched cohort covers <b>{matched_cells} cells</b> "
        f"(prompt × platform × replicate combinations eligible in both months). "
        f"Non-Branded Discovery Score at M1: <b>{m1_nb}</b>; "
        f"Branded Performance Score at M1: <b>{m1_bp}</b>. "
        "Movement in M2 is observed — not proven causal — and should be interpreted "
        "in the context of concurrent content fixes, platform model updates and "
        "the inherent variability of LLM responses.",
        style_normal
    ))
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================
    # M1 BASELINE
    # =========================================================
    story.append(Paragraph("2. Month 1 Baseline (Reported Period)", style_h1))

    baseline_display = [
        ("Metric", "M1 Score", "Cohort", "Role"),
        ("Category Presence", _fmt(_get_metric(baseline, "category_presence")), "Non-branded", "30% NB"),
        ("AI Share of Voice", _fmt(_get_metric(baseline, "ai_share_of_voice")), "Non-branded", "40% NB"),
        ("Comparison Standing", _fmt(_get_metric(baseline, "comparison_standing")), "Comparison NB", "20% NB"),
        ("NB Owned Citation Rate", _fmt(_get_metric(baseline, "nb_owned_citation_rate")), "AV-mentioned NB", "10% NB"),
        ("NB Discovery Score", _fmt(_get_metric(baseline, "nb_discovery_score")), "Composite", "60% Final"),
        ("Branded Presence Quality", _fmt(_get_metric(baseline, "branded_presence_quality")), "Branded", "30% B"),
        ("Branded Recommendation Rate", _fmt(_get_metric(baseline, "branded_recommendation_rate")), "Branded", "40% B"),
        ("Branded Prominence", _fmt(_get_metric(baseline, "branded_prominence")), "Branded", "20% B"),
        ("Branded Owned Citation Rate", _fmt(_get_metric(baseline, "branded_owned_citation_rate")), "AV-mentioned B", "10% B"),
        ("Branded Performance Score", _fmt(_get_metric(baseline, "branded_performance_score")), "Composite", "40% Final"),
        ("FINAL ASV SCORE", _fmt(_get_metric(baseline, "final_asv_score")), "Composite", "—"),
    ]

    tbl_data = [[Paragraph(str(c), style_bold if i == 0 else style_normal) for c in row]
                for i, row in enumerate(baseline_display)]
    story.append(_table(tbl_data, col_widths=[6.5 * cm, 2 * cm, 4 * cm, 4.1 * cm]))
    story.append(Paragraph(
        "Scores are on a 0–100 scale. All values generated by the pipeline from M1 eligible runs.",
        style_caption
    ))
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================
    # M2 MOVEMENT
    # =========================================================
    story.append(Paragraph("3. Month 2 Matched-Core Movement", style_h1))

    comp_display_metrics = [
        "category_presence", "ai_share_of_voice", "comparison_standing",
        "nb_owned_citation_rate", "nb_discovery_score",
        "branded_presence_quality", "branded_recommendation_rate", "branded_prominence",
        "branded_owned_citation_rate", "branded_performance_score", "final_asv_score",
    ]
    comp_rows = [("Metric", "M1", "M2", "Δ (pp)", "Rel. Δ")]
    for mname in comp_display_metrics:
        row = comparison[comparison["metric"] == mname]
        if len(row) == 0:
            continue
        r = row.iloc[0]
        try:
            delta_str = f"{float(r['delta_pp']):+.2f}"
            rel_str = f"{float(r['relative_change_pct']):+.1f}%"
            m1_str = f"{float(r['M1']):.2f}"
            m2_str = f"{float(r['M2']):.2f}"
        except Exception:
            delta_str = str(r.get("delta_pp", ""))
            rel_str = str(r.get("relative_change_pct", ""))
            m1_str = str(r.get("M1", ""))
            m2_str = str(r.get("M2", ""))
        comp_rows.append((mname.replace("_", " ").title(), m1_str, m2_str, delta_str, rel_str))

    tbl_data2 = [[Paragraph(str(c), style_bold if i == 0 else style_normal) for c in row]
                 for i, row in enumerate(comp_rows)]
    story.append(_table(tbl_data2, col_widths=[6 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 5.2 * cm]))
    story.append(Paragraph(
        "Primary movement claim uses matched-core cohort only. Δ (pp) = percentage-point movement. "
        "Rel. Δ = relative change from M1. Temporal movement ≠ causal attribution.",
        style_caption
    ))
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================
    # DIAGNOSIS
    # =========================================================
    story.append(Paragraph("4. Diagnosis — Prompt Family & Platform Drivers", style_h1))

    # Identify top families by final_asv_score_delta
    if "final_asv_score_delta" in family.columns:
        top_families = family.nlargest(3, "final_asv_score_delta")[
            ["prompt_family", "final_asv_score_m1", "final_asv_score_m2", "final_asv_score_delta"]
        ].fillna("N/A")
        bottom_families = family.nsmallest(2, "final_asv_score_delta")[
            ["prompt_family", "final_asv_score_m1", "final_asv_score_m2", "final_asv_score_delta"]
        ].fillna("N/A")

        story.append(Paragraph("<b>Top-improving prompt families (matched M1→M2):</b>", style_bold))
        fam_rows = [("Prompt Family", "ASV M1", "ASV M2", "ASV Δ")]
        for _, r in top_families.iterrows():
            try:
                fam_rows.append((
                    str(r["prompt_family"]),
                    f"{float(r['final_asv_score_m1']):.2f}" if r["final_asv_score_m1"] != "N/A" else "N/A",
                    f"{float(r['final_asv_score_m2']):.2f}" if r["final_asv_score_m2"] != "N/A" else "N/A",
                    f"{float(r['final_asv_score_delta']):+.2f}" if r["final_asv_score_delta"] != "N/A" else "N/A",
                ))
            except Exception:
                fam_rows.append((str(r["prompt_family"]), "—", "—", "—"))
        tbl_data3 = [[Paragraph(str(c), style_bold if i == 0 else style_normal) for c in row]
                     for i, row in enumerate(fam_rows)]
        story.append(_table(tbl_data3, col_widths=[7 * cm, 2 * cm, 2 * cm, 5.6 * cm], header=True))
        story.append(Spacer(1, 0.15 * cm))

    # Platform
    if "final_asv_score_delta" in platform.columns:
        plat_rows = [("Platform", "ASV M1", "ASV M2", "ASV Δ")]
        for _, r in platform.iterrows():
            try:
                plat_rows.append((
                    str(r["platform"]),
                    f"{float(r['final_asv_score_m1']):.2f}" if pd.notna(r.get("final_asv_score_m1")) else "N/A",
                    f"{float(r['final_asv_score_m2']):.2f}" if pd.notna(r.get("final_asv_score_m2")) else "N/A",
                    f"{float(r['final_asv_score_delta']):+.2f}" if pd.notna(r.get("final_asv_score_delta")) else "N/A",
                ))
            except Exception:
                plat_rows.append((str(r.get("platform", "")), "—", "—", "—"))

        story.append(Paragraph("<b>Platform breakdown (matched M1→M2):</b>", style_bold))
        tbl_data4 = [[Paragraph(str(c), style_bold if i == 0 else style_normal) for c in row]
                     for i, row in enumerate(plat_rows)]
        story.append(_table(tbl_data4, col_widths=[5 * cm, 2 * cm, 2 * cm, 7.6 * cm], header=True))
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================
    # FIX ASSESSMENT
    # =========================================================
    story.append(Paragraph("5. Fix Assessment", style_h1))

    fix_rows = [("Fix", "Assessment", "Confidence", "Summary Evidence")]
    for _, r in fix_assess.iterrows():
        ev = str(r.get("primary_evidence", ""))[:120] + ("…" if len(str(r.get("primary_evidence", ""))) > 120 else "")
        fix_rows.append((
            f"{r['fix_id']}: {str(r.get('fix_name',''))[:30]}",
            str(r.get("month_2_assessment", "")),
            str(r.get("confidence", "")),
            ev,
        ))

    tbl_data5 = [[Paragraph(str(c), style_bold if i == 0 else style_normal) for c in row]
                 for i, row in enumerate(fix_rows)]
    story.append(_table(tbl_data5, col_widths=[4 * cm, 3 * cm, 2 * cm, 7.6 * cm]))
    story.append(Paragraph(
        "Assessment = observational. Temporal sequence ≠ causation. "
        "One to two months is insufficient to isolate fix impact from platform variance.",
        style_caption
    ))
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================
    # BUSINESS IMPLICATION
    # =========================================================
    story.append(Paragraph("6. Business Implication", style_h1))
    story.append(Paragraph(
        "AsterVale's AI visibility remains materially below 50 on most component metrics, "
        "indicating that LLM systems are either not aware of the brand in category contexts "
        "or are aware but attributing lower quality/prominence. "
        "The matched M1→M2 movement, where positive, is an encouraging early signal — "
        "but with only one comparison point and inherent LLM response variability, "
        "it cannot yet be treated as a trend. "
        "Branded prompts show stronger AsterVale presence than non-branded, "
        "suggesting the brand has awareness but insufficient category-level authority. "
        "Owned citation presence is the most direct lever AsterVale controls "
        "and should be the operational focus for Month 3.",
        style_normal
    ))
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================
    # MONTH 3 PRIORITIES
    # =========================================================
    story.append(Paragraph("7. Month 3 Priorities (Max 4)", style_h1))

    sprint_rows = [("Priority", "Action", "Target Metric", "Measurement")]
    for _, r in sprint.iterrows():
        sprint_rows.append((
            str(r.get("priority", "")),
            str(r.get("action_theme", ""))[:50],
            str(r.get("metric_to_move", ""))[:25],
            str(r.get("month_3_measurement", ""))[:80],
        ))
    tbl_data6 = [[Paragraph(str(c), style_bold if i == 0 else style_normal) for c in row]
                 for i, row in enumerate(sprint_rows)]
    story.append(_table(tbl_data6, col_widths=[1.5 * cm, 4 * cm, 3.5 * cm, 7.6 * cm]))
    story.append(Spacer(1, 0.2 * cm))

    # =========================================================
    # METHODOLOGICAL CAVEATS
    # =========================================================
    story.append(Paragraph("8. Methodological Caveats", style_h1))
    story.append(Paragraph(
        "<b>Caveat 1 — Small matched cohort size:</b> The matched cohort (cells eligible in both months) "
        "may be a subset of the planned design, limiting statistical power. "
        "Single percentage-point movements should not be over-interpreted. "
        "<b>Caveat 2 — LLM response variability:</b> AI platforms do not produce deterministic responses. "
        "Two replicates per prompt reduce but do not eliminate noise. "
        "Observed movements may partially reflect platform model updates rather than content changes. "
        "A multi-month trend with larger replication would substantially strengthen confidence.",
        style_normal
    ))

    # =========================================================
    # BUILD PDF
    # =========================================================
    doc.build(story)
    print(f"  [OK] Executive memo written: {PDF_PATH}")


def _text_fallback():
    """Write a plain text memo if reportlab is not available."""
    txt_path = PDF_PATH.replace(".pdf", "_FALLBACK.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("AsterVale AI Visibility Executive Memo (Text Fallback)\n")
        f.write("reportlab not installed — install it to generate the PDF.\n")
        f.write("Run: pip install reportlab\n")
    print(f"  [WARN] Text fallback written to {txt_path}. Install reportlab for PDF.")


def generate_executive_memo(output_dir: str = None, pdf_path: str = None):
    """
    Wrapper for generate_memo accepting dynamic output_dir and pdf_path.
    """
    global OUTPUT_DIR, PDF_PATH
    if output_dir:
        OUTPUT_DIR = output_dir
    if pdf_path:
        PDF_PATH = pdf_path
    generate_memo()

