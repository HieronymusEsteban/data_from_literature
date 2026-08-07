"""
DES-T_Modestin_et_al_2004.py
============================
Per-paper extractor for:
    Modestin & Erni (2004), "Testing the dissociative taxon",
    Psychiatry Research 126, 77-82.

Scale of interest : DES-T (taxon subscale of the DES).
Source            : Table 1, on PDF page 4 (0-indexed page 3).

This module exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded).
It parses the numbers DIRECTLY from the PDF text (no hardcoded values).

----------------------------------------------------------------------------
LAYOUT ASSUMPTIONS (so you can debug later)
----------------------------------------------------------------------------
Table 1 lives on PDF page index 3. pdfplumber.extract_text() returns it as
six data lines, each a whitespace-separated list of tokens:

    label  N(%)  | DES-total: Mn(S.D.) Md Mn>20n(%) | DES-T: Mn(S.D.) Md Mn>15n(%) Mn>35n(%)

Concretely (line 6, Nonpatients):
    'Nonpatients 276(100) 10.4(9.6) 8.0 31(11) 5.0(9.3) 1.7 22(8) 5(2)'
     tok[0]      tok[1]   tok[2]    tok3 tok4   tok[5]   tok6 tok7  tok8
     label       parentN  --- DES-total (ignored) ---  ^^^^^ DES-T ^^^^^

So for every data row, counting tokens from the END is the robust trick:
    tok[-4] = DES-T  Mn(S.D.)   e.g. '5.0(9.3)'   -> mean, sd
    tok[-3] = DES-T  Md         e.g. '1.7'        -> median
    tok[-2] = DES-T  Mn>15 n(%)  (cut-off count, NOT a descriptive stat)
    tok[-1] = DES-T  Mn>35 n(%)  (cut-off count, NOT a descriptive stat)
and tok[1] = this row's own N(%), e.g. '276(100)' -> group n.

The Mn>15 / Mn>35 columns are taxon-classification tallies, not descriptive
statistics of the scale, so they are shown in the RAW view but NOT emitted as
long-format rows.

Row labels and their schema mapping:
    'Nonpatients' -> healthy_controls, subsample NA   (parent)
    'T'  (under Nonpatients) -> healthy_controls, subsample 'taxon'
    'Non-T'                  -> healthy_controls, subsample 'non_taxon'
    'Patients'    -> patients,         subsample NA   (parent)
    'T'  (under Patients)    -> patients,         subsample 'taxon'
    'Non-T'                  -> patients,         subsample 'non_taxon'

The two 'T'/'Non-T' blocks are distinguished by ORDER: the first
Nonpatients/T/Non-T trio belongs to healthy_controls, the second
Patients/T/Non-T trio to patients. NOTE: T + Non-T partition each parent
(8+268=276; 26+181=207), and the subgroups are defined BY a DES-T-derived
classification, so their DES-T stats are circular w.r.t. this scale.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from scaffold import make_row, split_paren, NA_MARKER

# ---------------------------------------------------------------------------
# Paper-specific constants
# ---------------------------------------------------------------------------
PUBLICATION = "Modestin & Erni 2004"
SCALE = "DES-T"
TABLE_PAGE_INDEX = 3          # PDF page 4, 0-indexed
DATA_ROW_LABELS = {"Nonpatients", "T", "Non-T", "Patients"}


# ---------------------------------------------------------------------------
# 1. Pull the six Table-1 data lines off the PDF page.
# ---------------------------------------------------------------------------

def _read_table_lines(pdf_path):
    """Return the six raw data lines of Table 1 as lists of tokens.

    A data line is one whose first token is a known row label. We keep them
    in document order (Nonpatients, T, Non-T, Patients, T, Non-T).
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[TABLE_PAGE_INDEX].extract_text()

    rows = []
    for line in text.split("\n"):
        toks = line.split()
        if toks and toks[0] in DATA_ROW_LABELS:
            rows.append(toks)
    if len(rows) != 6:
        raise ValueError(f"expected 6 data rows, found {len(rows)}: "
                         f"{[r[0] for r in rows]}")
    return rows


# ---------------------------------------------------------------------------
# 2. Turn the six token-lists into structured records.
# ---------------------------------------------------------------------------

