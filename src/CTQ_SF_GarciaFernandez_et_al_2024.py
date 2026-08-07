"""
CTQ_SF_GarciaFernandez_et_al_2024.py
====================================
Per-paper extractor for:
    García-Fernández et al. (2024), "Validation of the Spanish Childhood
    Trauma Questionnaire-Short Form in adolescents with suicide attempts",
    Front. Psychol. 15:1378486.
    Scale of interest: CTQ-SF (5 subscales).

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching scaffold.run_extraction(). Values are parsed DIRECTLY from the PDF
text (pdfplumber), so hardcoded_flag is always False.

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* Table 3 ("Descriptive analysis of CTQ-SF subscale scores") is on PDF page
  index 5 (journal page 06).
* pdfplumber renders each subscale row as ONE clean line:
      <subscale label> <mean> (<sd>) <min>-<max> <skew> (<se>) ...
  e.g.  'Emotional abuse 15.26 (5.65) 5–25 −0.110 (0.169) ...'
  We only want the first three data fields: Mean, SD, and the Range
  (min-max). Everything after the range (skewness, kurtosis, normality,
  floor/ceiling) is ignored.
* The subscale LABEL is one or two words and is matched explicitly from a
  known list (it always precedes the first numeric token). The five labels,
  in paper row order:
      Emotional abuse, Physical abuse, Sexual abuse,
      Emotional neglect, Physical neglect
* The range uses an EN-DASH or hyphen between min and max ('5–25' / '5-19');
  both are handled.
* One clinical sample (208 adolescents recruited from psychiatric emergency
  departments after a suicide attempt), so every row is sample='patients',
  subsample='NA', n=208. n is read from the methods text ("208 adolescents")
  rather than from the table (the table has no n column).
* The subscale name goes into the SCALE column as 'CTQ-SF_<subscale>'
  (e.g. 'CTQ-SF_emotional_abuse'), parallel to the per-variable scale naming
  used for the Spitzer paper. subsample stays 'NA'.
* Min/Max are OBSERVED values (confirmed by the floor effects in the text and
  the physical-neglect max of 19 < theoretical 25), stored as
  minimum/maximum.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, NA_MARKER

# --- fixed metadata --------------------------------------------------------
PUBLICATION = "Garcia-Fernandez et al. 2024"
SAMPLE = "patients"
TABLE_PAGE_INDEX = 5  # 0-based pdfplumber page index for journal page 06

# Subscale labels exactly as printed, in paper row order, mapped to the
# scale-name suffix used in the output.
_SUBSCALES = [
    ("Emotional abuse",   "CTQ-SF_emotional_abuse"),
    ("Physical abuse",    "CTQ-SF_physical_abuse"),
    ("Sexual abuse",      "CTQ-SF_sexual_abuse"),
    ("Emotional neglect", "CTQ-SF_emotional_neglect"),
    ("Physical neglect",  "CTQ-SF_physical_neglect"),
]


# ---------------------------------------------------------------------------
# 1. Pull the sample size from the methods text.
# ---------------------------------------------------------------------------

def _sample_size(text):
    """Read n from a phrase like '208 adolescents with suicide attempts'."""
    m = re.search(r"(\d+)\s+adolescents with suicide attempts", text)
    if not m:
        raise ValueError("could not find sample size '<n> adolescents ...'")
    return int(m.group(1))


# ---------------------------------------------------------------------------
# 2. Parse one Table-3 subscale row into its three wanted fields.
# ---------------------------------------------------------------------------

def _parse_row(text, label):
    """Return (mean, sd, minimum, maximum) for one subscale row.

    Matches: '<label> <mean> (<sd>) <min><dash><max>' at the start of the
    line, where <dash> is an en-dash or hyphen. Numbers are plain dot
    decimals in this PDF.
    """
    # \u2013 = en-dash; also allow plain hyphen.
    pat = re.compile(
        rf"^{re.escape(label)}\s+"
        r"([\d.]+)\s*\(([\d.]+)\)\s+"          # mean (sd)
        r"(\d+)\s*[\u2013-]\s*(\d+)",           # min - max
        re.MULTILINE,
    )
    m = pat.search(text)
    if not m:
        raise ValueError(f"Table 3 row {label!r} not found / unparseable")
    mean = float(m.group(1))
    sd = float(m.group(2))
    minimum = float(m.group(3))
    maximum = float(m.group(4))
    return mean, sd, minimum, maximum


def _parsed_records(pdf_path):
    """Return a list of dicts, one per subscale, with all parsed values."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        page_text = pdf.pages[TABLE_PAGE_INDEX].extract_text()
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    n = _sample_size(full_text)

    records = []
    for label, scale in _SUBSCALES:
        mean, sd, mn, mx = _parse_row(page_text, label)
        records.append({
            "label": label, "scale": scale, "n": n,
            "mean": mean, "sd": sd, "minimum": mn, "maximum": mx,
        })
    return records


# ---------------------------------------------------------------------------
# 3. Verification frames.
# ---------------------------------------------------------------------------

def _build_raw_df(records):
    """Raw view mirroring the PDF: label, packed 'mean (sd)', and range."""
    rows = []
    for r in records:
        # Reassemble the packed cells exactly as they appear in the table.
        mean_sd = f"{r['mean']:.2f} ({r['sd']:.2f})"
        rng = f"{int(r['minimum'])}-{int(r['maximum'])}"
        rows.append({
            "CTQ-SF subscale": r["label"],
            "Mean (SD)": mean_sd,
            "Range": rng,
        })
    return pd.DataFrame(rows)


def _build_parsed_df(records):
    """Parsed view: scale + mean/sd/min/max split into columns."""
    rows = []
    for r in records:
        rows.append({
            "sample": SAMPLE,
            "subsample": NA_MARKER,
            "n": r["n"],
            "scale": r["scale"],
            "mean": r["mean"],
            "sd": r["sd"],
            "minimum": r["minimum"],
            "maximum": r["maximum"],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. Long-format rows (mean, sd, minimum, maximum per subscale).
# ---------------------------------------------------------------------------

def _build_rows(records):
    rows = []
    for r in records:
        common = dict(publication=PUBLICATION, scale=r["scale"],
                      sample=SAMPLE, subsample=NA_MARKER,
                      sample_size=r["n"])
        rows.append(make_row(data_type="mean",    value=r["mean"],    **common))
        rows.append(make_row(data_type="sd",      value=r["sd"],      **common))
        rows.append(make_row(data_type="minimum", value=r["minimum"], **common))
        rows.append(make_row(data_type="maximum", value=r["maximum"], **common))
    return rows


# ---------------------------------------------------------------------------
# 5. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse Table 3 CTQ-SF subscale stats directly from the PDF."""
    records = _parsed_records(Path(pdf_path))
    raw_df = _build_raw_df(records)
    parsed_df = _build_parsed_df(records)
    rows = _build_rows(records)
    return raw_df, parsed_df, rows, False
