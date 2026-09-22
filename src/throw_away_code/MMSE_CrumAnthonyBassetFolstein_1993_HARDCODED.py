"""
MMSE_CrumAnthonyBassetFolstein_1993_HARDCODED.py
==================================================
Per-paper extractor for:
  Crum RM, Anthony JC, Bassett SS, Folstein MF (1993). Population-Based Norms
  for the Mini-Mental State Examination by Age and Educational Level.
  JAMA. 269(18):2386-2391.

Fully hand-transcribed version (no OCR, no pytesseract, no poppler/pdftoppm --
no dependencies beyond pandas and this project's own scaffold.py). Every
value in TABLE below was read visually off a 300dpi render of page 4 of the
PDF and cross-checked (every age column's n across the 4 named education
levels sums exactly to the paper's own "Total" n, including the grand total
of 18 056). The user independently re-verified the raw and parsed views
against the PDF before this module was written.

Because every number was hand-typed (even though visually verified and
internally cross-checked) rather than parsed programmatically from the PDF,
`extract()` sets hardcoded_flag = True, per project rule 2.

TABLE EXTRACTED
----------------
The paper's single table (p. 2389): "Mini-Mental State Examination Score by
Age and Educational Level, Number of Participants, Mean, SD, and Selected
Percentiles". A 2-way cross-tab: 5 educational-level rows (incl. a "Total"
row) x 15 age columns (14 bands + a "Total" column) = 75 cells, each with
n, mean, SD, lower quartile (25th pctl), median, upper quartile (75th pctl).

DATA_TYPE MAPPING NOTE (revised per user decision)
------------------------------------------------------
The scaffold's ALLOWED_DATA_TYPES is {"mean","median","sd","minimum",
"maximum","individual"} -- it does NOT include "lower_quartile"/
"upper_quartile" (an earlier local scaffold edit adding those two was
reversed by the user). Since the paper reports the 25th/75th percentile,
not the literal sample min/max, this module maps:
    lower quartile (25th pctl)  -> data_type = "minimum"
    upper quartile (75th pctl)  -> data_type = "maximum"
This is an approximation of convenience to fit the existing vocabulary, not
a claim that these are the true sample minimum/maximum -- worth keeping in
mind if these rows are relabeled or reinterpreted downstream.

SCHEMA-MAPPING DECISIONS (as agreed with the user)
----------------------------------------------------
  sample_type          -> "healthy_controls" for every row (user's project
                           convention: community samples are counted as
                           healthy_controls)
  subsample              -> "age_{age_band}_x_edu_{edu_level}" (single-column
                           encoding of the 2-way age x education design)
  scale / subscale        -> "MMSE" / "none"
  record_type             -> "total" (only the MMSE total score is tabulated;
                           no subscales/items have descriptive stats in this
                           paper)
  scoring_rule             -> "raw_sum" (paper states explicitly, p. 2388:
                           score = sum of correct responses to MMSE items,
                           range 0-30; user confirmed wording)
  redundant_aggregate      -> True whenever age_band == "Total" or
                           edu_level == "Total" (these are marginal
                           aggregates that overlap their own finer
                           subsamples); False otherwise
  Individual items         -> none extracted (none exist in this paper: Fig 1
                           is the blank instrument, not scored item data)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
from scaffold import make_row

PUBLICATION = "Crum et al. 1993"
SCALE_OLD = "MMSE"          # label as used throughout the paper's own text
SCALE = "MMSE"               # normalized scale name (confirmed by user)
SUBSCALE = "none"            # confirmed by user

AGE_COLS = ["18-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54",
            "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", ">=85",
            "Total"]

# education level -> subsample slug
EDU_LEVELS = {
    "0 to 4 y":                              "0-4y",
    "5 to 8 y":                              "5-8y",
    "9 to 12 y or high school diploma":      "9-12y_or_hsdiploma",
    "College experience or higher degree":   "college_or_higher",
    "Total":                                 "Total",
}

# --------------------------------------------------------------------------
# Hand-transcribed table values (see module docstring for provenance/checks).
# Each dict: n, mean, sd, lower quartile (lq), median, upper quartile (uq),
# one value per AGE_COLS entry (14 age bands + Total), in that order.
# --------------------------------------------------------------------------
TABLE = {
    "0 to 4 y": dict(
        n=[17, 23, 41, 33, 36, 28, 34, 49, 88, 126, 139, 112, 105, 61, 892],
        mean=[22, 25, 25, 23, 23, 23, 23, 22, 23, 22, 22, 21, 20, 19, 22],
        sd=[2.9, 2.0, 2.4, 2.5, 2.6, 3.7, 2.6, 2.7, 1.9, 1.9, 1.7, 2.0, 2.2, 2.9, 2.3],
        lq=[21, 23, 23, 20, 20, 20, 20, 20, 19, 19, 19, 18, 16, 15, 19],
        median=[23, 25, 26, 24, 23, 23, 22, 22, 22, 22, 21, 21, 19, 20, 22],
        uq=[25, 27, 28, 27, 27, 26, 25, 26, 26, 25, 24, 24, 23, 23, 25],
    ),
    "5 to 8 y": dict(
        n=[94, 83, 74, 101, 100, 121, 154, 208, 310, 633, 533, 437, 241, 134, 3223],
        mean=[27, 27, 26, 26, 27, 26, 27, 26, 26, 26, 26, 25, 25, 23, 26],
        sd=[2.7, 2.5, 1.8, 2.8, 1.8, 2.5, 2.4, 2.9, 2.3, 1.7, 1.8, 2.1, 1.9, 3.3, 2.2],
        lq=[24, 25, 24, 23, 25, 24, 25, 25, 24, 24, 24, 22, 22, 21, 23],
        median=[28, 27, 26, 27, 27, 27, 27, 27, 27, 27, 26, 26, 25, 24, 26],
        uq=[29, 29, 28, 29, 29, 29, 29, 29, 29, 29, 28, 28, 27, 27, 28],
    ),
    "9 to 12 y or high school diploma": dict(
        n=[1326, 958, 822, 668, 489, 423, 462, 525, 626, 814, 550, 315, 163, 99, 8240],
        mean=[29, 29, 29, 28, 28, 28, 28, 28, 28, 28, 27, 27, 25, 26, 28],
        sd=[2.2, 1.3, 1.3, 1.8, 1.9, 2.4, 2.2, 2.2, 1.7, 1.4, 1.6, 1.5, 2.3, 2.0, 1.9],
        lq=[28, 28, 28, 28, 28, 27, 27, 27, 27, 27, 26, 25, 23, 23, 27],
        median=[29, 29, 29, 29, 29, 29, 29, 29, 28, 28, 28, 27, 26, 26, 29],
        uq=[30, 30, 30, 30, 30, 30, 30, 30, 30, 29, 29, 29, 28, 28, 30],
    ),
    "College experience or higher degree": dict(
        n=[783, 1012, 989, 641, 354, 259, 220, 231, 270, 358, 255, 181, 96, 52, 5701],
        mean=[29, 29, 29, 29, 29, 29, 29, 29, 29, 29, 28, 28, 27, 27, 29],
        sd=[1.3, 0.9, 1.0, 1.0, 1.7, 1.6, 1.9, 1.5, 1.3, 1.0, 1.6, 1.6, 0.9, 1.3, 1.3],
        lq=[29, 29, 29, 29, 29, 29, 28, 28, 28, 28, 27, 27, 26, 25, 29],
        median=[30, 30, 30, 30, 30, 30, 30, 29, 29, 29, 29, 28, 28, 28, 29],
        uq=[30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 29, 29, 29, 29, 30],
    ),
    "Total": dict(
        n=[2220, 2076, 1926, 1443, 979, 831, 870, 1013, 1294, 1931, 1477, 1045, 605, 346, 18056],
        mean=[29, 29, 29, 29, 28, 28, 28, 28, 28, 27, 27, 26, 25, 24, 28],
        sd=[2.0, 1.3, 1.3, 1.8, 2.0, 2.5, 2.4, 2.5, 2.0, 1.6, 1.8, 2.1, 2.2, 2.9, 2.0],
        lq=[28, 28, 28, 28, 27, 27, 27, 26, 26, 26, 24, 23, 21, 21, 27],
        median=[29, 29, 29, 29, 29, 29, 29, 29, 28, 28, 27, 26, 25, 25, 29],
        uq=[30, 30, 30, 30, 30, 30, 30, 30, 29, 29, 29, 28, 28, 28, 30],
    ),
}

# statistic key -> display name for the RAW view
STAT_MAP = [
    ("mean", "Mean"),
    ("sd", "SD"),
    ("lq", "Lower quartile"),
    ("median", "Median"),
    ("uq", "Upper quartile"),
]

# statistic key -> data_type value for the long-format schema
# (lq/uq mapped to minimum/maximum -- see module docstring note)
DATA_TYPE_MAP = {
    "mean": "mean",
    "sd": "sd",
    "lq": "minimum",
    "median": "median",
    "uq": "maximum",
}


def _age_slug(age: str) -> str:
    """'>=85' -> '85plus'; everything else passes through unchanged."""
    return "85plus" if age == ">=85" else age


def _build_raw_df() -> pd.DataFrame:
    """Mirror the published table layout exactly (one row per statistic)."""
    rows = []
    for edu_level, d in TABLE.items():
        row = {"Educational Level": edu_level, "Statistic": "n"}
        row.update({AGE_COLS[i]: d["n"][i] for i in range(len(AGE_COLS))})
        rows.append(row)
        for key, label in STAT_MAP:
            row = {"Educational Level": edu_level, "Statistic": label}
            row.update({AGE_COLS[i]: d[key][i] for i in range(len(AGE_COLS))})
            rows.append(row)
    return pd.DataFrame(rows)


def _build_parsed_df() -> pd.DataFrame:
    """Long, one row per (education level x age band) cell."""
    rows = []
    for edu_level, d in TABLE.items():
        for i, age in enumerate(AGE_COLS):
            rows.append({
                "education_level": edu_level,
                "age_group": age,
                "n": d["n"][i],
                "mean": d["mean"][i],
                "sd": d["sd"][i],
                "lower_quartile": d["lq"][i],
                "median": d["median"][i],
                "upper_quartile": d["uq"][i],
            })
    return pd.DataFrame(rows)


def _build_rows() -> list[dict]:
    """One make_row() call per (cell x statistic) = 75 cells x 5 stats = 375 rows."""
    rows = []
    for edu_level, edu_slug in EDU_LEVELS.items():
        d = TABLE[edu_level]
        for i, age in enumerate(AGE_COLS):
            n = d["n"][i]
            subsample = f"age_{_age_slug(age)}_x_edu_{edu_slug}"
            is_marginal = (age == "Total") or (edu_level == "Total")
            for key, _ in STAT_MAP:
                rows.append(make_row(
                    publication=PUBLICATION,
                    scale_old=SCALE_OLD,
                    data_type=DATA_TYPE_MAP[key],
                    sample_type="healthy_controls",
                    value=d[key][i],
                    scale=SCALE,
                    record_type="total",
                    subsample=subsample,
                    sample_size=n,
                    subscale=SUBSCALE,
                    scoring_rule="raw_sum",
                    redundant_aggregate=is_marginal,
                ))
    return rows


def extract(pdf_path):
    """Required interface: returns (raw_df, parsed_df, rows, hardcoded_flag)."""
    raw_df = _build_raw_df()
    parsed_df = _build_parsed_df()
    rows = _build_rows()
    hardcoded_flag = True  # see module docstring: every value is hand-transcribed
    return raw_df, parsed_df, rows, hardcoded_flag
