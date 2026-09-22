"""
PSYRATS_Haddock_et_al_1999.py
==============================
Per-paper extractor for:
    Haddock et al. 1999, "Scales to measure dimensions of hallucinations and
    delusions: the psychotic symptom rating scales (PSYRATS)",
    Psychological Medicine 29:879-889.

SOURCE: Table 2 ("Item medians and ranges for the modified KGV, AS and DS"),
page 884. Only the AS (-> our AHS) and DS sections are extracted; KGV rows
are out of scope.

LAYOUT NOTE
-----------
Table 2 is printed as two columns on the page: a left column of item labels,
a right column of "median (range)" values, aligned row-for-row. Cropping the
page to its right half and pulling every "N (N-N)" pattern out of it, in
order, gives exactly 22 values -- 7 KGV rows, then 8 AS rows (7 items + the
"Overall total (T-AH)" row), then 7 DS rows (6 items + "Overall total
(T-DS)"). Verified against a manual read of the table (see PROMPT 1): this
regex extraction and the addendum's confirmed order line up exactly, so we
rely on POSITION within that 22-value sequence rather than re-parsing the
left (label) column -- the left column's row order was confirmed by eye
against the PDF, not re-derived programmatically, since two of its rows
group several items under one shared row label (see below).

TABLE QUIRK: some rows report ONE median/range for SEVERAL items at once
(the paper's own choice of layout, not a parsing artifact):
  - "Frequency, duration, location, beliefs re-origin" (one AS row) is
    expanded into 4 separate item rows, all carrying that row's value.
  - "Negative content (amount and degree)" (one AS row) is expanded into 2
    item rows (amount, degree), both carrying that row's value.
This means several items in the output share an identical median/min/max --
that is what the paper reports, not a bug.

SAMPLE SIZES: NOT in Table 2 itself (no n column). Per the addendum
discussion for this paper: AHS n=56, DS n=57, derived from the "Subjects"
section (p.882): "Forty-two patients had both auditory hallucinations and
delusions, 14 had hallucinations only and 15 had delusions only" and
"Patients were also assessed using the PSYRATS (the AH or DS being
administered where symptoms were present)". 42+14=56 (AHS), 42+15=57 (DS),
and 42+14+15=71 matches the full recruited sample exactly. Hardcoded here as
confirmed constants (not read from Table 2's own page) since they come from
prose elsewhere in the PDF, not from this table.
"""

from __future__ import annotations

import re

import pandas as pd
import pdfplumber

import scaffold

# ---------------------------------------------------------------------------
# Fixed, paper-specific facts confirmed with the user during PROMPT 1.
# ---------------------------------------------------------------------------
PUBLICATION = "Haddock et al. 1999"
SCALE = "PSYRATS"

# Sample sizes -- from the Subjects section (p.882), NOT from Table 2 itself.
# See module docstring for the arithmetic.
N_AHS = 56
N_DS = 57

VALUE_PATTERN = re.compile(r"(\d+)\s*\((\d+)[\u2013-](\d+)\)")

# ---------------------------------------------------------------------------
# The 22 rows of Table 2, IN ORDER, confirmed against the PDF at PROMPT 1.
# Each entry: (subscale or None for KGV/out-of-scope, [(item_name, scale_old), ...])
# A row with more than one (item_name, scale_old) pair is one of the
# "grouped" rows described in the module docstring: every item in the list
# gets that row's median/min/max value.
# `None` for the item list marks the subscale-level "Overall total" row
# (record_type="subscale", no item_name).
# ---------------------------------------------------------------------------
ROW_MAP = [
    (None, "skip"),                                                   # 0 KGV: Anxiety, depression
    (None, "skip"),                                                   # 1 KGV: Suicidality
    (None, "skip"),                                                   # 2 KGV: Hallucinations, delusions
    (None, "skip"),                                                   # 3 KGV: Flattened affect, abnormal movements
    (None, "skip"),                                                   # 4 KGV: Incongruity...elevated mood
    (None, "skip"),                                                   # 5 KGV: Cooperation
    (None, "skip"),                                                   # 6 KGV: Overall total (T-KGV)
    ("AHS", [("PSYRATS-AS_frequency", "Frequency"),
             ("PSYRATS-AS_duration", "Duration"),
             ("PSYRATS-AS_location", "Location"),
             ("PSYRATS-AS_beliefs_re_origin", "Beliefs re-origin of voices")]),  # 7
    ("AHS", [("PSYRATS-AS_loudness", "Loudness")]),                                # 8
    ("AHS", [("PSYRATS-AS_negative_content_amount", "Amount of negative content of voices"),
             ("PSYRATS-AS_negative_content_degree", "Degree of negative content")]),  # 9
    ("AHS", [("PSYRATS-AS_distress_amount", "Amount of distress")]),               # 10
    ("AHS", [("PSYRATS-AS_distress_intensity", "Intensity of distress")]),         # 11
    ("AHS", [("PSYRATS-AS_disruption", "Disruption to life caused by voices")]),   # 12
    ("AHS", [("PSYRATS-AS_control", "Controllability of voices")]),                # 13
    ("AHS", None),                                                                 # 14 Overall total (T-AH)
    ("DS", [("PSYRATS-DS_preoccupation_amount", "Amount of preoccupation with delusions")]),   # 15
    ("DS", [("PSYRATS-DS_preoccupation_duration", "Duration of preoccupation with delusions")]),  # 16
    ("DS", [("PSYRATS-DS_conviction", "Conviction")]),                             # 17
    ("DS", [("PSYRATS-DS_distress_amount", "Amount of distress")]),                # 18
    ("DS", [("PSYRATS-DS_distress_intensity", "Intensity of distress")]),          # 19
    ("DS", [("PSYRATS-DS_disruption", "Disruption to life caused by beliefs")]),   # 20
    ("DS", None),                                                                  # 21 Overall total (T-DS)
]


