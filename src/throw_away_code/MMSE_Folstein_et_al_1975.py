"""
MMSE_Folstein_et_al_1975.py
=============================
Per-paper extractor for:
  Folstein MF, Folstein SE, McHugh PR (1975). "Mini-Mental State": A practical
  method for grading the cognitive state of patients for the clinician.
  J. Psychiat. Res. 12:189-198.

TABLE EXTRACTED
----------------
Table 1, Part A only ("Mini Mental State Scores on Admission", p.191):
4 rows -- 3 patient diagnostic groups (Dementia; Depression with cognitive
impairment; Affective Dis., Depressed -- together "the 69 patients" per the
text) plus 1 healthy-control group (Normal, n=63). Each row reports N, Age,
Sex M/F, MMS mean, MMS SD, and MMS Range (packed "lo-hi", split here into
minimum/maximum). No median is reported in this table. Table 1 also has
Parts B and C (age-matched subsample; pre/post-treatment) -- explicitly out
of scope per the user's PROMPT-1 instructions, not extracted here.

WHY THE VALUES ARE HARDCODED (HARDCODED_FLAG = True)
--------------------------------------------------------
This PDF has NO embedded text layer at all -- confirmed two ways:
  `pdftotext -layout MMSE_Folstein_et_al_1975.pdf -`  returns nothing
  `pdffonts MMSE_Folstein_et_al_1975.pdf`             lists zero fonts
It's a pure page-image scan (1975 journal reprint), so there is no text to
parse programmatically -- not a parsing-quality problem like the 1993 Crum
paper, but a complete absence of any text layer to work with. Per project
rule 2, the 16 values (4 rows x {mean, sd, minimum, maximum}) were instead
read visually off the PDF and cross-checked internally: on every row,
Sex(M) + Sex(F) == N, and the three patient rows' N's sum to 69, matching
the paper's own text ("chosen...(29 with dementia...,10 with...,30 with
uncomplicated affective disorder...) and 63 normal"). The user independently
re-verified the raw/parsed views against the PDF before this module was
written.

SCORING RULE NOTE
------------------
Unlike the Crum et al. 1993 paper (which has one explicit sentence stating
the score is a raw sum), this paper never states its scoring rule in one
clean sentence -- it gives Part I max = 21, Part II max = 9, "Maximum total
score is 30" (p.190), and per-item point values, which together imply a raw
sum but were not confirmed by the user as an explicit quote here. Left as
`scoring_rule="unverified"` (the schema default) rather than silently
reusing "raw_sum" from the other paper.

SCHEMA-MAPPING DECISIONS (as agreed with the user)
----------------------------------------------------
  sample_type    -> "patients" for Dementia / Depression with cognitive
                     impairment / Affective Dis., Depressed;
                     "healthy_controls" for Normal
  subsample       -> the diagnosis label itself (no nested/overlapping
                     structure in this table -- confirmed with the user)
  scale / subscale -> "MMSE" / "none" (per user, consistent with the Crum
                     1993 paper in the same project)
  record_type      -> "total" (single MMS total score per row; no
                     subscale/item breakdown in Table 1A)
  data_type         -> mean | sd | minimum | maximum (no median reported in
                     this table; these four are already in scaffold's base
                     ALLOWED_DATA_TYPES, no vocabulary extension needed)
  redundant_aggregate -> False for all rows (no "Total" row combining the
                     three patient subsamples exists in Table 1A, so no
                     row overlaps another -- confirmed with the user)
  Individual items    -> none extracted (Table 1A has no item-level scores;
                     Appendix is the blank instrument, not scored data)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
from scaffold import make_row

PUBLICATION = "Folstein et al. 1975"
SCALE_OLD = "MMS"           # the paper's own label ("Mini Mental State" / MMS)
SCALE = "MMSE"                # normalized scale name (confirmed by user)
SUBSCALE = "none"             # confirmed by user

# --------------------------------------------------------------------------
# Hand-transcribed Table 1, Part A (see module docstring for provenance).
# --------------------------------------------------------------------------
TABLE_1A = [
    dict(diagnosis="Dementia", sample_type="patients",
         n=29, age=80.8, sex_m=12, sex_f=17, mean=9.6, sd=5.8, lo=0.0, hi=22.0),
    dict(diagnosis="Depression with cognitive impairment", sample_type="patients",
         n=10, age=74.5, sex_m=7, sex_f=3, mean=19.0, sd=6.6, lo=9.0, hi=27.0),
    dict(diagnosis="Affective Dis., Depressed", sample_type="patients",
         n=30, age=49.8, sex_m=9, sex_f=21, mean=25.1, sd=5.4, lo=8.0, hi=30.0),
    dict(diagnosis="Normal", sample_type="healthy_controls",
         n=63, age=73.9, sex_m=27, sex_f=36, mean=27.6, sd=1.7, lo=24.0, hi=30.0),
]

# statistic key -> data_type value for the long-format schema
DATA_TYPE_MAP = {"mean": "mean", "sd": "sd", "lo": "minimum", "hi": "maximum"}


def _build_raw_df() -> pd.DataFrame:
    """Mirror the published table layout exactly (range kept packed)."""
    rows = []
    for r in TABLE_1A:
        rows.append({
            "Diagnosis": r["diagnosis"],
            "N": r["n"],
            "Age": r["age"],
            "Sex M/F": f"{r['sex_m']}/{r['sex_f']}",
            "MMS x\u0304": r["mean"],
            "MMS S.D.": r["sd"],
            "MMS Range": f"{int(r['lo'])}-{int(r['hi'])}",
        })
    return pd.DataFrame(rows)


def _build_parsed_df() -> pd.DataFrame:
    """Long-ish view, one row per diagnosis, range split into minimum/maximum."""
    rows = []
    for r in TABLE_1A:
        rows.append({
            "diagnosis": r["diagnosis"],
            "sample_type": r["sample_type"],
            "n": r["n"],
            "age_mean": r["age"],
            "sex_m": r["sex_m"],
            "sex_f": r["sex_f"],
            "mean": r["mean"],
            "sd": r["sd"],
            "minimum": r["lo"],
            "maximum": r["hi"],
        })
    return pd.DataFrame(rows)


def _build_rows() -> list[dict]:
    """One make_row() call per (diagnosis x statistic) = 4 rows x 4 stats = 16 rows."""
    rows = []
    for r in TABLE_1A:
        for key, data_type in DATA_TYPE_MAP.items():
            rows.append(make_row(
                publication=PUBLICATION,
                scale_old=SCALE_OLD,
                data_type=data_type,
                sample_type=r["sample_type"],
                value=r[key],
                scale=SCALE,
                record_type="total",
                subsample=r["diagnosis"],
                sample_size=r["n"],
                subscale=SUBSCALE,
                scoring_rule="unverified",
                redundant_aggregate=False,
            ))
    return rows


def extract(pdf_path):
    """Required interface: returns (raw_df, parsed_df, rows, hardcoded_flag)."""
    raw_df = _build_raw_df()
    parsed_df = _build_parsed_df()
    rows = _build_rows()
    hardcoded_flag = True  # see module docstring: PDF has no text layer at all
    return raw_df, parsed_df, rows, hardcoded_flag
