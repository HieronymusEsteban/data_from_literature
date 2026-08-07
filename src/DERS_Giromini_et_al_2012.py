"""
Per-paper extractor: Giromini et al. 2012, Italian DERS validation (Study 1).
Scale of interest: the six DERS subscales + the DERS Total scale (mean + SD),
for three groups: Women, Men, Entire Sample.

Returns (raw_df, parsed_df, rows, hardcoded_flag) for scaffold.run_extraction.

SCOPE
-----
This module covers TABLE 1 ONLY (Study 1, the Italian student sample). The
paper also reports a clinical (eating-disorder) vs nonclinical comparison in
Table 6; that is a separate sample with different `sample` labels and a
CI-vs-min/max trap, handled in its own module -- NOT here.

SAMPLE-LABEL CAVEAT
-------------------
Study 1's sample is 323 Italian psychology students, explicitly NON-clinical
(participants in psychiatric treatment / on psychiatric meds were excluded).
They are not patients and not case-control "healthy controls"; just a
community/student sample. The scaffold vocabulary only allows
{patients, healthy_controls}, so every row is tagged `healthy_controls` as the
closest fit, and a note file documents this (see _write_sample_note).

PAPER-SPECIFIC LAYOUT ASSUMPTIONS
---------------------------------
* Table 1 is on the 7th PDF page (0-indexed page 6). pdfplumber extracts it as
  text with NO spaces inside the running header/footer, but the table rows are
  normally spaced.
* The header line (line ~5) is:
      'Scale Mean SD Skew Kurtosis Mean SD Skew Kurtosis Mean SD Skew Kurtosis'
  i.e. each of the 3 groups (Women, Men, Entire Sample) contributes 4 columns
  in fixed order: Mean, SD, Skew, Kurtosis. We keep Mean & SD, drop Skew &
  Kurtosis.
* Each data row is: '<label> m sd skew kurt m sd skew kurt m sd skew kurt'
  -> 1 label token + 12 numeric tokens. Token indices we want (after the label
  is stripped): Mean at 0/4/8, SD at 1/5/9. Skew/Kurtosis (incl. negatives like
  '−.5') sit at indices we ignore, so they never interfere.
* Rows are identified by matching the leading label against the fixed SCALES
  list below; this also fixes row order and stops us at the Note/Table 2 lines.
* Group Ns are fixed in the header: Women 249, Men 74, Entire Sample 323.
* Only Mean and SD are reported (no median).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scaffold import make_row, NA_MARKER

PUBLICATION = "Giromini et al. 2012"
TABLE1_PAGE = 6                       # 0-indexed PDF page holding Table 1
SCALE_PREFIX = "DERS"

# DERS rows in the table's row order (6 subscales + full-scale Total).
SCALES = [
    "Nonacceptance",
    "Goals",
    "Impulse",
    "Awareness",
    "Strategies",
    "Clarity",
    "Total",
]

# Three column-groups, left-to-right, with the numeric index of their Mean
# within the row's numeric tokens (SD is always Mean-index + 1), plus the
# subsample label and N we map each to.
GROUPS = [
    # mean_idx, group_name, subsample, n
    (0, "Women",         "female", 249),
    (4, "Men",           "male",    74),
    (8, "Entire Sample", NA_MARKER, 323),
]


def _table1_lines(pdf_path):
    """Return text lines of the Table-1 page."""
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        return pdf.pages[TABLE1_PAGE].extract_text().split("\n")


def _row_for_scale(lines, scale):
    """Find the data line whose first token is `scale` and return its numeric
    tokens (everything after the label) as a list of strings.

    Note: 'Total' is a unique leading token in this table, and the subscale
    names are single words, so first-token matching is unambiguous."""
    for ln in lines:
        toks = ln.split()
        if toks and toks[0] == scale:
            return toks[1:]
    raise ValueError(f"row for scale {scale!r} not found")


def _to_float(tok):
    """'4.4' -> 4.4 ; handles the unicode minus used for negatives ('−.5')."""
    return float(tok.replace("\u2212", "-"))


def _parse_table1(pdf_path):
    """Return list of dicts: {scale, cells=[(mean,sd) x3]} in row order."""
    lines = _table1_lines(Path(pdf_path))
    out = []
    for scale in SCALES:
        nums = _row_for_scale(lines, scale)
        triples = []
        for mean_idx, _g, _sub, _n in GROUPS:
            mean = _to_float(nums[mean_idx])
            sd = _to_float(nums[mean_idx + 1])
            triples.append((mean, sd))
        out.append({"scale": scale, "cells": triples})
    return out


# --- view builders ---------------------------------------------------------

def _scale_name(scale):
    return f"{SCALE_PREFIX}_{scale}"


def _build_raw_df(parsed):
    """RAW view: packed 'mean (sd)' cells, mirroring the PDF columns."""
    def pk(ms): return f"{ms[0]} ({ms[1]})"
    recs = []
    for row in parsed:
        recs.append({
            "DERS scale": row["scale"],
            "Women (N=249)":          pk(row["cells"][0]),
            "Men (N=74)":             pk(row["cells"][1]),
            "Entire Sample (N=323)":  pk(row["cells"][2]),
        })
    return pd.DataFrame(recs)


def _build_parsed_df(parsed):
    """PARSED view: one row per scale x group, mean/sd/n split out."""
    recs = []
    for row in parsed:
        for col, (_idx, group, subsample, n) in enumerate(GROUPS):
            mean, sd = row["cells"][col]
            recs.append({
                "scale": row["scale"], "group": group,
                "sample": "healthy_controls", "subsample": subsample,
                "n": n, "mean": mean, "sd": sd,
            })
    return pd.DataFrame(recs)


def _build_rows(parsed):
    """Long-format rows: a mean row and an sd row per scale x group."""
    rows = []
    for row in parsed:
        scale = _scale_name(row["scale"])
        for col, (_idx, _group, subsample, n) in enumerate(GROUPS):
            mean, sd = row["cells"][col]
            rows.append(make_row(PUBLICATION, scale, "mean", "healthy_controls",
                                 mean, subsample=subsample, sample_size=n))
            rows.append(make_row(PUBLICATION, scale, "sd", "healthy_controls",
                                 sd, subsample=subsample, sample_size=n))
    return rows


def _write_sample_note(pdf_path):
    """Document the community/student -> healthy_controls compromise."""
    stem = Path(pdf_path).stem
    out_dir = Path("data/consolidated") / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    note = out_dir / f"{stem}.SAMPLE_NOTE.txt"
    note.write_text(
        "SAMPLE LABEL CAVEAT\n"
        "-------------------\n"
        "Table 1 reports Study 1 of Giromini et al. (2012): a sample of 323\n"
        "Italian psychology students. This is an explicitly NON-clinical\n"
        "community/student sample (people in psychiatric treatment or on\n"
        "psychiatric medication were excluded). They are NOT patients and NOT\n"
        "case-control 'healthy controls' in the usual sense.\n\n"
        "The pipeline's controlled vocabulary for `sample` only allows\n"
        "{patients, healthy_controls}. Every row from Table 1 is therefore\n"
        "tagged `healthy_controls` as the closest available fit. Treat as\n"
        "'community / non-clinical student sample'.\n\n"
        "NOTE: The paper's genuine clinical (eating-disorder) sample is in\n"
        "Table 6, handled separately -- it is NOT included here.\n"
    )
    print(f"sample note -> {note}")


def extract(pdf_path):
    """Scaffold entry point. All values parsed from the PDF; nothing hardcoded."""
    parsed = _parse_table1(pdf_path)
    raw_df = _build_raw_df(parsed)
    parsed_df = _build_parsed_df(parsed)
    rows = _build_rows(parsed)
    _write_sample_note(pdf_path)
    hardcoded_flag = False
    return raw_df, parsed_df, rows, hardcoded_flag
