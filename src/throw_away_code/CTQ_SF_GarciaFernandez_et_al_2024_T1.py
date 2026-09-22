"""
CTQ_SF_GarciaFernandez_et_al_2024_T1.py
=======================================
Per-paper extractor for TABLE 1 (item-level reliability characteristics) of:
    Garcia-Fernandez et al. (2024), "Validation of the Spanish Childhood
    Trauma Questionnaire-Short Form in adolescents with suicide attempts",
    Front. Psychol. 15:1378486.
    Scale of interest: CTQ-SF, all 28 items across 6 subscale blocks.

NOTE: this is the SAME PDF as the Table-3 extractor
(CTQ_SF_GarciaFernandez_et_al_2024.py). It is kept as a SEPARATE module with a
'_T1' suffix so both tables can be imported without a name clash. The notebook
imports it as:  from CTQ_SF_GarciaFernandez_et_al_2024_T1 import extract

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching scaffold.run_extraction(). Values are parsed DIRECTLY from the PDF
text (pdfplumber), so hardcoded_flag is always False.

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* Table 1 ("Reliability characteristics of CTQ-SF subscales") is on PDF page
  index 2 (journal page 03).
* The page is TWO-COLUMN, so pdfplumber interleaves the table rows with
  body-text prose on the same physical lines. We therefore do NOT parse line
  by line. Instead we regex every TABLE CELL anywhere on the page, keyed on
  its distinctive signature:
        <item> <mean> (<sd>) <item-total-corr>
  where item is like '3' or '5R', mean and item-total are 3-decimal numbers,
  and sd is in parentheses. This signature does not occur in the prose.
* The regex yields the 28 item cells in EXACT paper order (verified). The
  Cronbach's-alpha and subscale-label columns are only printed once per block
  and get tangled in the prose, so we DON'T read them; instead we assign each
  item to its subscale by the fixed block sizes below (the CTQ-SF item->
  subscale grouping is a property of the instrument, not of this PDF):
        Emotional abuse   : items 3, 8, 14, 18, 25      (5)
        Physical abuse    : items 9, 11, 12, 15, 17     (5)
        Sexual abuse      : items 20, 21, 23, 24, 27    (5)
        Emotional neglect : items 5R, 7R, 13R, 19R, 28R (5)
        Physical neglect  : items 1, 2R, 4, 6, 26R      (5)
        Validity          : items 10R, 16R, 22R         (3)
  We assert the parsed item numbers match this expected sequence, so if the
  table layout ever shifts the run fails loudly instead of mislabelling.
* One clinical sample (208 adolescents recruited after a suicide attempt):
  every row is sample='patients', subsample='NA', n=208. n is read from the
  methods text ("208 adolescents ...").
* Scale naming: 'CTQ-SF_<subscale>_item_<N>', with the reverse-coding 'R'
  flag RETAINED in the item label (e.g. CTQ-SF_emotional_neglect_item_5R).
* Only Mean and SD are kept (per request). Cronbach's alpha and item-total
  correlation are out of scope.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, NA_MARKER

# --- fixed metadata --------------------------------------------------------
PUBLICATION = "Garcia-Fernandez et al. 2024"
SAMPLE = "patients"
TABLE_PAGE_INDEX = 2  # 0-based pdfplumber page index for journal page 03

# Expected (subscale_suffix, item_label) sequence, in paper row order. This is
# the CTQ-SF instrument grouping; we validate the parsed items against it.
_EXPECTED = [
    ("emotional_abuse",   "3"), ("emotional_abuse",   "8"),
    ("emotional_abuse",   "14"), ("emotional_abuse",  "18"),
    ("emotional_abuse",   "25"),
    ("physical_abuse",    "9"), ("physical_abuse",    "11"),
    ("physical_abuse",    "12"), ("physical_abuse",   "15"),
    ("physical_abuse",    "17"),
    ("sexual_abuse",      "20"), ("sexual_abuse",      "21"),
    ("sexual_abuse",      "23"), ("sexual_abuse",      "24"),
    ("sexual_abuse",      "27"),
    ("emotional_neglect", "5R"), ("emotional_neglect", "7R"),
    ("emotional_neglect", "13R"), ("emotional_neglect", "19R"),
    ("emotional_neglect", "28R"),
    ("physical_neglect",  "1"), ("physical_neglect",  "2R"),
    ("physical_neglect",  "4"), ("physical_neglect",  "6"),
    ("physical_neglect",  "26R"),
    ("validity",          "10R"), ("validity",         "16R"),
    ("validity",          "22R"),
]

# Human-readable subscale labels for the RAW verification view.
_SUBSCALE_LABEL = {
    "emotional_abuse": "Emotional abuse",
    "physical_abuse": "Physical abuse",
    "sexual_abuse": "Sexual abuse",
    "emotional_neglect": "Emotional neglect",
    "physical_neglect": "Physical neglect",
    "validity": "Validity",
}

# Regex for one table cell: <item> <mean> (<sd>) <item-total-corr>.
# Item is 1-2 digits with an optional reverse-coding 'R'. Mean and corr are
# 3-decimal; sd is in parens. Anchored on whitespace/line-start to the left.
_CELL_RE = re.compile(
    r"(?:^|\s)(\d{1,2}R?)\s+(\d\.\d{3})\s*\(([\d.]+)\)\s+\d\.\d{3}"
)


# ---------------------------------------------------------------------------
# 1. Pull the 28 item cells from the PDF, in order.
# ---------------------------------------------------------------------------

def _item_cells(pdf_path):
    """Return [(item_label, mean, sd), ...] for all 28 items, paper order."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        page_text = pdf.pages[TABLE_PAGE_INDEX].extract_text()
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    cells = [(m.group(1), float(m.group(2)), float(m.group(3)))
             for m in _CELL_RE.finditer(page_text)]

    if len(cells) != len(_EXPECTED):
        raise ValueError(
            f"expected {len(_EXPECTED)} item cells, parsed {len(cells)}"
        )
    # Fail loudly if the item sequence doesn't match the known CTQ-SF layout.
    parsed_items = [c[0] for c in cells]
    expected_items = [e[1] for e in _EXPECTED]
    if parsed_items != expected_items:
        raise ValueError(
            "parsed item sequence does not match expected CTQ-SF layout:\n"
            f"  parsed:   {parsed_items}\n  expected: {expected_items}"
        )
    return cells, full_text


