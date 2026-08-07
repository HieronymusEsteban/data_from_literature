"""
DES_T_Giesbrecht_et_al_2007.py
==============================
Per-paper extractor for:
    Giesbrecht, Merckelbach & Geraerts (2007),
    "The Dissociative Experiences Taxon Is Related to Fantasy Proneness",
    J Nerv Ment Dis 195(9):769-772.  Scale of interest: DES-T.

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching scaffold.run_extraction(). Values are parsed DIRECTLY from the PDF
text (pdfplumber), so hardcoded_flag is always False.

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* Table 1 is on PDF page index 1 (journal page 770).
* The table is mean(SD) only -- there is NO median, min, or max.
* We want the DES-T column ONLY (not DES, DES-A, DES-T Taxon, DES-T-50/90,
  or CEQ).
* pdfplumber.extract_text() renders each data row as ONE line:
      <label...> <N(Women)> <Age> <DES> <DES-A> <DES-T> <DES-T taxon> \
                 <DES-T-50> <DES-T-90> <CEQ>
  i.e. after the trailing 9 numeric cells, the leading text is the label.
  We therefore parse each data row from the RIGHT: the last 9 whitespace-
  separated tokens are the numeric columns, and everything before them is
  the subsample label. This is robust to the "Borderline personality
  disorder" label wrapping onto two physical lines (the numbers all sit on
  the first line; the stray "disorder" lands on its own line with no
  numbers and is skipped).
* Of those 9 trailing numeric cells, by position (0-based):
      0: N(Women)        3: DES-A           6: DES-T-50 (%)
      1: Age             4: DES-T   <-WANT  7: DES-T-90 (%)
      2: DES             5: DES-T taxon     8: CEQ
  N is in cell 0 as 'n(women)'; the DES-T mean(SD) is cell 4.

CSA classification: assigned to `patients` per user instruction (the women
with a childhood-sexual-abuse history are treated as the clinical group of
interest, alongside the three psychiatric subsamples).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, split_paren

# --- fixed metadata for this paper ----------------------------------------
PUBLICATION = "Giesbrecht et al. 2007"
SCALE = "DES-T"
TABLE_PAGE_INDEX = 1  # 0-based pdfplumber page index for journal page 770

N_NUMERIC_CELLS = 9   # trailing numeric columns on each data row
_C_N = 0              # cell index of 'N(Women)'
_C_DEST_MEANSD = 4    # cell index of DES-T mean(SD)

# The six subsample labels exactly as they read once whitespace is stripped
# and the wrapped "Borderlinepersonality ... disorder" is rejoined. Keys are
# the normalized (spaces removed) label that appears at the start of the row;
# values are (schema_subsample, sample).
_ROW_MAP = {
    "Students":               ("students", "healthy_controls"),
    "Healthyadultwomen":      ("healthy_adult_women", "healthy_controls"),
    "Schizophrenia":          ("schizophrenia", "patients"),
    "Borderlinepersonality":  ("borderline_personality_disorder", "patients"),
    "Mooddisorder":           ("mood_disorder", "patients"),
    "CSA":                    ("csa", "patients"),
}

# Human-readable labels for the RAW verification view, in paper row order.
_RAW_LABELS = {
    "Students": "Students",
    "Healthyadultwomen": "Healthy adult women",
    "Schizophrenia": "Schizophrenia",
    "Borderlinepersonality": "Borderline personality disorder",
    "Mooddisorder": "Mood disorder",
    "CSA": "CSA",
}

# Fixed paper order so output is deterministic.
_ORDER = ["Students", "Healthyadultwomen", "Schizophrenia",
          "Borderlinepersonality", "Mooddisorder", "CSA"]


# ---------------------------------------------------------------------------
# 1. Pull the data rows out of the PDF and key them by normalized label.
# ---------------------------------------------------------------------------

def _data_rows(pdf_path):
    """Return {normalized_label: [9 numeric cells]} for the six subgroups.

    A data row is any line whose LAST token is a packed 'mean(sd)' or bare
    number AND that contains at least N_NUMERIC_CELLS trailing numeric cells.
    We split from the right so the (possibly multi-word) label stays intact.
    """
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[TABLE_PAGE_INDEX].extract_text()

    rows = {}
    for line in text.splitlines():
        tokens = line.strip().split()
        if len(tokens) < N_NUMERIC_CELLS + 1:
            continue
        tail = tokens[-N_NUMERIC_CELLS:]
        # Every tail cell must look numeric: '12.34', '12.34(5.6)', '13.80'.
        if not all(re.match(r"^[\d.]+(\([\d.]+\))?$", t) for t in tail):
            continue
        label = "".join(tokens[:-N_NUMERIC_CELLS])  # normalized (no spaces)
        if label in _ROW_MAP:
            rows[label] = tail
    missing = set(_ROW_MAP) - set(rows)
    if missing:
        raise ValueError(f"Table 1 rows not found: {sorted(missing)}")
    return rows


def _n_from_cell(cell):
    """'930(699)' -> 930 (group n, dropping the women count)."""
    m = re.match(r"^(\d+)\(", cell)
    if not m:
        raise ValueError(f"cannot read n from {cell!r}")
    return int(m.group(1))


# ---------------------------------------------------------------------------
# 2. Verification frames.
# ---------------------------------------------------------------------------

def _build_raw_df(rows):
    """Raw view: packed DES-T mean(sd) cell only, paper row order."""
    out = []
    for key in _ORDER:
        cells = rows[key]
        # Reformat 'n(women)' and 'mean(sd)' with a space for readability,
        # matching the verification view shown to the user.
        n_cell = re.sub(r"\(", " (", cells[_C_N])
        dest = re.sub(r"\(", " (", cells[_C_DEST_MEANSD])
        out.append({
            "Subsamples": _RAW_LABELS[key],
            "N (Women)": n_cell,
            "DES-T": dest,
        })
    return pd.DataFrame(out)


def _build_parsed_df(rows):
    """Parsed view: mean / sd / n split into columns."""
    out = []
    for key in _ORDER:
        cells = rows[key]
        subsample, sample = _ROW_MAP[key]
        mean, sd = split_paren(cells[_C_DEST_MEANSD])
        out.append({
            "sample": sample,
            "subsample": subsample,
            "n": _n_from_cell(cells[_C_N]),
            "mean": mean,
            "sd": sd,
        })
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# 3. Long-format rows (mean + sd per group; no median in this table).
# ---------------------------------------------------------------------------

def _build_rows(rows):
    out = []
    for key in _ORDER:
        cells = rows[key]
        subsample, sample = _ROW_MAP[key]
        mean, sd = split_paren(cells[_C_DEST_MEANSD])
        n = _n_from_cell(cells[_C_N])
        common = dict(publication=PUBLICATION, scale=SCALE,
                      sample=sample, subsample=subsample, sample_size=n)
        out.append(make_row(data_type="mean", value=mean, **common))
        out.append(make_row(data_type="sd", value=sd, **common))
    return out


# ---------------------------------------------------------------------------
# 4. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse Table 1 DES-T mean column directly from the PDF."""
    rows = _data_rows(Path(pdf_path))
    raw_df = _build_raw_df(rows)
    parsed_df = _build_parsed_df(rows)
    long_rows = _build_rows(rows)
    return raw_df, parsed_df, long_rows, False
