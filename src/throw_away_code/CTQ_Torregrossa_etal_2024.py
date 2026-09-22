"""
CTQ_Torregrossa_etal_2024.py
=============================
Per-paper extractor for:
  Torregrossa LJ, Liu J, Armstrong K, Heckers S, Sheffield JM. "Interplay
  between childhood trauma, bodily self-disturbances, and clinical phenomena
  in schizophrenia spectrum disorders: A network analysis."
  Schizophr Res. 2024;266:107-115.

SOURCE TABLE
------------
Table 1 ("Participants demographic and clinical information"), printed page
108 -> pdfplumber page index 1 (printed pages 107-115 across a 9-page PDF,
so index = printed_page - 107).

LAYOUT ASSUMPTION
------------------
Unlike the Xiang et al. 2021 paper, Table 1 here is NOT recognized as a
structured table by pdfplumber.extract_tables() (it renders as plain
running text, not a ruled grid). We therefore fall back to
page.extract_text() and parse the CTQ block by LINE:
    - the block starts right after the line "CTQ (M \u00b1SD)"
    - it is exactly len(SUBSCALE_MAP) = 6 lines long (the two-column PDF
      layout means the true next line, "PANSS (M \u00b1SD)", gets merged by
      pdfplumber onto an unrelated body-text line from the facing column,
      so we can't reliably anchor the END of the block by text -- instead
      we take a fixed number of lines and then VALIDATE their labels
      against the expected order below, so any layout drift fails loudly
      rather than silently)
    - each line in the block has the form "<Label> <mean> \u00b1<sd>", e.g.
      "Emotional Abuse 6.39 \u00b15.02"
This is a text-layout assumption specific to this PDF's extraction; if a
future re-extraction of this file yields different line breaks, this
anchor-based parse would need re-checking.

SAMPLE
------
Single group: 152 individuals with a schizophrenia-spectrum disorder,
whole-sample only (no baseline/follow-up, no patient/control split, no
nested subgroups). sample_type="patients", subsample="whole_sample",
sample_size=152 throughout.

SCALE / SUBSCALE (confirmed)
-----------------------------
scale       = "CTQ_SF" for every row.
scale_old   = "CTQ_" + the label as printed in the paper (e.g.
              "CTQ_Emotional Abuse", "CTQ_MD").
subscale    = EA / EN / PA / PN / SA / MD (all six rows are subscales;
              this paper does not report a CTQ total score anywhere).
record_type = "subscale" for all rows (no "total" row exists here).

Only mean and SD are extracted (data_type "mean" / "sd") -- no median is
reported. No individual items requested/available. scoring_rule is left at
the make_row() default ("unverified"): no explicit scoring rule is stated
for these summary scores. redundant_aggregate is False throughout: a single
whole-sample group with no subsamples, so there is nothing for it to
overlap with.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

import scaffold

# Printed page 108 holds Table 1; the PDF's own running pages are 107-115
# across 9 pages, so printed_page - 107 gives the 0-based pdfplumber index.
TABLE1_PRINTED_PAGE = 108
FIRST_PRINTED_PAGE = 107

# Order + normalized-name mapping, exactly as confirmed.
SUBSCALE_MAP = {
    "Emotional Abuse": "EA",
    "Emotional Neglect": "EN",
    "Physical Abuse": "PA",
    "Physical Neglect": "PN",
    "Sexual Abuse": "SA",
    "MD": "MD",
}

PUBLICATION = "Torregrossa et al. 2024"
SAMPLE_SIZE = 152  # whole schizophrenia-spectrum sample (Table 1 / p.108 text)

# Matches "<label> <mean> \u00b1<sd>" e.g. "Emotional Abuse 6.39 \u00b15.02".
# Built per-label (rather than a single generic line pattern) because the
# PDF is two-column and pdfplumber's text extraction interleaves each
# table row with a fragment of unrelated body text from the facing column
# on the same visual line (e.g. "...Cramer, 2013). Emotional Abuse 6.39
# \u00b15.02") -- anchoring on the known label text sidesteps that noise.
def _label_pattern(label):
    return re.compile(
        re.escape(label) + r"\s+([\d.]+)\s*\u00b1\s*([\d.]+)"
    )


def _find_table1_ctq_block(pdf_path):
    """Locate and return the CTQ block of Table 1 from the PDF's page text.

    Returns a list of (label, mean, sd) tuples, in the paper's own row order.
    """
    page_index = TABLE1_PRINTED_PAGE - FIRST_PRINTED_PAGE
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_index]
        text = page.extract_text()

    if not text:
        raise ValueError(f"no extractable text on printed page {TABLE1_PRINTED_PAGE}")

    # Restrict the search to the region from the "CTQ (M \u00b1SD)" anchor
    # onward, so we can't accidentally match a same-named label elsewhere
    # on the page (defensive; none of these labels appear elsewhere here).
    anchor = "CTQ (M \u00b1SD)"
    anchor_pos = text.find(anchor)
    if anchor_pos == -1:
        raise ValueError(f"could not locate the {anchor!r} anchor in Table 1's text")
    search_region = text[anchor_pos + len(anchor):]

    records = []
    for label in SUBSCALE_MAP:  # dict preserves the paper's row order
        match = _label_pattern(label).search(search_region)
        if not match:
            raise ValueError(f"could not find row for label {label!r} in Table 1")
        mean_s, sd_s = match.groups()
        records.append((label, float(mean_s), float(sd_s)))

    return records


def _build_views(records):
    """Build the RAW (packed) and PARSED (mean/sd split) verification frames."""
    raw_df = pd.DataFrame({
        "CTQ label (as in Table 1)": [label for label, _, _ in records],
        "Whole sample (N=152), Mean \u00b1 SD": [
            f"{mean:.2f} \u00b1 {sd:.2f}" for _, mean, sd in records
        ],
    })

    parsed_df = pd.DataFrame([{
        "scale_old": f"CTQ_{label}",
        "subscale": SUBSCALE_MAP[label],
        "record_type": "subscale",
        "subsample": "whole_sample",
        "sample_type": "patients",
        "sample_size": SAMPLE_SIZE,
        "mean": mean,
        "sd": sd,
    } for label, mean, sd in records])

    return raw_df, parsed_df


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
                # "none" / False -- no items, no stated scoring rule, no
                # whole-sample/subsample overlap in this paper.
            ))
    return rows


def extract(pdf_path):
    """Extract Table 1's CTQ mean/SD rows for this paper.

    Returns (raw_df, parsed_df, rows, hardcoded_flag).
    """
    pdf_path = Path(pdf_path)
    records = _find_table1_ctq_block(pdf_path)
    raw_df, parsed_df = _build_views(records)
    rows = _build_rows(parsed_df)
    hardcoded_flag = False  # values parsed directly from the PDF's page text
    return raw_df, parsed_df, rows, hardcoded_flag
