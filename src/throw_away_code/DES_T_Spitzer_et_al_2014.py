"""
Spitzer_et_al_2014.py
=====================
Per-paper extractor for:
    Spitzer, Freyberger, Brähler, Beutel & Stieglitz (2015),
    "Teststatistische Überprüfung der Dissociative Experiences Scale-Taxon
    (DES-T)", Psychother Psych Med 65:134-139.
    Scale of interest: DES-T (8 items + total scale).

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag).

============================================================================
!!! HARDCODED VALUES — hardcoded_flag is True !!!
============================================================================
Unlike the other papers in this project, the Table 2 values CANNOT be parsed
from the PDF:
  * The table is rendered as rotated vector graphics, NOT live text. Every
    numeric cell (M, SD, Min-Max, etc.) is ABSENT from the PDF text layer
    (pdfplumber.extract_words() returns 0 hits for '2,18', '8,39', '6,59',
    '72,5', ...). There are also no embedded raster images to pull.
  * OCR of the rasterised, 270°-rotated page recovers most cells but mangles
    several in error-invisible ways (e.g. '8,39'->'$39', '9,48'->'948',
    '47,1'->'471'). OCR is therefore used only as a cross-check, not as the
    source of record.

The values below were read by a human DIRECTLY off the PDF table and verified
against the eyeball view. Because they were typed by hand rather than parsed,
hardcoded_flag is set True so scaffold.write_consolidated() emits its loud
warning and writes the *.HARDCODED_WARNING.txt marker. VERIFY MANUALLY before
downstream use.

------------------------------------------------------------------------
Layout / schema decisions (so you can debug later)
------------------------------------------------------------------------
* Table 2 ("Teststatistische Kennwerte der 8 Items der DES-Taxon"), page 137
  of the journal (PDF page index 3).
* Source uses German comma-decimals; stored here as Python floats (dot).
* One general-population sample ("Allgemeinbevölkerungsstichprobe", n=2359),
  so every row is sample='healthy_controls', subsample='NA'.
* The item index is part of the SCALE NAME, not a subsample:
      rows 1..8        -> scale 'DES-T_item_1' .. 'DES-T_item_8'
      row 'T' (total)  -> scale 'DES-T'   (Gesamtwert is implicit)
* Columns kept (per request): mean (M), sd (SD), minimum & maximum (Min-Max).
  Schiefe / Kurtosis / KS-test columns are intentionally dropped (not in the
  schema vocabulary).
* sample_size: uniform 2359 for all rows. Per-item missing values are only
  2-7 people (<0.3%), not material for weighted aggregation.
"""

from __future__ import annotations

import pandas as pd

from scaffold import make_row, NA_MARKER

# --- fixed metadata --------------------------------------------------------
PUBLICATION = "Spitzer et al. 2014"
SAMPLE = "healthy_controls"
SAMPLE_SIZE = 2359
HARDCODED = True  # values typed by hand, NOT parsed from the PDF (see header)

# --- the verified table values --------------------------------------------
# Each tuple: (scale_name, mean, sd, minimum, maximum)
# Order mirrors Table 2 top-to-bottom: items 1-8, then the total scale.
_TABLE = [
    ("DES-T_item_1", 2.18, 8.39, 0.0, 90.0),
    ("DES-T_item_2", 2.19, 8.52, 0.0, 100.0),
    ("DES-T_item_3", 2.83, 9.48, 0.0, 100.0),
    ("DES-T_item_4", 1.89, 8.28, 0.0, 100.0),
    ("DES-T_item_5", 1.75, 7.33, 0.0, 90.0),
    ("DES-T_item_6", 2.36, 8.39, 0.0, 100.0),
    ("DES-T_item_7", 1.56, 6.96, 0.0, 70.0),
    ("DES-T_item_8", 2.32, 8.56, 0.0, 100.0),
    ("DES-T",        2.14, 6.59, 0.0, 72.5),  # Gesamtwert (total)
]

# Human-readable row labels for the RAW verification view (as printed: "Nr.").
_RAW_LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "T (Gesamtskala)"]

# German comma-decimal strings for the RAW view, to mirror the PDF exactly.
_RAW_CELLS = [
    ("2,18", "8,39", "0-90"),
    ("2,19", "8,52", "0-100"),
    ("2,83", "9,48", "0-100"),
    ("1,89", "8,28", "0-100"),
    ("1,75", "7,33", "0-90"),
    ("2,36", "8,39", "0-100"),
    ("1,56", "6,96", "0-70"),
    ("2,32", "8,56", "0-100"),
    ("2,14", "6,59", "0-72,5"),
]


# ---------------------------------------------------------------------------
# 1. Verification frames.
# ---------------------------------------------------------------------------

def _build_raw_df():
    """Raw view mirroring the PDF: Nr. + packed German comma-decimal cells."""
    rows = []
    for label, (m, sd, rng) in zip(_RAW_LABELS, _RAW_CELLS):
        rows.append({"Nr.": label, "M": m, "SD": sd, "Min - Max": rng})
    return pd.DataFrame(rows)


def _build_parsed_df():
    """Parsed view: scale + mean/sd/min/max split into columns."""
    rows = []
    for scale, mean, sd, mn, mx in _TABLE:
        rows.append({
            "scale": scale,
            "sample": SAMPLE,
            "subsample": NA_MARKER,
            "n": SAMPLE_SIZE,
            "mean": mean,
            "sd": sd,
            "minimum": mn,
            "maximum": mx,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. Long-format rows (mean, sd, minimum, maximum per scale variable).
# ---------------------------------------------------------------------------

def _build_rows():
    rows = []
    for scale, mean, sd, mn, mx in _TABLE:
        common = dict(publication=PUBLICATION, scale=scale,
                      sample=SAMPLE, subsample=NA_MARKER,
                      sample_size=SAMPLE_SIZE)
        rows.append(make_row(data_type="mean",    value=mean, **common))
        rows.append(make_row(data_type="sd",      value=sd,   **common))
        rows.append(make_row(data_type="minimum", value=mn,   **common))
        rows.append(make_row(data_type="maximum", value=mx,   **common))
    return rows


# ---------------------------------------------------------------------------
# 3. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Return the four-tuple. Values are HARDCODED (see module header)."""
    raw_df = _build_raw_df()
    parsed_df = _build_parsed_df()
    rows = _build_rows()
    return raw_df, parsed_df, rows, HARDCODED