def _find_table2_values(pdf_path):
    """Locate Table 2 and return its 22 (median, min, max) triples, in order.

    Cropping to the right half avoids this page's own column-interleaving
    (same issue as the Favrod extractor, different page).
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "Item medians and ranges" in text:
                width, height = page.width, page.height
                right_half = page.crop((width / 2, 0, width, height))
                right_text = right_half.extract_text() or ""
                return VALUE_PATTERN.findall(right_text)
    return []


def extract(pdf_path):
    """Extract PSYRATS AHS/DS item- and subscale-level median/min/max for
    Haddock et al. 1999.

    Returns (raw_df, parsed_df, rows, hardcoded_flag) per the scaffold
    interface.
    """
    values = _find_table2_values(pdf_path)

    hardcoded = False
    if len(values) != len(ROW_MAP):
        # Table structure didn't parse as expected -- fall back to the
        # hand-checked PROMPT 1 values rather than silently emitting nothing,
        # but flag it loudly. (As of writing this branch is never taken --
        # verified to produce exactly 22 matches -- but kept as a safety net
        # against a future PDF re-render changing the extracted text.)
        hardcoded = True
        values = [
            ("2", "0", "4"), ("1", "0", "4"), ("3", "0", "4"), ("1", "0", "3"),
            ("0", "0", "3"), ("0", "0", "2"), ("15", "5", "31"),
            ("3", "1", "4"), ("2", "1", "4"), ("3", "0", "4"), ("3", "0", "4"),
            ("2", "0", "4"), ("2", "0", "3"), ("3", "0", "4"), ("28", "14", "39"),
            ("3", "1", "4"), ("2", "1", "4"), ("3", "1", "4"), ("3", "0", "4"),
            ("2", "0", "5"), ("2", "0", "4"), ("15", "5", "22"),
        ]

    n_for_subscale = {"AHS": N_AHS, "DS": N_DS}

    # --- RAW verification view: packed cells, as in the paper -------------
    raw_records = []
    for (subscale, item_spec), (median, lo, hi) in zip(ROW_MAP, values):
        if subscale is None:
            continue
        label = "Overall total" if item_spec is None else " / ".join(
            name for _, name in item_spec)
        raw_records.append({
            "section": subscale, "item_label": label,
            "median_range": f"{median} ({lo}-{hi})",
        })
    raw_df = pd.DataFrame(raw_records)

    # --- PARSED verification view ------------------------------------------
    parsed_records = []
    for (subscale, item_spec), (median, lo, hi) in zip(ROW_MAP, values):
        if subscale is None:
            continue
        n = n_for_subscale[subscale]
        if item_spec is None:
            parsed_records.append({
                "scale": SCALE, "subscale": subscale, "record_type": "subscale",
                "item_name": "none", "n": n,
                "median": int(median), "minimum": int(lo), "maximum": int(hi),
            })
        else:
            for item_name, scale_old in item_spec:
                parsed_records.append({
                    "scale": SCALE, "subscale": subscale, "record_type": "item",
                    "item_name": item_name, "n": n,
                    "median": int(median), "minimum": int(lo), "maximum": int(hi),
                })
    parsed_df = pd.DataFrame(parsed_records)

    # --- long-format rows ---------------------------------------------------
    rows = []
    for (subscale, item_spec), (median, lo, hi) in zip(ROW_MAP, values):
        if subscale is None:
            continue
        n = n_for_subscale[subscale]
        subsample = f"whole_sample_{subscale}"
        stats = [("median", int(median)), ("minimum", int(lo)), ("maximum", int(hi))]

        if item_spec is None:
            # subscale-level "Overall total" row
            for data_type, value in stats:
                rows.append(scaffold.make_row(
                    publication=PUBLICATION,
                    scale_old="Overall total",
                    data_type=data_type,
                    sample_type="patients",
                    value=value,
                    scale=SCALE,
                    record_type="subscale",
                    subsample=subsample,
                    sample_size=n,
                    subscale=subscale,
                    scoring_rule="unverified",
                ))
        else:
            for item_name, scale_old in item_spec:
                for data_type, value in stats:
                    rows.append(scaffold.make_row(
                        publication=PUBLICATION,
                        scale_old=scale_old,
                        data_type=data_type,
                        sample_type="patients",
                        value=value,
                        scale=SCALE,
                        record_type="item",
                        subsample=subsample,
                        sample_size=n,
                        subscale=subscale,
                        item_name=item_name,
                        scoring_rule="unverified",
                    ))

    return raw_df, parsed_df, rows, hardcoded
