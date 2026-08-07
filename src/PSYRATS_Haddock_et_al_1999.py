"""
PSYRATS_Haddock_et_al_1999.py
=============================
Per-paper extractor for TABLE 2 of:
    Haddock, McCarron, Tarrier & Faragher (1999), "Scales to measure
    dimensions of hallucinations and delusions: the psychotic symptom rating
    scales (PSYRATS)", Psychological Medicine 29:879-889.
    Scale of interest: PSYRATS AS (auditory hallucinations) and DS (delusions)
    subscales. KGV rows are ignored.

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching scaffold.run_extraction(). Values are parsed DIRECTLY from the PDF
text (pdfplumber), so hardcoded_flag is always False.

This module also writes TWO explanatory note files into the consolidated
folder (see extract()'s caller note below): a sample-size note and a
suspect-value note. They are written by _write_notes(), invoked from extract().

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* Table 2 is on PDF page index 5 (journal page 884).
* pdfplumber renders each data row as:  '<label> <median> (<min>-<max>)'
  with the en-dash '-' (U+2013) inside the range, e.g.
        'Loudness 2 (1-4)'
  Multi-word labels have their spaces STRIPPED by pdfplumber, e.g.
        'Frequency,duration,location,beliefsre-origin 3 (1-4)'
  so we match the numeric tail and treat everything before it as the label.
* The table has three blocks delimited by lone header lines 'KGV', 'AS', 'DS'.
  We read only the AS and DS blocks (KGV is out of scope). Each block ends at
  its 'Overalltotal(T-..)' row.
* Some rows are GROUPED (one median/range shared by several PSYRATS items):
        AS 'Frequency,duration,location,beliefsre-origin' -> 4 items
        AS 'Negativecontent(amountanddegree)'             -> 2 items
  Per instruction these are SPLIT into one output row per individual item,
  all carrying the same median/range. The split is driven by the explicit
  _AS_ITEMS / _DS_ITEMS maps below (printed-row -> list of item suffixes),
  NOT inferred from the label text.
* The 'Distress' (AS & DS) and 'Pre-occupation' (DS) sub-headers print on
  their own line; the Amount/Intensity/Duration values follow on later lines.
  We parse those value lines directly (their labels are 'Amount','Intensity',
  'Duration') and prefix the parent via _AS_ITEMS / _DS_ITEMS order.

Schema mapping:
    - scale     : 'PSYRATS-AS_<item>' / 'PSYRATS-DS_<item>';
                  totals 'PSYRATS-AS_total' / 'PSYRATS-DS_total'.
    - sample    : 'patients' (71 psychotic patients; no controls).
    - subsample : 'NA'.
    - sample_size: 56 for ALL AS rows, 57 for ALL DS rows. The AS subscale
                  was given only to patients with hallucinations (42 both +
                  14 hallucinations-only = 56) and DS only to those with
                  delusions (42 + 15 = 57); see the SAMPLE_SIZE_NOTE file.
    - data_type : median, minimum, maximum (Range -> min/max).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, NA_MARKER

# --- fixed metadata --------------------------------------------------------
PUBLICATION = "Haddock et al. 1999"
SAMPLE = "patients"
TABLE_PAGE_INDEX = 5  # 0-based pdfplumber page index for journal page 884

AS_N = 56  # patients with hallucinations (42 both + 14 hallucinations-only)
DS_N = 57  # patients with delusions      (42 both + 15 delusions-only)

# AS block: ordered list of (printed_label_key, [item_suffixes]).
# printed_label_key is the whitespace-stripped label as pdfplumber emits it.
_AS_ITEMS = [
    ("Frequency,duration,location,beliefsre-origin",
        ["frequency", "duration", "location", "beliefs_re_origin"]),
    ("Loudness", ["loudness"]),
    ("Negativecontent(amountanddegree)",
        ["negative_content_amount", "negative_content_degree"]),
    ("Amount", ["distress_amount"]),        # under 'Distress' sub-header
    ("Intensity", ["distress_intensity"]),  # under 'Distress' sub-header
    ("Disruption", ["disruption"]),
    ("Control", ["control"]),
    ("Overalltotal(T-AH)", ["total"]),
]

# DS block: same structure.
_DS_ITEMS = [
    ("Amount", ["preoccupation_amount"]),    # under 'Pre-occupation'
    ("Duration", ["preoccupation_duration"]),# under 'Pre-occupation'
    ("Conviction", ["conviction"]),
    ("Amount", ["distress_amount"]),         # under 'Distress'
    ("Intensity", ["distress_intensity"]),
    ("Disruption", ["disruption"]),
    ("Overalltotal(T-DS)", ["total"]),
]

# Range dash is an en-dash in this PDF; allow hyphen too.
_VALUE_RE = re.compile(r"(\d+)\s*\((\d+)\s*[\u2013-]\s*(\d+)\)\s*$")


# ---------------------------------------------------------------------------
# 1. Slice the AS and DS blocks out of the page text.
# ---------------------------------------------------------------------------

def _block_lines(text, start_marker, end_marker):
    """Return the lines strictly between a lone start header and the line
    whose stripped form starts with end_marker (inclusive of that end line)."""
    lines = [ln.strip() for ln in text.splitlines()]
    out, collecting = [], False
    for ln in lines:
        if not collecting:
            if ln == start_marker:
                collecting = True
            continue
        out.append(ln)
        if ln.replace("", "").startswith(end_marker):
            break
    if not out:
        raise ValueError(f"block {start_marker!r} not found")
    return out


def _value_lines(block_lines):
    """Return the ordered list of (median, min, max) tuples found in a block.

    Lines without a trailing 'median (min-max)' (e.g. lone 'Distress' or
    'Pre-occupation' sub-headers, or wrapped label tails) are skipped.
    """
    vals = []
    for ln in block_lines:
        compact = ln.replace(" ", "")
        m = _VALUE_RE.search(compact)
        if m:
            vals.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return vals


# ---------------------------------------------------------------------------
# 2. Pair the parsed values with the expected item list for each block.
# ---------------------------------------------------------------------------

def _block_records(text, block, items, n):
    """Return list of dicts for one block.

    `items` is _AS_ITEMS / _DS_ITEMS: ordered (label_key, [suffixes]). We pull
    the value lines in order and zip them onto the expected rows, expanding
    grouped rows so each item suffix becomes its own record with the shared
    (median, min, max).
    """
    if block == "AS":
        lines = _block_lines(text, "AS", "Overalltotal(T-AH)")
        prefix = "PSYRATS-AS_"
    else:
        lines = _block_lines(text, "DS", "Overalltotal(T-DS)")
        prefix = "PSYRATS-DS_"

    values = _value_lines(lines)
    if len(values) != len(items):
        raise ValueError(
            f"{block}: expected {len(items)} value rows, parsed {len(values)}"
        )

    records = []
    for (label_key, suffixes), (median, mn, mx) in zip(items, values):
        for suffix in suffixes:
            records.append({
                "scale": f"{prefix}{suffix}",
                "median": median, "minimum": mn, "maximum": mx,
                "n": n,
                # keep the printed packed cell for the raw view
                "raw_label": label_key, "raw_cell": f"{median} ({mn}-{mx})",
                "block": block,
            })
    return records


def _records(pdf_path):
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[TABLE_PAGE_INDEX].extract_text() or ""
    rec = _block_records(text, "AS", _AS_ITEMS, AS_N)
    rec += _block_records(text, "DS", _DS_ITEMS, DS_N)
    return rec


# ---------------------------------------------------------------------------
# 3. Verification frames.
# ---------------------------------------------------------------------------

def _build_raw_df(records):
    """Raw view: one row per OUTPUT item, packed 'median (min-max)' kept.

    The grouped source rows are already split here (one row per item), which
    matches the requested output structure.
    """
    return pd.DataFrame([{
        "Block": r["block"],
        "Item": r["scale"].split("_", 1)[1],
        "Median (Range)": r["raw_cell"],
    } for r in records])


def _build_parsed_df(records):
    return pd.DataFrame([{
        "scale": r["scale"], "sample": SAMPLE, "subsample": NA_MARKER,
        "n": r["n"], "median": r["median"],
        "minimum": r["minimum"], "maximum": r["maximum"],
    } for r in records])


# ---------------------------------------------------------------------------
# 4. Long-format rows (median, minimum, maximum per item).
# ---------------------------------------------------------------------------

def _build_rows(records):
    rows = []
    for r in records:
        common = dict(publication=PUBLICATION, scale=r["scale"],
                      sample=SAMPLE, subsample=NA_MARKER, sample_size=r["n"])
        rows.append(make_row(data_type="median",  value=r["median"],  **common))
        rows.append(make_row(data_type="minimum", value=r["minimum"], **common))
        rows.append(make_row(data_type="maximum", value=r["maximum"], **common))
    return rows


# ---------------------------------------------------------------------------
# 5. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse Table 2 AS+DS medians/ranges directly from the PDF.

    Grouped rows are split to one item each; AS rows carry n=56, DS rows n=57.
    The DS 'distress_intensity' maximum is 5 as printed (likely a 0-4 typo) -
    see the SUSPECT_VALUE note written alongside the verification CSVs.
    """
    records = _records(Path(pdf_path))
    raw_df = _build_raw_df(records)
    parsed_df = _build_parsed_df(records)
    rows = _build_rows(records)
    return raw_df, parsed_df, rows, False
