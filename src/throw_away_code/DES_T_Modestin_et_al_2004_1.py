"""
DES_T_Modestin_et_al_2004.py
============================
Per-paper extractor for:
    Modestin & Erni (2004), "Testing the dissociative taxon",
    Psychiatry Research 126, 77-82.  Scale of interest: DES-T.

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching the interface scaffold.run_extraction() expects. Values are parsed
DIRECTLY from the PDF (pdfplumber), so hardcoded_flag is always False.

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* Table 1 is on PDF page index 3 (page 80 of the journal).
* pdfplumber.extract_text() renders each data row as ONE line:
      <label> <tok0> <tok1> ... <tok7>
  where the 8 tokens (after the row label) are, in order:
      0: N(%)                   <- group n
      1: DES-total Mn(S.D.)     <- ignored (DES total, not our scale)
      2: DES-total Md           <- ignored
      3: DES-total Mn>20 n(%)   <- ignored
      4: DES-T   Mn(S.D.)       <- WANTED  (mean + sd)
      5: DES-T   Md             <- WANTED  (median)
      6: DES-T   Mn>15 n(%)     <- kept for raw view only
      7: DES-T   Mn>35 n(%)     <- kept for raw view only
* The six data rows, in paper order, carry these labels:
      Nonpatients, T, Non-T, Patients, T, Non-T
  The first three belong to the non-clinical sample (healthy_controls),
  the last three to the clinical sample (patients). T / Non-T are the
  taxon / non-taxon SUBGROUPS that partition each parent group.
* Numbers use a normal dot decimal in this PDF; split_paren (scaffold)
  is comma-safe anyway.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from scaffold import make_row, split_paren, NA_MARKER

# --- fixed metadata for this paper ----------------------------------------
PUBLICATION = "Modestin & Erni 2004"
SCALE = "DES-T"
TABLE_PAGE_INDEX = 3  # 0-based pdfplumber page index for journal page 80

# The six data-row labels exactly as they appear at the start of each line.
_DATA_LINE_LABELS = ("Nonpatients", "T", "Non-T", "Patients", "T", "Non-T")

# How each table row maps onto the schema. (sample, subsample) per row,
# in paper order. T/Non-T partition their parent total.
_ROW_MAP = [
    ("healthy_controls", NA_MARKER),    # Nonpatients (parent total)
    ("healthy_controls", "taxon"),      # T
    ("healthy_controls", "non_taxon"),  # Non-T
    ("patients", NA_MARKER),            # Patients (parent total)
    ("patients", "taxon"),              # T
    ("patients", "non_taxon"),          # Non-T
]


# ---------------------------------------------------------------------------
# 1. Pull the raw table lines out of the PDF.
# ---------------------------------------------------------------------------

def _table_lines(pdf_path):
    """Return the six data-row strings from Table 1, in paper order.

    We locate rows by their known leading labels rather than by absolute
    line number, so small layout shifts don't break extraction. The
    Nonpatients/Patients lines are matched by prefix; the ambiguous T /
    Non-T labels are taken in the order they appear between them.
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[TABLE_PAGE_INDEX].extract_text()

    wanted = []
    for line in text.splitlines():
        stripped = line.strip()
        # A data row starts with one of the known labels followed by a space
        # and then a digit (the N(%) column). This filters out header/footer.
        if re.match(r"^(Nonpatients|Patients|Non-T|T)\s+\d", stripped):
            wanted.append(stripped)
    if len(wanted) != 6:
        raise ValueError(
            f"expected 6 data rows in Table 1, found {len(wanted)}: {wanted}"
        )
    return wanted


# ---------------------------------------------------------------------------
# 2. Split one data line into its fields.
# ---------------------------------------------------------------------------