def _sample_size(text):
    """Read n from '208 adolescents ...' in the methods text."""
    m = re.search(r"(\d+)\s+adolescents", text)
    if not m:
        raise ValueError("could not find sample size '<n> adolescents'")
    return int(m.group(1))


def _scale_name(subscale_suffix, item_label):
    """'emotional_neglect', '5R' -> 'CTQ-SF_emotional_neglect_item_5R'."""
    return f"CTQ-SF_{subscale_suffix}_item_{item_label}"


# ---------------------------------------------------------------------------
# 2. Verification frames.
# ---------------------------------------------------------------------------

def _build_raw_df(cells):
    """Raw view mirroring the PDF: subscale, item number, packed mean (sd)."""
    rows = []
    for (subscale, item_lbl), (item, mean, sd) in zip(_EXPECTED, cells):
        rows.append({
            "CTQ-SF subscale": _SUBSCALE_LABEL[subscale],
            "Item number": item_lbl,
            "Mean (SD)": f"{mean:.3f} ({sd:.3f})",
        })
    return pd.DataFrame(rows)


def _build_parsed_df(cells, n):
    """Parsed view: scale + mean/sd split into columns."""
    rows = []
    for (subscale, item_lbl), (item, mean, sd) in zip(_EXPECTED, cells):
        rows.append({
            "sample": SAMPLE,
            "subsample": NA_MARKER,
            "n": n,
            "scale": _scale_name(subscale, item_lbl),
            "mean": mean,
            "sd": sd,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Long-format rows (mean + sd per item; no median/min/max in this table).
# ---------------------------------------------------------------------------

def _build_rows(cells, n):
    rows = []
    for (subscale, item_lbl), (item, mean, sd) in zip(_EXPECTED, cells):
        common = dict(publication=PUBLICATION, scale=_scale_name(subscale, item_lbl),
                      sample=SAMPLE, subsample=NA_MARKER, sample_size=n)
        rows.append(make_row(data_type="mean", value=mean, **common))
        rows.append(make_row(data_type="sd",   value=sd,   **common))
    return rows


# ---------------------------------------------------------------------------
# 4. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse Table 1 item-level CTQ-SF Mean (SD) directly from the PDF."""
    cells, full_text = _item_cells(Path(pdf_path))
    n = _sample_size(full_text)

    raw_df = _build_raw_df(cells)
    parsed_df = _build_parsed_df(cells, n)
    rows = _build_rows(cells, n)
    return raw_df, parsed_df, rows, False
