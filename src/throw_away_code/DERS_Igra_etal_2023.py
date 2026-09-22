"""
DERS_Igra_etal_2023.py
======================
Per-paper extractor for:

    Igra et al. 2023, "Examining the associations between difficulties in
    emotion regulation and symptomatic outcome measures among individuals
    with different mental disorders", Frontiers in Psychology 14:944457.
    DERS subscale means (SDs) from Table 1.

Reads the six DERS subscale rows of Table 1 DIRECTLY from the PDF
(pdfplumber) and returns rows for the normalized schema via
scaffold.make_row().

TABLE 1 LAYOUT (page 5, 0-based index 4)
----------------------------------------
Table 1 is a matrix: 6 DERS subscales (rows) x 3 diagnostic groups (columns),
each cell a "M (SD)". After pdfplumber's text extraction each subscale's data
sits on ONE line that starts with the subscale label, e.g.:

  "Lack of awareness 14.66 (4.60) 17.14 (3.16) 16.24 (3.62) 3.83* 0.07 ..."
   |---- label ----|  SCZ M (SD)   EDs M (SD)    Controls M(SD)  |-ANOVA/post hoc-|

The three M (SD) pairs (SCZ, EDs, Controls) are the first three
"number (number)" cells on the line; everything after them (F, eta^2, p
values) is ignored. Two subscale labels wrap onto a second line
("emotion regulation", "goal-directed behaviors") but the DATA is always on
the first line, so we match each row by a unique label PREFIX.

CONFIRMED NORMALIZATION (from the user)
---------------------------------------
  scale = "DERS", record_type = "subscale"
  scale_old = "DERS_" + the paper's full subscale label
  subscale  = the normalized name (mapping below)
  groups -> SCZ = patients / subsample "schizophrenia" (n=36)
            EDs = patients / subsample "emotional_disorders" (n=36)
            Controls = healthy_controls / subsample "whole_sample" (n=36)
  no individual-item rows; no redundant aggregates (the 3 groups are separate,
  matched samples that do not overlap).
"""

import re

import pdfplumber

from scaffold import make_row, split_paren

PUBLICATION = "Igra et al. 2023"
SCALE = "DERS"
TABLE_PAGE_INDEX = 4          # Table 1 is on PDF page 5 (0-based index 4)
HARDCODED = False

# A unique starting prefix of each subscale's data line -> (paper label,
# normalized subscale). The prefix must be enough to identify the line
# unambiguously; the full paper label is used to build scale_old.
SUBSCALES = [
    ("Lack of awareness",        "Lack of awareness",
                                 "AWARENESS"),
    ("Lack of clarity",          "Lack of clarity",
                                 "CLARITY"),
    ("Non-acceptance",           "Non-acceptance",
                                 "NONACCEPTANCE"),
    ("Limited access to",        "Limited access to emotion regulation strategies",
                                 "STRATEGIES"),
    ("Difficulties controlling", "Difficulties controlling impulses",
                                 "IMPULSE"),
    ("Difficulties engaging in", "Difficulties engaging in goal-directed behaviors",
                                 "GOALS"),
]

# The three diagnostic-group columns, in the order they appear left-to-right:
# (sample_type, subsample, n).
GROUPS = [
    ("patients",         "schizophrenia",        36),   # SCZ column
    ("patients",         "emotional_disorders",  36),   # EDs column
    ("healthy_controls", "whole_sample",         36),   # Controls column
]


# ---------------------------------------------------------------------------
# Read the six subscale data lines from Table 1.
# ---------------------------------------------------------------------------
def _read_table(pdf_path):
    """Return a list of dicts, one per (subscale x group) cell.

    Each dict: scale_old, subscale, sample_type, subsample, n, mean, sd.
    """
    page = pdfplumber.open(pdf_path).pages[TABLE_PAGE_INDEX]
    lines = page.extract_text().split("\n")

    records = []
    for prefix, paper_label, norm_subscale in SUBSCALES:
        # find the one data line that starts with this subscale's prefix
        line = _find_line(lines, prefix)

        # pull every "number (number)" cell; the first three are SCZ/EDs/Controls
        cells = re.findall(r"[-\d.]+\s*\([-\d.]+\)", line)
        mean_sd_pairs = [split_paren(c.replace(" ", "")) for c in cells[:3]]

        for (mean, sd), (sample_type, subsample, n) in zip(mean_sd_pairs, GROUPS):
            records.append({
                "scale_old": f"DERS_{paper_label}",
                "subscale": norm_subscale,
                "sample_type": sample_type,
                "subsample": subsample,
                "n": n,
                "mean": mean,
                "sd": sd,
            })
    return records


def _find_line(lines, prefix):
    """Return the single line starting with `prefix` (after stripping)."""
    for line in lines:
        if line.strip().startswith(prefix):
            return line
    raise ValueError(f"could not find a table line starting with {prefix!r}")


# ---------------------------------------------------------------------------
# Build the two verification views (raw packed + parsed).
# ---------------------------------------------------------------------------
def _build_verification(records):
    import pandas as pd

    # RAW: one row per subscale, the three groups side by side (packed cells).
    # Rebuild from records, grouped by scale_old in original subscale order.
    raw_by_subscale = {}
    for r in records:
        raw_by_subscale.setdefault(r["scale_old"], {})[r["subsample"]] = (
            f"{r['mean']} ({r['sd']})")

    raw_rows = []
    for prefix, paper_label, norm in SUBSCALES:
        key = f"DERS_{paper_label}"
        cells = raw_by_subscale[key]
        raw_rows.append({
            "Measure": paper_label,
            "SCZ M (SD)": cells["schizophrenia"],
            "EDs M (SD)": cells["emotional_disorders"],
            "Controls M (SD)": cells["whole_sample"],
        })
    raw_df = pd.DataFrame(raw_rows)

    # PARSED: long form, one row per (subscale x group).
    parsed_df = pd.DataFrame([{
        "scale_old": r["scale_old"], "subscale": r["subscale"],
        "sample_type": r["sample_type"], "subsample": r["subsample"],
        "n": r["n"], "mean": r["mean"], "sd": r["sd"],
    } for r in records])

    return raw_df, parsed_df


# ---------------------------------------------------------------------------
# Turn one (subscale x group) record into its long-format rows (mean, sd).
# ---------------------------------------------------------------------------
def _rows_for_record(r):
    """Emit the mean and sd long-format rows for one table cell."""
    stats = {"mean": r["mean"], "sd": r["sd"]}
    out = []
    for data_type in ("mean", "sd"):
        out.append(make_row(
            publication=PUBLICATION,
            scale_old=r["scale_old"],
            data_type=data_type,
            sample_type=r["sample_type"],
            value=stats[data_type],
            scale=SCALE,
            record_type="subscale",
            subsample=r["subsample"],
            sample_size=r["n"],
            subscale=r["subscale"],
            # three separate matched groups -> no overlap, nothing redundant
            redundant_aggregate=False,
        ))
    return out


# ---------------------------------------------------------------------------
# The entry point the scaffold calls.
# ---------------------------------------------------------------------------
def extract(pdf_path):
    """Return (raw_df, parsed_df, rows, hardcoded_flag)."""
    records = _read_table(pdf_path)
    raw_df, parsed_df = _build_verification(records)

    rows = []
    for r in records:
        rows.extend(_rows_for_record(r))

    return raw_df, parsed_df, rows, HARDCODED
