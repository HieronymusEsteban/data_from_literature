"""
CTQ_SF_Xiang_etal_2021.py
==========================
Per-paper extractor for:
  Xiang Z, Liu Z, Cao H, Wu Z, Long Y. "Evaluation on Long-Term Test-Retest
  Reliability of the Short-Form Childhood Trauma Questionnaire in Patients
  with Schizophrenia." Psychol Res Behav Manag. 2021;14:1033-1040.

SOURCE TABLE
------------
Table 1 ("The Demographic and Clinical Characteristics of the Longitudinally
Followed Participants"), printed page 1036 -> pdfplumber page index 3
(pages are 1033-1040 across an 8-page PDF, so index = printed_page - 1033).

LAYOUT ASSUMPTION
------------------
pdfplumber.extract_tables() on that page returns Table 1 as the FIRST table
on the page (there are 3 tables on p.1036: Table 1, Table 2, Table 3). Within
Table 1, the "CTQ-SF scores" block is a single ROW whose first cell is a
newline-joined block of 7 labels ("CTQ-SF scores\\nEmotional abuse\\n...\\n
MD score") and whose baseline/follow-up cells are newline-joined "mean ± SD"
strings in the SAME order. We split all three columns on "\\n" and zip them,
then drop the header line ("CTQ-SF scores").

SAMPLE
------
Single group: schizophrenia patients, same n=35 individuals at two
timepoints (baseline, follow-up). No healthy-control group in this paper.
Per the confirmed mapping, timepoint is stored in `subsample`
("baseline" / "follow_up"); sample_type is "patients" throughout.

SCALE / SUBSCALE (confirmed)
-----------------------------
scale       = "CTQ_SF" for every row.
scale_old   = "CTQ_SF_" + the label as printed in the paper (e.g.
              "CTQ_SF_Emotional abuse", "CTQ_SF_Total", "CTQ_SF_MD score").
subscale    = EA / PA / SA / EN / PN / MD ; "none" for the Total row.
record_type = "total" for the Total row, "subscale" for the other six.

Only mean and SD are extracted (data_type "mean" / "sd") -- no median is
reported in Table 1. No individual items were requested/available.
scoring_rule is left at the make_row() default ("unverified"): the paper
does not state an explicit scoring rule for these summary scores.
redundant_aggregate is False throughout: baseline/follow-up are two
different measurement occasions of the same people, not a whole-sample
value overlapping its own subsamples.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

import scaffold

# Printed page 1036 holds Table 1; the PDF's own running page numbers are
# 1033-1040 across 8 pages, so printed_page - 1033 gives the 0-based index.
TABLE1_PRINTED_PAGE = 1036
FIRST_PRINTED_PAGE = 1033

# Order + normalized-name mapping, exactly as confirmed.
SUBSCALE_MAP = {
    "Emotional abuse": "EA",
    "Physical abuse": "PA",
    "Sexual abuse": "SA",
    "Emotional neglect": "EN",
    "Physical neglect": "PN",
    "Total": None,        # total score -> subscale "none", record_type "total"
    "MD score": "MD",
}

PUBLICATION = "Xiang et al. 2021"
SAMPLE_SIZE = 35  # n who completed both baseline and follow-up (Table 1 header)


def _find_table1(pdf_path):
    """Locate and return Table 1's raw rows from the PDF.

    Returns the CTQ-SF block as three parallel lists (labels, baseline cells,
    follow-up cells), still packed as "mean ± SD" strings.
    """
    page_index = TABLE1_PRINTED_PAGE - FIRST_PRINTED_PAGE
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_index]
        tables = page.extract_tables()

    if not tables:
        raise ValueError(f"no tables found on printed page {TABLE1_PRINTED_PAGE}")

    table1 = tables[0]  # Table 1 is the first table on this page

    # Find the row whose first cell starts the "CTQ-SF scores" block.
    ctq_row = None
    for row in table1:
        first_cell = (row[0] or "")
        if first_cell.startswith("CTQ-SF scores"):
            ctq_row = row
            break
    if ctq_row is None:
        raise ValueError("could not find the 'CTQ-SF scores' row in Table 1")

    label_lines = ctq_row[0].split("\n")
    baseline_lines = ctq_row[1].split("\n")
    followup_lines = ctq_row[2].split("\n")

    # Drop the "CTQ-SF scores" header line from the labels; baseline/followup
    # columns have no such header line (they start straight with values).
    assert label_lines[0] == "CTQ-SF scores"
    labels = label_lines[1:]

    if not (len(labels) == len(baseline_lines) == len(followup_lines)):
        raise ValueError(
            "row-count mismatch while parsing the CTQ-SF block: "
            f"{len(labels)} labels vs {len(baseline_lines)} baseline vs "
            f"{len(followup_lines)} follow-up values"
        )

    return labels, baseline_lines, followup_lines


def _build_views(labels, baseline_lines, followup_lines):
    """Build the RAW (packed) and PARSED (mean/sd split) verification frames."""
    raw_df = pd.DataFrame({
        "CTQ-SF label (as in Table 1)": labels,
        "At Baseline (n=35), Mean \u00b1 SD": baseline_lines,
        "At Follow-Up (n=35), Mean \u00b1 SD": followup_lines,
    })

    parsed_records = []
    for label, base_packed, fu_packed in zip(labels, baseline_lines, followup_lines):
        base_mean, base_sd = _split_pm(base_packed)
        fu_mean, fu_sd = _split_pm(fu_packed)
        subscale = SUBSCALE_MAP[label]
        record_type = "total" if label == "Total" else "subscale"
        for timepoint, mean_val, sd_val in [
            ("baseline", base_mean, base_sd),
            ("follow_up", fu_mean, fu_sd),
        ]:
            parsed_records.append({
                "scale_old": f"CTQ_SF_{label}",
                "subscale": subscale if subscale else "none",
                "record_type": record_type,
                "subsample": timepoint,
                "sample_type": "patients",
                "sample_size": SAMPLE_SIZE,
                "mean": mean_val,
                "sd": sd_val,
            })
    parsed_df = pd.DataFrame(parsed_records)
    return raw_df, parsed_df


def _split_pm(packed):
    """Split a 'mean \u00b1 sd' string (Table 1's own separator) into two floats.

    Table 1 uses '\u00b1' rather than the '(sd)' packing scaffold.split_paren()
    expects, so we parse it directly here instead of forcing it through that
    helper.
    """
    match = re.match(r"^\s*([-\d.]+)\s*\u00b1\s*([-\d.]+)\s*$", packed)
    if not match:
        raise ValueError(f"cannot parse 'mean \u00b1 sd' from {packed!r}")
    return float(match.group(1)), float(match.group(2))


def _build_rows(parsed_df):
    """Turn the parsed frame into schema rows via scaffold.make_row()."""
    rows = []
    for _, r in parsed_df.iterrows():
        for data_type, value in [("mean", r["mean"]), ("sd", r["sd"])]:
            rows.append(scaffold.make_row(
                publication=PUBLICATION,
                scale_old=r["scale_old"],
                data_type=data_type,
                sample_type=r["sample_type"],
                value=value,
                scale="CTQ_SF",
                record_type=r["record_type"],
                subsample=r["subsample"],
                sample_size=r["sample_size"],
                subscale=r["subscale"],
                # item_name, redcap_item_number, scoring_rule,
                # item_score_reversed, redundant_aggregate all left at
                # make_row()'s defaults: "none" / "none" / "unverified" /
                # "none" / False -- no items in this paper, no stated
                # scoring rule, no redundant whole-sample overlap.
            ))
    return rows


def extract(pdf_path):
    """Extract Table 1's CTQ-SF mean/SD rows for this paper.

    Returns (raw_df, parsed_df, rows, hardcoded_flag).
    """
    pdf_path = Path(pdf_path)
    labels, baseline_lines, followup_lines = _find_table1(pdf_path)
    raw_df, parsed_df = _build_views(labels, baseline_lines, followup_lines)
    rows = _build_rows(parsed_df)
    hardcoded_flag = False  # values parsed directly from the PDF table
    return raw_df, parsed_df, rows, hardcoded_flag