def _n_from_cell(cell):
    """'276(100)' -> 276 (the group n, ignoring the percentage)."""
    m = re.match(r"^(\d+)\(", cell)
    if not m:
        raise ValueError(f"cannot read n from {cell!r}")
    return int(m.group(1))


# Fixed sample/subsample mapping, applied in document order. The first three
# rows are the Nonpatients trio, the next three the Patients trio.
_ROW_PLAN = [
    ("healthy_controls", NA_MARKER),    # Nonpatients
    ("healthy_controls", "taxon"),      # T
    ("healthy_controls", "non_taxon"),  # Non-T
    ("patients",         NA_MARKER),    # Patients
    ("patients",         "taxon"),      # T
    ("patients",         "non_taxon"),  # Non-T
]


def _parse_rows(token_lines):
    """Map the six token-lists to dicts of DES-T descriptive values.

    Uses negative indexing so the (ignored) DES-total columns in the middle
    don't matter: DES-T Mn(S.D.) is always tok[-4], Md is tok[-3].
    """
    records = []
    for toks, (sample, subsample) in zip(token_lines, _ROW_PLAN):
        label = toks[0]
        n = _n_from_cell(toks[1])
        mean, sd = split_paren(toks[-4])   # DES-T 'Mn(S.D.)'
        median = float(toks[-3])           # DES-T 'Md'
        records.append({
            "label": label,
            "sample": sample,
            "subsample": subsample,
            "n": n,
            "mean": mean,
            "sd": sd,
            "median": median,
            # cut-off tallies kept only for the raw view
            "cut15": toks[-2],
            "cut35": toks[-1],
            "parentN": toks[1],
        })
    return records


# ---------------------------------------------------------------------------
# 3. Build the two verification views.
# ---------------------------------------------------------------------------

def _build_raw_df(records):
    """RAW view: DES-T columns kept packed, mirroring the PDF row order."""
    return pd.DataFrame([{
        "Probands": r["label"],
        "N (%)": r["parentN"],
        "DES-T Mn (S.D.)": f"{r['mean']} ({r['sd']})",
        "DES-T Md": r["median"],
        "DES-T Mn>15 n (%)": r["cut15"],
        "DES-T Mn>35 n (%)": r["cut35"],
    } for r in records])


def _build_parsed_df(records):
    """PARSED view: mean / sd / median split into columns."""
    label_map = {
        ("healthy_controls", NA_MARKER): "Nonpatients",
        ("healthy_controls", "taxon"): "Nonpatients - T",
        ("healthy_controls", "non_taxon"): "Nonpatients - Non-T",
        ("patients", NA_MARKER): "Patients",
        ("patients", "taxon"): "Patients - T",
        ("patients", "non_taxon"): "Patients - Non-T",
    }
    return pd.DataFrame([{
        "group_label": label_map[(r["sample"], r["subsample"])],
        "sample": r["sample"],
        "subsample": r["subsample"],
        "n": r["n"],
        "mean": r["mean"],
        "sd": r["sd"],
        "median": r["median"],
    } for r in records])


# ---------------------------------------------------------------------------
# 4. Build the long-format rows (mean, sd, median per group).
# ---------------------------------------------------------------------------

def _build_rows(records):
    """One make_row() per descriptive statistic per group."""
    rows = []
    for r in records:
        common = dict(publication=PUBLICATION, scale=SCALE,
                      sample=r["sample"], subsample=r["subsample"],
                      sample_size=r["n"])
        rows.append(make_row(data_type="mean", value=r["mean"], **common))
        rows.append(make_row(data_type="sd", value=r["sd"], **common))
        rows.append(make_row(data_type="median", value=r["median"], **common))
    return rows


# ---------------------------------------------------------------------------
# 5. Public entry point expected by the scaffold.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Return (raw_df, parsed_df, rows, hardcoded_flag) for this paper."""
    token_lines = _read_table_lines(Path(pdf_path))
    records = _parse_rows(token_lines)

    raw_df = _build_raw_df(records)
    parsed_df = _build_parsed_df(records)
    rows = _build_rows(records)
    hardcoded = False          # everything parsed directly from the PDF
    return raw_df, parsed_df, rows, hardcoded
