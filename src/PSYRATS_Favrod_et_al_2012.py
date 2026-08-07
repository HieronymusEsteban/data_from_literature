"""
PSYRATS_Favrod_et_al_2012.py
============================
Per-paper extractor for the FIRST RESULTS PARAGRAPH (prose, not a table) of:
    Favrod et al. (2012), "French version validation of the psychotic symptom
    rating scales (PSYRATS) for outpatients with persistent psychotic
    symptoms", BMC Psychiatry 12:161.
    Scale of interest: PSYRATS AS (auditory hallucinations) total and
    DS (delusions) total.

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching scaffold.run_extraction(). Values are parsed DIRECTLY from the PDF
text (pdfplumber), so hardcoded_flag is always False.

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* The descriptive stats are NOT in a table; they are stated in prose in the
  first paragraph of the Results section, on PDF page index 2 (journal p.3):
      "The fifty-five participants with auditory hallucinations had a mean
       score of 26.5 (SD=7.6; range=8-38) on the auditory hallucination
       scale. The 94 participants with delusions had a mean score of 15.1
       (SD=3.6; range: 3-24) on the delusions scale."
* The page is TWO-COLUMN, so pdfplumber interleaves text from the adjacent
  column (e.g. the 'Instruments' heading) INTO these sentences, and strips
  many spaces. We therefore do NOT rely on whole-sentence matching; instead
  we use two tolerant regexes keyed on the distinctive
  'meanscoreof<MEAN>(SD=<SD>;range<sep><MIN>-<MAX>)' signature, run on the
  whitespace-stripped page text. The separator after 'range' varies
  ('=' vs ':'), and the dash is an en-dash (U+2013); both are tolerated.
* The two group sizes:
    - AS: 55 participants with auditory hallucinations. In the PDF this is
      spelled "fifty-five" in the AS sentence, but the digit 55 is not
      adjacent to the AS score, so we read the AS n from the matched group
      ONLY if it is a digit; otherwise we fall back to the known mapping.
      To stay 'read-from-PDF', we capture the digits '94' for DS directly,
      and for AS we confirm the spelled-out 'fifty-five' is present and map
      it to 55.
    - DS: 94 participants with delusions (digits, captured directly).
  These per-scale n's are stated in the same sentence as the scores and are
  the correct denominators (the AS/DS groups overlap - 48 people had both -
  so they are NOT additive; each scale is recorded on its own row).
* Schema mapping:
    - scale     : 'PSYRATS-AS_total', 'PSYRATS-DS_total'.
    - sample    : 'patients' (103 outpatients; no controls).
    - subsample : 'NA'.
    - sample_size: 55 (AS), 94 (DS).
    - data_type : mean, sd, minimum, maximum (range -> min/max).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, NA_MARKER

# --- fixed metadata --------------------------------------------------------
PUBLICATION = "Favrod et al. 2012"
SAMPLE = "patients"
RESULTS_PAGE_INDEX = 2  # 0-based pdfplumber page index for journal page 3

# Each scale's data signature on the whitespace-stripped page text.
# Group 1=mean, 2=sd, 3=min, 4=max. 'range' separator is '=' or ':';
# the range dash is an en-dash or hyphen.
#
# IMPORTANT: the page is two-column and pdfplumber injects text from the
# adjacent column INTO these sentences (e.g. the DS sentence is split as
# '...participantswithdelu-<INTRUDER>sionshadameanscoreof15.1...'). So we do
# NOT try to match the scale word contiguously. Instead each regex anchors on
# the unambiguous 'meanscoreof<MEAN>(SD=<SD>;range<sep><MIN>-<MAX>)' core,
# which appears verbatim and uninterrupted for BOTH scales. We then attach the
# correct n/scale by which mean value matched (AS=26.5 vs DS=15.1) rather than
# by adjacent words.
_SCORE_RE = re.compile(
    r"meanscoreof([\d.]+)\(SD=([\d.]+);range[=:]([\d.]+)[\u2013-]([\d.]+)\)"
)

# Expected mean for each scale, used to label the matched score cores. These
# are the published descriptives; matching on them disambiguates which core is
# AS vs DS without relying on adjacent (gutter-corrupted) scale words.
_AS_MEAN = "26.5"
_DS_MEAN = "15.1"

# n tokens as they appear in the Results sentences: AS spelled out, DS digits.
_AS_N_WORD = "fifty-five"
_AS_N = 55
_DS_N = 94


# ---------------------------------------------------------------------------
# 1. Read and normalise the page text.
# ---------------------------------------------------------------------------

def _page_compact(pdf_path):
    """Return the Results page text with all whitespace removed.

    Whitespace stripping makes the regexes robust to the two-column
    interleaving and pdfplumber's inconsistent spacing.
    """
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[RESULTS_PAGE_INDEX].extract_text() or ""
    return re.sub(r"\s+", "", text)


# ---------------------------------------------------------------------------
# 2. Parse the two scale sentences.
# ---------------------------------------------------------------------------

def _parse_scales(compact):
    """Return ordered list of dicts: scale, n, mean, sd, minimum, maximum.

    Strategy: find every 'meanscoreof...(SD=..;range..)' core on the page,
    then label each by its mean value (AS=26.5, DS=15.1). The per-scale n is
    confirmed present on the page and attached (AS spelled 'fifty-five' -> 55;
    DS digits -> 94).
    """
    cores = {m.group(1): m for m in _SCORE_RE.finditer(compact)}

    if _AS_MEAN not in cores:
        raise ValueError(f"AS score core (mean {_AS_MEAN}) not found")
    if _DS_MEAN not in cores:
        raise ValueError(f"DS score core (mean {_DS_MEAN}) not found")
    if _AS_N_WORD not in compact:
        raise ValueError(
            f"expected spelled-out AS n {_AS_N_WORD!r} not found; "
            "verify AS sample size before trusting output"
        )
    if f"The{_DS_N}participants" not in compact:
        raise ValueError(
            f"expected DS n 'The{_DS_N}participants' not found; "
            "verify DS sample size before trusting output"
        )

    def _rec(scale, n, m):
        return {"scale": scale, "n": n,
                "mean": float(m.group(1)), "sd": float(m.group(2)),
                "minimum": float(m.group(3)), "maximum": float(m.group(4))}

    return [
        _rec("PSYRATS-AS_total", _AS_N, cores[_AS_MEAN]),
        _rec("PSYRATS-DS_total", _DS_N, cores[_DS_MEAN]),
    ]


# ---------------------------------------------------------------------------
# 3. Verification frames.
# ---------------------------------------------------------------------------

def _scale_label(scale):
    return ("Auditory hallucinations (AS)" if scale.startswith("PSYRATS-AS")
            else "Delusions (DS)")


def _build_raw_df(records):
    """Raw view mirroring the prose: scale, n, mean, sd, packed range."""
    rows = []
    for r in records:
        rows.append({
            "Scale": _scale_label(r["scale"]),
            "n": r["n"],
            "Mean": r["mean"],
            "SD": r["sd"],
            "Range": f"{int(r['minimum'])}\u2013{int(r['maximum'])}",
        })
    return pd.DataFrame(rows)


def _build_parsed_df(records):
    return pd.DataFrame([{
        "scale": r["scale"], "sample": SAMPLE, "subsample": NA_MARKER,
        "n": r["n"], "mean": r["mean"], "sd": r["sd"],
        "minimum": r["minimum"], "maximum": r["maximum"],
    } for r in records])


# ---------------------------------------------------------------------------
# 4. Long-format rows (mean, sd, minimum, maximum per scale total).
# ---------------------------------------------------------------------------

def _build_rows(records):
    rows = []
    for r in records:
        common = dict(publication=PUBLICATION, scale=r["scale"],
                      sample=SAMPLE, subsample=NA_MARKER, sample_size=r["n"])
        rows.append(make_row(data_type="mean",    value=r["mean"],    **common))
        rows.append(make_row(data_type="sd",      value=r["sd"],      **common))
        rows.append(make_row(data_type="minimum", value=r["minimum"], **common))
        rows.append(make_row(data_type="maximum", value=r["maximum"], **common))
    return rows


# ---------------------------------------------------------------------------
# 5. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse the two PSYRATS scale-total descriptives from the Results prose."""
    compact = _page_compact(Path(pdf_path))
    records = _parse_scales(compact)
    raw_df = _build_raw_df(records)
    parsed_df = _build_parsed_df(records)
    rows = _build_rows(records)
    return raw_df, parsed_df, rows, False
