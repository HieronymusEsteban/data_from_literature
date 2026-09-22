"""
Per-paper extractor: Neumann et al. 2010, DERS in Dutch adolescents.
Scale of interest: the six DERS subscales (mean + SD), for three groups:
Total sample, Males, Females.

Returns (raw_df, parsed_df, rows, hardcoded_flag) for scaffold.run_extraction.

SAMPLE-LABEL CAVEAT
-------------------
This is a general COMMUNITY sample of adolescents (one school, non-clinical) --
not patients and not case-control "healthy controls". The scaffold's controlled
vocabulary only allows {patients, healthy_controls}, so every row is tagged
`healthy_controls` as the closest fit. A note file documenting this compromise
is written next to the consolidated output (see _write_sample_note / extract).

PAPER-SPECIFIC LAYOUT ASSUMPTIONS
---------------------------------
* Table 4 ("Mean DERS, Anxiety, Depression, ... Scores (Standard Deviations)")
  is on the 8th PDF page (0-indexed page 7). pdfplumber extracts it as text.
* The DERS block sits between the 'DERS  N = 870 ...' header line and the
  'Externalizing ...' header line. We only parse rows in that block (the
  Externalizing / Internalizing rows are other scales -> out of scope).
* Each DERS data line holds three packed 'mean (SD)' cells in column order
  Total sample, Males, Females, e.g.
      'Lack of Emotional Awareness 18.45 (4.92) 19.63 (4.74) 17.31 (4.81) 51.47** .49'
  Two subscale names wrap onto a following continuation line (e.g.
  'Behavior When Distressed'); those continuation lines carry no numbers and
  are skipped. We therefore identify data rows by the presence of the
  'mean (SD)' pattern, and take the subscale NAME from a fixed known list
  rather than from the (wrapped) text, so wrapping cannot corrupt the label.
* Group Ns are fixed in the header: Total 870, Males 429, Females 441.
* Only mean and SD are reported (no median).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, split_paren, NA_MARKER

PUBLICATION = "Neumann et al. 2010"
TABLE4_PAGE = 7                       # 0-indexed PDF page holding Table 4
SCALE_PREFIX = "DERS"

# Canonical subscale names, in the paper's row order. The matching uses the
# table's own (sometimes wrapped) text only to locate rows; these strings are
# what we actually emit, so wrapped labels never reach the output.
SUBSCALES = [
    "Lack of Emotional Awareness",
    "Lack of Emotional Clarity",
    "Difficulties Controlling Impulsive Behavior When Distressed",
    "Difficulties Engaging in Goal-Directed Behavior When Distressed",
    "Nonacceptance of Negative Emotional Responses",
    "Limited Access to ER Strategies",
]

# Three groups, in the table's left-to-right column order, with fixed Ns and
# the subsample label we map each to.
GROUPS = [
    # column_index_in_packed_cells, group_name, subsample, n
    (0, "Total sample", NA_MARKER, 870),
    (1, "Males",        "male",    429),
    (2, "Females",      "female",  441),
]

# A packed 'mean (SD)' cell, e.g. '18.45 (4.92)'.
_CELL = re.compile(r"[-\d.]+\s*\([-\d.]+\)")


def _table4_lines(pdf_path):
    """Return text lines of the Table-4 page."""
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        return pdf.pages[TABLE4_PAGE].extract_text().split("\n")


def _ders_block_lines(lines):
    """Return only the lines between the 'DERS  N = ...' header and the
    'Externalizing' header -- i.e. the six DERS data rows (plus any wrapped
    continuation lines, which carry no numbers)."""
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("DERS") and "N =" in ln)
    end = next(i for i, ln in enumerate(lines) if ln.startswith("Externalizing"))
    return lines[start + 1:end]


def _packed_cells(line):
    """Return the list of 'mean (SD)' strings on a line (empty if none)."""
    return [m.group(0).replace(" ", "") for m in _CELL.finditer(line)]


def _parse_block(lines):
    """Pair each data line (one with 3 packed cells) with the next canonical
    subscale name, in order. Returns list of dicts:
    {subscale, cells=[(mean,sd) x3]}."""
    out = []
    for ln in lines:
        cells = _packed_cells(ln)
        if len(cells) < 3:            # continuation line (wrapped name) -> skip
            continue
        subscale = SUBSCALES[len(out)]            # rows arrive in fixed order
        triples = [split_paren(c) for c in cells[:3]]   # Total, Males, Females
        out.append({"subscale": subscale, "cells": triples})
    return out


def _parse_table4(pdf_path):
    return _parse_block(_ders_block_lines(_table4_lines(Path(pdf_path))))


# --- view builders ---------------------------------------------------------

def _scale_name(subscale):
    return f"{SCALE_PREFIX}_{subscale}"


def _build_raw_df(parsed):
    """RAW view: packed 'mean (SD)' cells, mirroring the PDF columns."""
    def pk(ms): return f"{ms[0]} ({ms[1]})"
    recs = []
    for row in parsed:
        recs.append({
            "DERS subscale": row["subscale"],
            "Total sample (N=870)": pk(row["cells"][0]),
            "Males (n=429)":        pk(row["cells"][1]),
            "Females (n=441)":      pk(row["cells"][2]),
        })
    return pd.DataFrame(recs)


def _build_parsed_df(parsed):
    """PARSED view: one row per subscale x group, mean/sd/n split out."""
    recs = []
    for row in parsed:
        for col, group, subsample, n in GROUPS:
            mean, sd = row["cells"][col]
            recs.append({
                "subscale": row["subscale"], "group": group,
                "sample": "healthy_controls", "subsample": subsample,
                "n": n, "mean": mean, "sd": sd,
            })
    return pd.DataFrame(recs)


def _build_rows(parsed):
    """Long-format rows: a mean row and an sd row per subscale x group."""
    rows = []
    for row in parsed:
        scale = _scale_name(row["subscale"])
        for col, _group, subsample, n in GROUPS:
            mean, sd = row["cells"][col]
            rows.append(make_row(PUBLICATION, scale, "mean", "healthy_controls",
                                 mean, subsample=subsample, sample_size=n))
            rows.append(make_row(PUBLICATION, scale, "sd", "healthy_controls",
                                 sd, subsample=subsample, sample_size=n))
    return rows


def _write_sample_note(pdf_path):
    """Document the community-sample / healthy_controls compromise next to the
    consolidated output."""
    stem = Path(pdf_path).stem
    out_dir = Path("data/consolidated") / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    note = out_dir / f"{stem}.SAMPLE_NOTE.txt"
    note.write_text(
        "SAMPLE LABEL CAVEAT\n"
        "-------------------\n"
        "Neumann et al. (2010) studied a general COMMUNITY sample of 870 Dutch\n"
        "adolescents from a single school. They are NOT clinical patients and\n"
        "NOT case-control 'healthy controls' in the usual sense -- just a\n"
        "non-clinical community sample.\n\n"
        "The pipeline's controlled vocabulary for `sample` only allows\n"
        "{patients, healthy_controls}. Every DERS row from this paper is therefore\n"
        "tagged `healthy_controls` as the closest available fit. Treat this as\n"
        "'community / non-clinical', not as a matched control group.\n"
    )
    print(f"sample note -> {note}")


def extract(pdf_path):
    """Scaffold entry point. All values parsed from the PDF; nothing hardcoded."""
    parsed = _parse_table4(pdf_path)
    raw_df = _build_raw_df(parsed)
    parsed_df = _build_parsed_df(parsed)
    rows = _build_rows(parsed)
    _write_sample_note(pdf_path)
    hardcoded_flag = False
    return raw_df, parsed_df, rows, hardcoded_flag