def _fields(line):
    """Split a data line into [label, tok0, ... tok8] (10 fields).

    The label may be one token (e.g. 'T') and the rest are the 9 packed
    statistic cells separated by whitespace.
    """
    parts = line.split()
    # Re-join the label: every label here is a single whitespace-free token
    # ('Nonpatients', 'Patients', 'Non-T', 'T'), so parts[0] is the label.
    label, cells = parts[0], parts[1:]
    if len(cells) != 8:
        raise ValueError(f"expected 8 stat cells, got {len(cells)} in {line!r}")
    return label, cells


def _n_from_cell(cell):
    """'276(100)' -> 276 (the group n, dropping the percentage)."""
    m = re.match(r"^(\d+)\(", cell)
    if not m:
        raise ValueError(f"cannot read n from {cell!r}")
    return int(m.group(1))


# ---------------------------------------------------------------------------
# 3. Build the two verification frames (raw packed + parsed split).
# ---------------------------------------------------------------------------

# Column indices WITHIN the 8 stat cells (0-based, after the label):
#   cells[0] = N(%)
#   cells[1] = DES-total Mn(S.D.)   cells[2] = DES-total Md   cells[3] = DES-total Mn>20
#   cells[4] = DES-T   Mn(S.D.)     cells[5] = DES-T   Md
#   cells[6] = DES-T   Mn>15 n(%)   cells[7] = DES-T   Mn>35 n(%)
_C_N = 0
_C_DEST_MEANSD = 4
_C_DEST_MD = 5
_C_DEST_GT15 = 6
_C_DEST_GT35 = 7


def _build_raw_df(parsed_lines):
    """Raw view: packed cells, DES-T columns only, paper row order."""
    rows = []
    for label, cells in parsed_lines:
        rows.append({
            "Probands": label,
            "N (%)": cells[_C_N],
            "DES-T Mn (S.D.)": cells[_C_DEST_MEANSD],
            "DES-T Md": cells[_C_DEST_MD],
            "DES-T Mn>15 n (%)": cells[_C_DEST_GT15],
            "DES-T Mn>35 n (%)": cells[_C_DEST_GT35],
        })
    return pd.DataFrame(rows)


def _build_parsed_df(parsed_lines):
    """Parsed view: mean / sd / median / n split into columns."""
    rows = []
    for (label, cells), (sample, subsample) in zip(parsed_lines, _ROW_MAP):
        mean, sd = split_paren(cells[_C_DEST_MEANSD])
        median = float(cells[_C_DEST_MD])
        n = _n_from_cell(cells[_C_N])
        rows.append({
            "sample": sample,
            "subsample": subsample,
            "n": n,
            "mean": mean,
            "sd": sd,
            "median": median,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. Build the long-format rows (mean, sd, median per group).
# ---------------------------------------------------------------------------

def _build_rows(parsed_lines):
    """Emit make_row() dicts: mean, sd, median for each of the 6 groups."""
    rows = []
    for (label, cells), (sample, subsample) in zip(parsed_lines, _ROW_MAP):
        mean, sd = split_paren(cells[_C_DEST_MEANSD])
        median = float(cells[_C_DEST_MD])
        n = _n_from_cell(cells[_C_N])
        common = dict(publication=PUBLICATION, scale=SCALE,
                      sample=sample, subsample=subsample, sample_size=n)
        rows.append(make_row(data_type="mean", value=mean, **common))
        rows.append(make_row(data_type="sd", value=sd, **common))
        rows.append(make_row(data_type="median", value=median, **common))
    return rows


# ---------------------------------------------------------------------------
# 5. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse Table 1 DES-T columns directly from the PDF.

    Returns (raw_df, parsed_df, rows, hardcoded_flag). hardcoded_flag is
    False because every value is read from the PDF text.
    """
    lines = _table_lines(Path(pdf_path))
    parsed_lines = [_fields(ln) for ln in lines]  # [(label, cells), ...]

    raw_df = _build_raw_df(parsed_lines)
    parsed_df = _build_parsed_df(parsed_lines)
    rows = _build_rows(parsed_lines)
    return raw_df, parsed_df, rows, False
