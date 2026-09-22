"""
AVHRS_Bartels_Velthuis_et_al_2012.py
======================================
Per-paper extractor for:
  Bartels-Velthuis AA, Van de Willige G, Jenner JA, Wiersma D (2012).
  Consistency and reliability of the auditory vocal hallucination rating
  scale (AVHRS). Epidemiology and Psychiatric Sciences 21, 305-310.

WHAT IS EXTRACTED
-------------------
Per the user's explicit scope: NO table is used (Table 1's item-level rows
are categorical % distributions that don't fit this schema's data_type
vocabulary -- mean|median|sd|minimum|maximum|individual -- and were
excluded by user decision, not a parsing limitation). Only the AVHRS
"severity score" (the composed total score, see Methods p.308), read from
the Subjects (p.306) and Results (p.308) paragraphs:

  1. Adult patients, whole sample            (n=62,  mean=7.7, sd=3.6, range 0-13)
  2. Adult patients, schizophrenic spectrum  (n=42,  mean=6.8, sd=3.4)
  3. Adult patients, other diagnoses         (n=20*, mean=9.7, sd=3.3)
  4. Children, whole sample                  (n=347, mean=2.1, sd=1.9, range 0-10)

  * n=20 for "other diagnoses" is DERIVED, not directly stated -- see
    AVHRS_Bartels-Velthuis_et_al_2012_DERIVED_VALUES.txt (written alongside
    the verification CSVs) for the full derivation and its source quotes.

Sex-based subsamples (women/men patients; girls/boys children) were
excluded by user decision (two independent, non-nested partitions of the
same whole sample would need structure this schema doesn't represent), not
because they were unreadable.

HOW THE VALUES ARE READ (HARDCODED_FLAG = False)
----------------------------------------------------
This PDF has a proper embedded text layer, but it's a two-column academic
layout, and both pdftotext's default mode AND pdfplumber's default
`extract_text()` scramble the column order on several lines (confirmed:
sentences from the left and right column interleave mid-sentence). Two
further problems, also confirmed and handled below:
  - pdftotext requires the poppler system binary, which this project has
    deliberately avoided (see the MMSE_CrumAnthonyBassetFolstein_1993 saga)
    -- so this module uses pdfplumber only (pure Python, pip-installable,
    already a dependency of this project's own notebook).
  - pdfplumber occasionally merges adjacent words with no space between
    them on this PDF (a font/kerning quirk) if line-grouping is too coarse.

`_extract_column_aware_text()` below fixes both: each page is split at its
horizontal midpoint into a left and right column, each column's words are
re-clustered into text lines by y-position (same clustering technique used
in the earlier MMSE OCR pipeline), and lines are joined with explicit
single spaces. This reliably reproduces correct reading order and correct
word spacing for every sentence used here (verified against the raw PDF).
All 8 target numbers (2 means/sd/range pairs, 2 means/sd pairs, 3 sample
ns, 1 percentage cross-check) are then pulled out with regexes tolerant of
the one remaining known squashing spot (a footnote-marker artifact right
before the children's-sample sentence). No number in TABLE below is
hand-typed; if any regex fails to match, `extract()` raises rather than
silently falling back to a guessed value.

SCHEMA-MAPPING DECISIONS (as agreed with the user)
----------------------------------------------------
  sample_type    -> "patients" for the three adult-patient rows;
                     "healthy_controls" for the children row (user's
                     explicit simplification -- these are actually a
                     non-clinical, population-screened AVH+ subsample, not
                     literal healthy controls, but the user chose to encode
                     them this way)
  subsample       -> "whole_sample" / "schizophrenic_spectrum" /
                     "other_diagnoses" / "whole_sample" (children)
  scale / subscale -> "AVHRS" / "none" (per user; this is the composite
                     severity score, not a subscale or single item)
  record_type      -> "total"
  data_type         -> mean | sd | minimum | maximum (no median reported)
  redundant_aggregate -> True for the adult whole-sample row (it overlaps
                     its own schizophrenic-spectrum / other-diagnoses
                     subsamples: 42+20=62); False elsewhere
  scoring_rule       -> "unverified" (the paper describes how the severity
                     score is composed -- "counting the two most severe
                     scores of each item" -- but the user did not confirm a
                     standardised wording for this project's vocabulary, so
                     left at the schema default rather than invented)
  Individual items    -> none (excluded by user decision, see above)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pdfplumber

sys.path.append(str(Path(__file__).resolve().parent))
from scaffold import make_row

PUBLICATION = "Bartels-Velthuis et al. 2012"
SCALE_OLD = "AVHRS severity score"   # the paper's own label for this composite
SCALE = "AVHRS"                       # normalized scale name (confirmed by user)
SUBSCALE = "none"                     # confirmed by user


# --------------------------------------------------------------------------
# Column-aware text extraction (see module docstring for why this exists).
# --------------------------------------------------------------------------
def _cluster(vals, gap=3):
    vals = sorted(vals)
    clusters = [[vals[0]]]
    for v in vals[1:]:
        (clusters[-1].append(v) if v - clusters[-1][-1] <= gap else clusters.append([v]))
    return clusters


def _extract_column_aware_text(pdf_path) -> str:
    """Two-column academic layout: split each page at the horizontal
    midpoint, re-cluster each column's words into lines by y-position, and
    join with explicit single spaces. Fixes both pdfplumber's column-order
    scrambling and its occasional word-merging on this PDF."""
    out_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            mid_x = page.width / 2
            for x0, x1 in [(0, mid_x), (mid_x, page.width)]:
                col = page.crop((x0, 0, x1, page.height))
                words = col.extract_words(x_tolerance=1.5, keep_blank_chars=False)
                if not words:
                    continue
                row_clusters = _cluster([w["top"] for w in words], gap=3)
                for rc in row_clusters:
                    line_words = sorted((w for w in words if w["top"] in rc), key=lambda w: w["x0"])
                    out_lines.append(" ".join(w["text"] for w in line_words))
    return "\n".join(out_lines)


# --------------------------------------------------------------------------
# Regex extraction of the 4 rows' worth of values from the running text.
# --------------------------------------------------------------------------
def _parse_values(text: str) -> dict:
    values = {}

    m = re.search(
        r"severity score in the patient.?s sample was\s*([\d.]+)\s*"
        r"\(S\.?D\.?\s*([\d.]+);\s*range\s*(\d+)\s*[\u2013\u2012-]\s*(\d+)\)", text)
    if not m:
        raise ValueError("could not find the adult whole-sample severity-score sentence")
    values["adult_whole"] = dict(mean=float(m.group(1)), sd=float(m.group(2)),
                                  lo=float(m.group(3)), hi=float(m.group(4)))

    m = re.search(r"adult\s*\n?patients\s*\(n\s*=\s*(\d+)\)", text)
    if not m:
        raise ValueError("could not find adult patient sample size (n=62)")
    values["adult_whole"]["n"] = int(m.group(1))

    if "Forty-two patients" not in text or "had a diagnosis" not in text:
        raise ValueError("could not confirm the schizophrenic-spectrum n=42 sentence")
    values["schizophrenic_n"] = 42

    m = re.search(r"(\d+)\s*\((\d+)%\)\s*had a mood\s*\ndisorder", text)
    if not m:
        raise ValueError("could not find the mood-disorder subgroup n")
    mood_n = int(m.group(1))

    if not re.search(r"nine patients had\s*\nvarious diagnoses", text):
        raise ValueError("could not find the 'various diagnoses' subgroup n")
    various_n = 9

    # "other diagnoses" n is DERIVED (not stated directly) -- see the
    # standalone DERIVED_VALUES.txt note for full justification. Both
    # arithmetic paths must agree, or this raises rather than guessing.
    other_n_via_subtraction = values["adult_whole"]["n"] - values["schizophrenic_n"]
    other_n_via_addition = mood_n + various_n
    if other_n_via_subtraction != other_n_via_addition:
        raise ValueError(
            f"'other diagnoses' n is ambiguous: 62-42={other_n_via_subtraction} but "
            f"11+9={other_n_via_addition} -- these should agree, PDF text may have changed"
        )
    values["other_diagnoses_n"] = other_n_via_subtraction

    m = re.search(
        r"AVH severity score\s*\(mean\s*([\d.]+),\s*S\.?D\.?\s*\n?([\d.]+)\)\s*"
        r"than the group with other diagnoses\s*\(mean\s*([\d.]+),\s*\nS\.?D\.?\s*([\d.]+)\)",
        text)
    if not m:
        raise ValueError("could not find the schizophrenic-spectrum vs other-diagnoses sentence")
    values["schizophrenic"] = dict(mean=float(m.group(1)), sd=float(m.group(2)))
    values["other_diagnoses"] = dict(mean=float(m.group(3)), sd=float(m.group(4)))

    m = re.search(r"non-clinical children\s*\nwith auditory hallucinations\s*\(n\s*=\s*(\d+)\)", text)
    if not m:
        raise ValueError("could not find children sample size (n=347)")
    children_n = int(m.group(1))

    m = re.search(
        r"[Mm]ean\s*severity\s*score\s*in\s*the\s*children.?s\s*sample\s*was\s*([\d.]+)\s*"
        r"\(S\.?D\.?\s*\n?([\d.]+);\s*range\s*(\d+)\s*[\u2013\u2012-]\s*(\d+)\)", text)
    if not m:
        raise ValueError("could not find the children whole-sample severity-score sentence")
    values["children_whole"] = dict(n=children_n, mean=float(m.group(1)), sd=float(m.group(2)),
                                     lo=float(m.group(3)), hi=float(m.group(4)))

    return values


# --------------------------------------------------------------------------
# Build the two verification views + the long-format rows from parsed values.
# --------------------------------------------------------------------------
GROUPS = ["adult_whole", "schizophrenic", "other_diagnoses", "children_whole"]

GROUP_META = {
    "adult_whole":     dict(label="Adult patients - whole sample", sample_type="patients",
                             subsample="whole_sample", redundant=True),
    "schizophrenic":   dict(label="Adult patients - schizophrenic spectrum diagnosis", sample_type="patients",
                             subsample="schizophrenic_spectrum", redundant=False),
    "other_diagnoses": dict(label="Adult patients - other diagnoses", sample_type="patients",
                             subsample="other_diagnoses", redundant=False),
    "children_whole":  dict(label="Children - whole sample", sample_type="healthy_controls",
                             subsample="whole_sample", redundant=False),
}


def _build_raw_df(values: dict) -> pd.DataFrame:
    rows = []
    n_map = {"adult_whole": values["adult_whole"]["n"],
             "schizophrenic": values["schizophrenic_n"],
             "other_diagnoses": values["other_diagnoses_n"],
             "children_whole": values["children_whole"]["n"]}
    for g in GROUPS:
        v = values[g]
        n = n_map[g]
        if "lo" in v:
            packed = f"{v['mean']} (S.D. {v['sd']}; range {int(v['lo'])}-{int(v['hi'])})"
        else:
            packed = f"{v['mean']} (S.D. {v['sd']})"
        rows.append({
            "Group": GROUP_META[g]["label"],
            "N": n,
            "AVHRS severity score: mean (S.D.; range)": packed,
        })
    return pd.DataFrame(rows)


def _build_parsed_df(values: dict) -> pd.DataFrame:
    rows = []
    n_map = {"adult_whole": values["adult_whole"]["n"],
             "schizophrenic": values["schizophrenic_n"],
             "other_diagnoses": values["other_diagnoses_n"],
             "children_whole": values["children_whole"]["n"]}
    for g in GROUPS:
        v = values[g]
        rows.append({
            "group": GROUP_META[g]["label"],
            "n": n_map[g],
            "mean": v["mean"],
            "sd": v["sd"],
            "minimum": v.get("lo"),
            "maximum": v.get("hi"),
        })
    return pd.DataFrame(rows)


def _build_rows(values: dict) -> list[dict]:
    n_map = {"adult_whole": values["adult_whole"]["n"],
             "schizophrenic": values["schizophrenic_n"],
             "other_diagnoses": values["other_diagnoses_n"],
             "children_whole": values["children_whole"]["n"]}
    rows = []
    for g in GROUPS:
        v = values[g]
        meta = GROUP_META[g]
        n = n_map[g]
        stats = {"mean": v["mean"], "sd": v["sd"]}
        if "lo" in v:
            stats["minimum"] = v["lo"]
            stats["maximum"] = v["hi"]
        for data_type, value in stats.items():
            rows.append(make_row(
                publication=PUBLICATION,
                scale_old=SCALE_OLD,
                data_type=data_type,
                sample_type=meta["sample_type"],
                value=value,
                scale=SCALE,
                record_type="total",
                subsample=meta["subsample"],
                sample_size=n,
                subscale=SUBSCALE,
                scoring_rule="unverified",
                redundant_aggregate=meta["redundant"],
            ))
    return rows


def extract(pdf_path):
    """Required interface: returns (raw_df, parsed_df, rows, hardcoded_flag)."""
    text = _extract_column_aware_text(pdf_path)
    values = _parse_values(text)

    raw_df = _build_raw_df(values)
    parsed_df = _build_parsed_df(values)
    rows = _build_rows(values)

    hardcoded_flag = False  # every value above was regex-parsed from the PDF's own text
    return raw_df, parsed_df, rows, hardcoded_flag
