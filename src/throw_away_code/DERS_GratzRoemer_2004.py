"""
DERS_GratzRoemer_2004.py
========================
Per-paper extractor for TABLE V of:
    Gratz & Roemer (2004), "Multidimensional Assessment of Emotion Regulation
    and Dysregulation: Development, Factor Structure, and Initial Validation
    of the Difficulties in Emotion Regulation Scale (DERS)",
    J Psychopathol Behav Assess 26(1):41-54.
    Scale of interest: DERS Overall + 6 subscales.

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching scaffold.run_extraction(). Values are parsed DIRECTLY from the PDF
text (pdfplumber), so hardcoded_flag is always False.

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* Table V ("Means and Standard Deviations for DERS Scales Among Women
  (n = 260) and Men (n = 97)") is on PDF page index 8 (journal page 49).
* The page is TWO-COLUMN, so pdfplumber interleaves the table with body-text
  prose. We do NOT parse by line position; instead we regex each table row by
  its distinctive signature:
        <LABEL> <women_mean> <women_sd> <men_mean> <men_sd>
  i.e. the label followed by exactly four dot-decimal numbers. This signature
  does not occur in the surrounding prose.
* The seven row labels, in table order:
        DERS Overall, NONACCEPTANCE, GOALS, IMPULSE, AWARENESS,
        STRATEGIES, CLARITY
  NOTE: pdfplumber renders "DERS Overall" with an internal space; all other
  labels are single tokens. We normalise "DERS Overall" -> "DERSOverall"
  before matching so every label is one token.
* The two group sizes come from the CAPTION, not a table cell. pdfplumber
  renders "n = 260" as "nD260" (the '=' becomes 'D'), so the n-regex allows
  any single char between 'n' and the digits: 'Women(n.260)and Men(n.97)'.
* Column -> sex mapping: first numeric pair = Women, second pair = Men.
* Schema mapping:
    - scale     : 'DERS_total' for "DERS Overall"; otherwise
                  'DERS_<label lowercased>' (e.g. DERS_nonacceptance).
    - sample    : 'healthy_controls' (undergraduate students; NOT a clinical
                  sample, despite the paper's clinical themes).
    - subsample : 'women' or 'men'.
    - sample_size: 260 (women) / 97 (men), from the caption.
  Only Mean and SD exist in this table (no median/min/max).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, NA_MARKER

# --- fixed metadata --------------------------------------------------------
PUBLICATION = "Gratz & Roemer 2004"
SAMPLE = "healthy_controls"
TABLE_PAGE_INDEX = 8  # 0-based pdfplumber page index for journal page 49

# Printed row label (normalised, single-token) -> schema scale name, in order.
_SCALES = [
    ("DERSOverall",    "DERS_total"),
    ("NONACCEPTANCE",  "DERS_nonacceptance"),
    ("GOALS",          "DERS_goals"),
    ("IMPULSE",        "DERS_impulse"),
    ("AWARENESS",      "DERS_awareness"),
    ("STRATEGIES",     "DERS_strategies"),
    ("CLARITY",        "DERS_clarity"),
]

# Human-readable labels for the RAW verification view (as printed).
_RAW_LABEL = {
    "DERSOverall": "DERS Overall",
    "NONACCEPTANCE": "NONACCEPTANCE",
    "GOALS": "GOALS",
    "IMPULSE": "IMPULSE",
    "AWARENESS": "AWARENESS",
    "STRATEGIES": "STRATEGIES",
    "CLARITY": "CLARITY",
}

# One table row: label + four dot-decimal numbers (women mean/sd, men mean/sd).
_ROW_RE = re.compile(
    r"^(DERSOverall|NONACCEPTANCE|GOALS|IMPULSE|AWARENESS|STRATEGIES|CLARITY)"
    r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
)


# ---------------------------------------------------------------------------
# 1. Read the page text and pull caption n's + the seven data rows.
# ---------------------------------------------------------------------------

def _page_text(pdf_path):
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return pdf.pages[TABLE_PAGE_INDEX].extract_text() or ""


def _caption_ns(text):
    """Return (women_n, men_n) from 'Women(n=260) and Men(n=97)'.

    pdfplumber may render '=' as 'D' and drop spaces, so we strip spaces and
    allow any single character between 'n' and the digits.
    """
    compact = text.replace(" ", "")
    m = re.search(r"Women\(n.?(\d+)\)andMen\(n.?(\d+)\)", compact)
    if not m:
        raise ValueError("could not find 'Women(n=...) and Men(n=...)' caption")
    return int(m.group(1)), int(m.group(2))


def _data_rows(text):
    """Return {scale_name: (w_mean, w_sd, m_mean, m_sd)} for all 7 rows."""
    scale_of = dict(_SCALES)
    found = {}
    for line in text.splitlines():
        # Normalise the two-token "DERS Overall" label to one token.
        s = line.strip().replace("DERS Overall", "DERSOverall")
        m = _ROW_RE.match(s)
        if m:
            label = m.group(1)
            found[scale_of[label]] = (float(m.group(2)), float(m.group(3)),
                                      float(m.group(4)), float(m.group(5)))
    missing = {sc for _, sc in _SCALES} - set(found)
    if missing:
        raise ValueError(f"Table V rows not found: {sorted(missing)}")
    return found


# ---------------------------------------------------------------------------
# 2. Build a flat record list shared by all three outputs.
# ---------------------------------------------------------------------------

def _records(pdf_path):
    """Return list of dicts: scale, subsample, n, mean, sd (women then men)."""
    text = _page_text(pdf_path)
    w_n, m_n = _caption_ns(text)
    data = _data_rows(text)

    out = []
    # Women column first, then men, each in canonical scale order.
    for sex, n, idx in (("women", w_n, 0), ("men", m_n, 2)):
        for _, scale in _SCALES:
            w_mean, w_sd, m_mean, m_sd = data[scale]
            vals = (w_mean, w_sd, m_mean, m_sd)
            mean, sd = vals[idx], vals[idx + 1]
            out.append({"scale": scale, "subsample": sex, "n": n,
                        "mean": mean, "sd": sd})
    return out, data, (w_n, m_n)


# ---------------------------------------------------------------------------
# 3. Verification frames.
# ---------------------------------------------------------------------------

def _build_raw_df(data):
    """Raw view mirroring the PDF: label + women mean/sd + men mean/sd."""
    rows = []
    for label, scale in _SCALES:
        w_mean, w_sd, m_mean, m_sd = data[scale]
        rows.append({
            "Scale": _RAW_LABEL[label],
            "Women Mean": w_mean, "Women SD": w_sd,
            "Men Mean": m_mean, "Men SD": m_sd,
        })
    return pd.DataFrame(rows)


def _build_parsed_df(records):
    """Parsed view: scale/subsample/sample/n/mean/sd."""
    return pd.DataFrame([{
        "scale": r["scale"], "subsample": r["subsample"], "sample": SAMPLE,
        "n": r["n"], "mean": r["mean"], "sd": r["sd"],
    } for r in records])


# ---------------------------------------------------------------------------
# 4. Long-format rows (mean + sd per scale per sex).
# ---------------------------------------------------------------------------

def _build_rows(records):
    rows = []
    for r in records:
        common = dict(publication=PUBLICATION, scale=r["scale"],
                      sample=SAMPLE, subsample=r["subsample"],
                      sample_size=r["n"])
        rows.append(make_row(data_type="mean", value=r["mean"], **common))
        rows.append(make_row(data_type="sd",   value=r["sd"],   **common))
    return rows


# ---------------------------------------------------------------------------
# 5. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse Table V (DERS means/SDs by sex) directly from the PDF."""
    records, data, _ = _records(Path(pdf_path))
    raw_df = _build_raw_df(data)
    parsed_df = _build_parsed_df(records)
    rows = _build_rows(records)
    return raw_df, parsed_df, rows, False
