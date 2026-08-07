"""
CTQ_SF_Hagborg_et_al_2022.py
============================
Per-paper extractor for TABLE 1 of:
    Hagborg, Kalin & Gerdner (2022), "The Childhood Trauma Questionnaire-
    Short Form (CTQ-SF) used with adolescents - methodological report from
    clinical and community samples", J Child Adolesc Trauma 15:1199-1213.
    Scale of interest: CTQ total + 7 subscales (EN, PN, EA, PA, SA, M/D, IU).

Exposes extract(pdf_path) -> (raw_df, parsed_df, rows, hardcoded_flag),
matching scaffold.run_extraction(). Values are parsed DIRECTLY from the PDF
text (pdfplumber), so hardcoded_flag is always False.

------------------------------------------------------------------------
Paper-specific layout assumptions (so you can debug later)
------------------------------------------------------------------------
* Table 1 is on PDF page index 5 (journal page 1204).
* The table is a SAMPLE x WAVE x SEX grid, stacked as two blocks (Boys then
  Girls). Each block has its own 'n =' row, then 8 scale rows in this order:
        CTQ total, EN, PN, EA, PA, SA, M/D, IU
  and these FIVE data columns, left to right:
        community Wave2, Wave3, Wave4, Wave5, clinical
* pdfplumber returns each data row as ONE clean line, e.g.
        'EN 7.7 (3.21) 7.3 (3.32) 7.4 (3.42) 7.5 (3.45) 9.6 (4.69)'
  We regex every 'mean (sd)' cell on the line. BUT some rows have STRUCTURAL
  GAPS, so the number of cells is < 5 and we must know WHICH columns are
  present:
    - Wave 2 only used 13 items (subscales EN, EA + M/D), so for
      CTQ total / PN / PA / SA the Wave-2 cell is MISSING (gap at LEFT).
    - IU could not be computed for the clinical sample (dichotomised M/D),
      so the clinical cell is MISSING (gap at RIGHT). The PDF prints '-'.
  Because two different rows can both have 4 cells but different gaps
  (e.g. CTQ total vs IU), we CANNOT infer the mapping from the cell count.
  Instead, _COLUMNS_PRESENT below states explicitly which columns each scale
  row fills; we zip the parsed cells onto exactly those columns and assert
  the counts match (fails loudly if the layout ever changes).
* The two 'n =' rows give the per-column group sizes (one set per sex).
* Schema mapping:
    - scale     : CTQ_total, CTQ_EN, CTQ_PN, CTQ_EA, CTQ_PA, CTQ_SA,
                  CTQ_MD, CTQ_IU   (the printed 'M/D' -> 'CTQ_MD')
    - sample    : community columns -> 'healthy_controls';
                  clinical column  -> 'patients'
    - subsample : 'community_<wave>_<sex>'  e.g. community_W3_boys
                  'clinical_<sex>'          e.g. clinical_boys
    - sample_size: the per-column n for that sex.
  Missing cells produce NO long-format row (long format simply omits them).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scaffold import make_row, NA_MARKER

# --- fixed metadata --------------------------------------------------------
PUBLICATION = "Hagborg et al. 2022"
TABLE_PAGE_INDEX = 5  # 0-based pdfplumber page index for journal page 1204

# The five data columns, in print order (left to right).
_COLUMNS = ["W2", "W3", "W4", "W5", "clinical"]

# Scale rows in print order. Maps the printed row label -> schema scale name.
_SCALES = [
    ("CTQ total", "CTQ_total"),
    ("EN", "CTQ_EN"),
    ("PN", "CTQ_PN"),
    ("EA", "CTQ_EA"),
    ("PA", "CTQ_PA"),
    ("SA", "CTQ_SA"),
    ("M/D", "CTQ_MD"),
    ("IU", "CTQ_IU"),
]

# Which columns each scale row actually fills (structural gaps encoded here).
#   - Wave 2 only had EN, EA, M/D, IU -> the other four lack the W2 cell.
#   - IU lacks the clinical cell.
_COLUMNS_PRESENT = {
    "CTQ_total": ["W3", "W4", "W5", "clinical"],          # no W2
    "CTQ_EN":    ["W2", "W3", "W4", "W5", "clinical"],    # full
    "CTQ_PN":    ["W3", "W4", "W5", "clinical"],          # no W2
    "CTQ_EA":    ["W2", "W3", "W4", "W5", "clinical"],    # full
    "CTQ_PA":    ["W3", "W4", "W5", "clinical"],          # no W2
    "CTQ_SA":    ["W3", "W4", "W5", "clinical"],          # no W2
    "CTQ_MD":    ["W2", "W3", "W4", "W5", "clinical"],    # full
    "CTQ_IU":    ["W2", "W3", "W4", "W5"],                # no clinical
}

_CELL_RE = re.compile(r"(\d+\.\d+)\s*\(([\d.]+)\)")
_ROW_RE = re.compile(r"^(CTQ total|EN|PN|EA|PA|SA|M/D|IU)(?:\s*\(a\))?\s+")
_N_RE = re.compile(r"^n\s*=\s*([\d\s]+)$")


# ---------------------------------------------------------------------------
# 1. Read the raw table lines (two n-rows + two blocks of 8 scale rows).
# ---------------------------------------------------------------------------

def _table_text(pdf_path):
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return pdf.pages[TABLE_PAGE_INDEX].extract_text() or ""


def _parse_n_rows(text):
    """Return [boys_n_dict, girls_n_dict], each mapping column -> int.

    There are two 'n =' lines; the first is Boys, the second Girls. Each lists
    five integers in column order W2 W3 W4 W5 clinical.
    """
    n_lists = []
    for line in text.splitlines():
        m = _N_RE.match(line.strip())
        if m:
            nums = [int(x) for x in m.group(1).split()]
            if len(nums) == len(_COLUMNS):
                n_lists.append(dict(zip(_COLUMNS, nums)))
    if len(n_lists) != 2:
        raise ValueError(f"expected 2 'n =' rows, found {len(n_lists)}")
    return n_lists  # [boys, girls]


def _parse_scale_rows(text):
    """Return [boys_rows, girls_rows].

    Each is an ordered list of (scale_name, {column: (mean, sd)}). The first 8
    scale rows encountered are Boys, the next 8 are Girls.
    """
    collected = []
    for line in text.splitlines():
        s = line.strip()
        m = _ROW_RE.match(s)
        if not m:
            continue
        label = m.group(1)
        scale = dict(_SCALES)[label]
        cells = [(float(a), float(b)) for a, b in _CELL_RE.findall(s)]

        present = _COLUMNS_PRESENT[scale]
        if len(cells) != len(present):
            raise ValueError(
                f"{scale}: expected {len(present)} cells {present}, "
                f"got {len(cells)} -> {cells}"
            )
        collected.append((scale, dict(zip(present, cells))))

    if len(collected) != 2 * len(_SCALES):
        raise ValueError(
            f"expected {2*len(_SCALES)} scale rows, got {len(collected)}"
        )
    return collected[:len(_SCALES)], collected[len(_SCALES):]


# ---------------------------------------------------------------------------
# 2. Assemble a flat record list shared by all three outputs.
# ---------------------------------------------------------------------------

def _records(pdf_path):
    """Return list of dicts: scale, sample, subsample, n, mean, sd.

    Walks Boys then Girls, each scale, each present column, in table order.
    """
    text = _table_text(pdf_path)
    (boys_n, girls_n) = _parse_n_rows(text)
    boys_rows, girls_rows = _parse_scale_rows(text)

    out = []
    for sex, rows, n_map in (("boys", boys_rows, boys_n),
                             ("girls", girls_rows, girls_n)):
        for scale, col_cells in rows:
            for col in _COLUMNS:               # keep canonical column order
                if col not in col_cells:
                    continue
                mean, sd = col_cells[col]
                if col == "clinical":
                    sample, subsample = "patients", f"clinical_{sex}"
                else:
                    sample, subsample = "healthy_controls", f"community_{col}_{sex}"
                out.append({
                    "scale": scale, "sample": sample, "subsample": subsample,
                    "n": n_map[col], "mean": mean, "sd": sd, "sex": sex,
                    "col": col,
                })
    return out


# ---------------------------------------------------------------------------
# 3. Verification frames.
# ---------------------------------------------------------------------------

def _fmt_cell(rec_map, col):
    """'mean (sd)' for the cell at `col`, or NA_MARKER if absent."""
    if col in rec_map:
        mean, sd = rec_map[col]
        return f"{mean} ({sd})"
    return NA_MARKER


def _build_raw_df(pdf_path):
    """Raw grid mirroring the PDF: one row per (block, scale), NA in gaps."""
    text = _table_text(pdf_path)
    boys_n, girls_n = _parse_n_rows(text)
    boys_rows, girls_rows = _parse_scale_rows(text)

    out = []
    for sex_label, rows, n_map in (("Boys", boys_rows, boys_n),
                                   ("Girls", girls_rows, girls_n)):
        # n-row first, mirroring the PDF.
        out.append({
            "Block": f"{sex_label} n", "Scale": NA_MARKER,
            "Wave2": n_map["W2"], "Wave3": n_map["W3"], "Wave4": n_map["W4"],
            "Wave5": n_map["W5"], "Clinical": n_map["clinical"],
        })
        printed = {sc: lbl for lbl, sc in _SCALES}
        for scale, col_cells in rows:
            out.append({
                "Block": sex_label,
                "Scale": printed[scale],
                "Wave2": _fmt_cell(col_cells, "W2"),
                "Wave3": _fmt_cell(col_cells, "W3"),
                "Wave4": _fmt_cell(col_cells, "W4"),
                "Wave5": _fmt_cell(col_cells, "W5"),
                "Clinical": _fmt_cell(col_cells, "clinical"),
            })
    return pd.DataFrame(out)


def _build_parsed_df(records):
    """Parsed long view: scale/subsample/sample/n/mean/sd, gaps omitted."""
    return pd.DataFrame([{
        "scale": r["scale"], "subsample": r["subsample"],
        "sample": r["sample"], "n": r["n"], "mean": r["mean"], "sd": r["sd"],
    } for r in records])


# ---------------------------------------------------------------------------
# 4. Long-format rows (mean + sd per present cell).
# ---------------------------------------------------------------------------

def _build_rows(records):
    rows = []
    for r in records:
        common = dict(publication=PUBLICATION, scale=r["scale"],
                      sample=r["sample"], subsample=r["subsample"],
                      sample_size=r["n"])
        rows.append(make_row(data_type="mean", value=r["mean"], **common))
        rows.append(make_row(data_type="sd",   value=r["sd"],   **common))
    return rows


# ---------------------------------------------------------------------------
# 5. Public entry point.
# ---------------------------------------------------------------------------

def extract(pdf_path):
    """Parse Table 1 (sample x wave x sex) directly from the PDF."""
    pdf_path = Path(pdf_path)
    records = _records(pdf_path)
    raw_df = _build_raw_df(pdf_path)
    parsed_df = _build_parsed_df(records)
    rows = _build_rows(records)
    return raw_df, parsed_df, rows, False
