"""
BNSS_kirkpatrick_et_al_2011.py
================================
Per-paper extractor for:
    Kirkpatrick et al. 2011, "The Brief Negative Symptom Scale: Psychometric
    Properties", Schizophrenia Bulletin 37(2):300-305.

SOURCE: Table 2 ("Descriptive Statistics for the 6 Subscales of the Brief
Negative Symptom Scale"), page 302.

LAYOUT NOTE
-----------
Unlike the PSYRATS papers extracted earlier, this table's page renders as
clean, single-line rows under plain page.extract_text() -- no two-column
interleaving to work around. Each of the "Mean", "Median", "SD" and "Range"
rows is one line: a label followed by 7 space-separated values, in column
order (Total Score, Anhedonia, Distress, Asociality, Avolition, Blunted
Affect, Alogia). We find those four lines by their leading label and split
on whitespace. The "Range" row's cells use an en dash ("0-66"), so those are
additionally split into (minimum, maximum). Skewness/Kurtosis rows exist in
the table but are out of scope (not requested) and are not parsed.

SAMPLE SIZE: n=20 for every column (one flat sample, no subsamples) --
confirmed in the "Participants" section (p.301): "Twenty subjects... were
recruited from outpatient units at the Medical College of Georgia (N = 10)
and the Maryland Psychiatric Research Center (N = 10)" (10+10=20). Not
stated again in Table 2 itself, so treated as a paper-wide constant here,
same as Haddock's n's were carried over from its Subjects section.
"""

from __future__ import annotations

import pandas as pd
import pdfplumber

import scaffold

# ---------------------------------------------------------------------------
# Fixed, paper-specific facts confirmed with the user during PROMPT 1.
# ---------------------------------------------------------------------------
PUBLICATION = "Kirkpatrick et al. 2011"
SCALE = "BNSS"
N = 20  # whole sample, uniform across every column -- see module docstring

# Column order in Table 2, left to right, mapped to (subscale code, record_type).
# "Total Score" has no subscale code -- record_type="total", subscale="none".
COLUMNS = [
    ("none", "total", "Total Score"),
    ("ANH", "subscale", "Anhedonia"),
    ("DIS", "subscale", "Distress"),
    ("ASO", "subscale", "Asociality"),
    ("AVO", "subscale", "Avolition"),
    ("BA", "subscale", "Blunted Affect"),
    ("ALO", "subscale", "Alogia"),
]


def _table2_lines(pdf_path):
    """Return the Mean/Median/SD/Range lines of Table 2, or None if not found."""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "DescriptiveStatisticsforthe6Subscales" in text.replace(" ", ""):
                lines = {}
                for line in text.splitlines():
                    for label in ("Mean", "Median", "SD", "Range"):
                        if line.startswith(label + " "):
                            lines[label] = line.split()[1:]  # drop the label token
                if len(lines) == 4:
                    return lines
    return None


def extract(pdf_path):
    """Extract BNSS total/subscale mean, median, sd, min, max for
    Kirkpatrick et al. 2011.

    Returns (raw_df, parsed_df, rows, hardcoded_flag) per the scaffold
    interface.
    """
    lines = _table2_lines(pdf_path)

    hardcoded = False
    if lines is None or any(len(v) != 7 for v in lines.values()):
        # Couldn't find/parse the four rows cleanly -- fall back to the
        # hand-checked PROMPT 1 values rather than emitting nothing, but
        # flag it loudly. (Not expected to trigger -- verified below to
        # parse cleanly -- kept as a safety net.)
        hardcoded = True
        lines = {
            "Mean": ["26.8", "5.4", "1.6", "3.9", "5.0", "7.7", "3.4"],
            "Median": ["27.0", "5.0", "1.0", "4.0", "5.0", "8.0", "3.0"],
            "SD": ["16.8", "4.9", "1.8", "2.9", "3.1", "5.1", "3.3"],
            "Range": ["0-66", "0-18", "0-6", "0-12", "0-11", "0-18", "0-12"],
        }

    # split each Range cell "0-66" into (minimum, maximum)
    mins, maxs = [], []
    for cell in lines["Range"]:
        lo, hi = cell.replace("\u2013", "-").split("-")
        mins.append(lo)
        maxs.append(hi)

    # --- RAW verification view: packed cells, as in the paper -------------
    raw_df = pd.DataFrame(
        [lines["Mean"], lines["Median"], lines["SD"], lines["Range"]],
        index=["Mean", "Median", "SD", "Range"],
        columns=[label for _, _, label in COLUMNS],
    ).reset_index(names="statistic")

    # --- PARSED verification view ------------------------------------------
    parsed_records = []
    for i, (subscale, record_type, label) in enumerate(COLUMNS):
        parsed_records.append({
            "scale": SCALE, "subscale": subscale, "record_type": record_type,
            "n": N,
            "mean": float(lines["Mean"][i]),
            "median": float(lines["Median"][i]),
            "sd": float(lines["SD"][i]),
            "minimum": float(mins[i]),
            "maximum": float(maxs[i]),
        })
    parsed_df = pd.DataFrame(parsed_records)

    # --- long-format rows ---------------------------------------------------
    rows = []
    for i, (subscale, record_type, label) in enumerate(COLUMNS):
        stats = [
            ("mean", float(lines["Mean"][i])),
            ("median", float(lines["Median"][i])),
            ("sd", float(lines["SD"][i])),
            ("minimum", float(mins[i])),
            ("maximum", float(maxs[i])),
        ]
        for data_type, value in stats:
            rows.append(scaffold.make_row(
                publication=PUBLICATION,
                scale_old=label,
                data_type=data_type,
                sample_type="patients",
                value=value,
                scale=SCALE,
                record_type=record_type,
                subsample="whole_sample",
                sample_size=N,
                subscale=subscale,
                scoring_rule="unverified",
            ))

    return raw_df, parsed_df, rows, hardcoded
