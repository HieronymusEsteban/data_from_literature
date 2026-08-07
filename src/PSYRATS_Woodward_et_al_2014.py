"""
Per-paper extractor: Woodward et al. 2014, PSYRATS multisite study.
Scale of interest: AHS Total and DS Total subscale MEAN scores, per site.

Returns (raw_df, parsed_df, rows, hardcoded_flag) for scaffold.run_extraction.

PAPER-SPECIFIC LAYOUT ASSUMPTIONS
---------------------------------
* Table 1 ("Sample Size, Mean Age, ... as a Function of Site") lives on the
  3rd PDF page (0-indexed page 2). pdfplumber extracts it cleanly as text.
* Each site is one line of whitespace-separated tokens, e.g.
      '4 Bern 54 39.57 13.04 24.46 54 39.57 13.04 8.81 54 39.57 13.04 33.28'
  Token positions (0-indexed), per the paper's own column key
  (cols 3-6 = AHS, 7-10 = DS, 11-14 = AHS+DS):
      0  site id (int 1..12)
      1  location (single word in this table)
      2  AHS (N)
      3  Age            (out of scope)
      4  DI             (out of scope)
      5  AHS Total mean   <-- we want this
      6  DS (N)
      7  Age            (out of scope)
      8  DI             (out of scope)
      9  DS Total mean    <-- we want this
      ...                (AHS+DS block, out of scope)
  DS columns are 'n/a' for sites that did not administer the DS.
* Only the MEAN is reported in this table; no SD / median / range exist, so
  only data_type='mean' rows are produced. All samples are psychosis/
  schizophrenia patients (no healthy controls in this table).
* The trailing 'Ns 711 711 ...' pooled-total line is NOT a site and is skipped.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from scaffold import make_row, NA_MARKER

PUBLICATION = "Woodward et al. 2014"
TABLE1_PAGE = 2          # 0-indexed PDF page holding Table 1
AHS_SCALE = "PSYRATS-AHS_total"
DS_SCALE = "PSYRATS-DS_total"

# A site line starts with an integer id then a non-numeric location token.
_SITE_LINE = re.compile(r"^\s*\d{1,2}\s+[A-Za-z]")


def _table1_lines(pdf_path):
    """Return the raw text lines of the Table-1 page."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        return pdf.pages[TABLE1_PAGE].extract_text().split("\n")


def _is_site_line(line):
    """True for the 12 per-site data rows (id + word location), not 'Ns ...'."""
    return bool(_SITE_LINE.match(line))


def _num_or_na(tok):
    """'24.46' -> 24.46 ; 'n/a' -> None."""
    return None if tok.lower() == "n/a" else float(tok)


def _parse_site_line(line):
    """One Table-1 site line -> dict of the fields we care about.

    Relies on the fixed token positions documented in the module docstring.
    """
    t = line.split()
    return {
        "site": int(t[0]),
        "location": t[1],
        "ahs_n": int(t[2]),
        "ahs_total_mean": _num_or_na(t[5]),
        "ds_n": _num_or_na(t[6]),          # may be 'n/a'
        "ds_total_mean": _num_or_na(t[9]),
    }


def _parse_table1(pdf_path):
    """Return a list of per-site dicts parsed from Table 1."""
    return [_parse_site_line(ln) for ln in _table1_lines(pdf_path) if _is_site_line(ln)]


def _build_raw_df(sites):
    """RAW verification view: mirrors Table 1's AHS/DS Total mean columns."""
    recs = []
    for s in sites:
        recs.append({
            "Site": s["site"],
            "Location": s["location"],
            "AHS (N)": s["ahs_n"],
            "AHS Total (mean)": s["ahs_total_mean"],
            "DS (N)": "n/a" if s["ds_n"] is None else int(s["ds_n"]),
            "DS Total (mean)": "n/a" if s["ds_total_mean"] is None else s["ds_total_mean"],
        })
    return pd.DataFrame(recs)


def _build_parsed_df(sites):
    """PARSED view: one row per site x subscale that has a mean."""
    recs = []
    for s in sites:
        recs.append({
            "scale": AHS_SCALE, "sample": "patients",
            "subsample": f"Site {s['site']} ({s['location']})",
            "n": s["ahs_n"], "mean": s["ahs_total_mean"],
        })
        if s["ds_total_mean"] is not None:
            recs.append({
                "scale": DS_SCALE, "sample": "patients",
                "subsample": f"Site {s['site']} ({s['location']})",
                "n": int(s["ds_n"]), "mean": s["ds_total_mean"],
            })
    return pd.DataFrame(recs)


def _build_rows(sites):
    """Long-format rows via make_row(): one 'mean' row per site x subscale."""
    rows = []
    for s in sites:
        sub = f"Site {s['site']} ({s['location']})"
        rows.append(make_row(
            PUBLICATION, AHS_SCALE, "mean", "patients",
            s["ahs_total_mean"], subsample=sub, sample_size=s["ahs_n"]))
        if s["ds_total_mean"] is not None:
            rows.append(make_row(
                PUBLICATION, DS_SCALE, "mean", "patients",
                s["ds_total_mean"], subsample=sub, sample_size=int(s["ds_n"])))
    return rows


def extract(pdf_path):
    """Scaffold entry point. All values parsed from the PDF; nothing hardcoded."""
    sites = _parse_table1(Path(pdf_path))
    raw_df = _build_raw_df(sites)
    parsed_df = _build_parsed_df(sites)
    rows = _build_rows(sites)
    hardcoded_flag = False
    return raw_df, parsed_df, rows, hardcoded_flag
