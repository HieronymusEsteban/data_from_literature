"""
DES_T_Levin_et_al_2003.py
=========================
Per-paper extractor for:
    Levin & Spei (2003), "Relationship of Purported Measures of Pathological
    and Nonpathological Dissociation to Self-Reported Psychological Distress
    and Fantasy Immersion", Assessment 11(2):160-168.
    Scale of interest: DES-T.

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching scaffold.run_extraction(). Values are parsed DIRECTLY from the PDF
text (pdfplumber), so hardcoded_flag is always False.

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* Table 1 is on PDF page index 4 (journal page 164).
* This table is TRANSPOSED relative to the other DES-T papers:
  statistics are ROWS and scales are COLUMNS. The three data columns are,
  in order:  DES   DES-T   DES-A.  We want the MIDDLE one (DES-T).
* The whole study is ONE nonclinical community sample (N = 376), so every
  value maps to sample='healthy_controls', subsample='NA'. N is taken from
  the table caption "(N = 376)", not from a per-row cell.
* pdfplumber renders the page in a two-column layout, so some table rows
  have body-text prose PREPENDED on the same physical line, e.g.
      '...collapsed across sex. Median 10.0 2.5 15.0'
  The three numbers always sit at the END of the line, so we locate each
  row by its label keyword and take the LAST 3 whitespace tokens. DES-T is
  index 1 of those three.
* Rows we read and how they map to the schema:
      Mean               -> mean
      Standard deviation -> sd
      Median             -> median
      Range  '0-64.4'    -> minimum (0) and maximum (64.4)
  Kurtosis and Skewness are intentionally ignored (not in the schema
  vocabulary).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, NA_MARKER

# --- fixed metadata for this paper ----------------------------------------
PUBLICATION = "Levin & Spei 2003"
SCALE = "DES-T"
TABLE_PAGE_INDEX = 4  # 0-based pdfplumber page index for journal page 164

_DEST_COL = 1  # DES-T is the middle of the three columns: DES, DES-T, DES-A

# Row label keywords as they appear at the start of the table-data portion
# of each line. Order here is the order shown in the RAW verification view.
_STAT_LABELS = ["Mean", "Standard deviation", "Median",
                "Kurtosis", "Skewness", "Range"]


# ---------------------------------------------------------------------------
# 1. Pull the DES-T value for each statistic row out of the PDF.
# ---------------------------------------------------------------------------

def _row_tail(text, label):
    """Find the line carrying `label` and return its last 3 tokens.

    The three tokens are the DES / DES-T / DES-A columns. Body-text prose
    may precede the label on the same physical line, so we search for the
    label followed by the three trailing numeric/range tokens.
    """
    # Match: <label> <tok> <tok> <tok> at END of a line. Tokens are numbers,
    # 'mean(sd)'-free here, or ranges like '0-64.4'.
    pat = re.compile(
        rf"{re.escape(label)}\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*$",
        re.MULTILINE,
    )
    m = pat.search(text)
    if not m:
        raise ValueError(f"Table 1 row {label!r} not found")
    return [m.group(1), m.group(2), m.group(3)]


def _dest_values(pdf_path):
    """Return {label: DES-T_token} for each statistic row in Table 1."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[TABLE_PAGE_INDEX].extract_text()

    return {label: _row_tail(text, label)[_DEST_COL] for label in _STAT_LABELS}


def _sample_size(pdf_path):
    """Read the overall N from the table caption '(N = 376)'."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[TABLE_PAGE_INDEX].extract_text()
    m = re.search(r"\(N\s*=\s*(\d+)\)", text)
    if not m:
        raise ValueError("could not find sample size '(N = ...)' for Table 1")
    return int(m.group(1))


def _split_range(tok):
    """'0-64.4' -> (0.0, 64.4). Handles a leading-zero minimum cleanly."""
    m = re.match(r"^([\d.]+)-([\d.]+)$", tok)
    if not m:
        raise ValueError(f"cannot parse range from {tok!r}")
    return float(m.group(1)), float(m.group(2))


# ---------------------------------------------------------------------------
# 2. Verification frames.
# ---------------------------------------------------------------------------

def _build_raw_df(dest):
    """Raw view: statistic label + DES-T cell, in paper row order."""
    return pd.DataFrame(
        [{"Statistic": label, "DES-T": dest[label]} for label in _STAT_LABELS]
    )


def _build_parsed_df(dest, n):
    """Parsed view: single row with mean/sd/median/min/max split out."""
    minimum, maximum = _split_range(dest["Range"])
    return pd.DataFrame([{
        "sample": "healthy_controls",
        "subsample": NA_MARKER,
        "n": n,
        "mean": float(dest["Mean"]),
        "sd": float(dest["Standard deviation"]),
        "median": float(dest["Median"]),
        "minimum": minimum,
        "maximum": maximum,
    }])


# ---------------------------------------------------------------------------
# 3. Long-format rows (mean, sd, median, minimum, maximum for the one sample).
# ---------------------------------------------------------------------------

def _build_rows(dest, n):
    minimum, maximum = _split_range(dest["Range"])
    common = dict(publication=PUBLICATION, scale=SCALE,
                  sample="healthy_controls", subsample=NA_MARKER,
                  sample_size=n)
    return [
        make_row(data_type="mean",    value=float(dest["Mean"]), **common),
        make_row(data_type="sd",      value=float(dest["Standard deviation"]), **common),
        make_row(data_type="median",  value=float(dest["Median"]), **common),
        make_row(data_type="minimum", value=minimum, **common),
        make_row(data_type="maximum", value=maximum, **common),
    ]


# ---------------------------------------------------------------------------
# 4. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse Table 1 DES-T column directly from the PDF."""
    pdf_path = Path(pdf_path)
    dest = _dest_values(pdf_path)
    n = _sample_size(pdf_path)

    raw_df = _build_raw_df(dest)
    parsed_df = _build_parsed_df(dest, n)
    rows = _build_rows(dest, n)
    return raw_df, parsed_df, rows, False
