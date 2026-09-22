"""
PSYRATS_Favrod_et_al_2012.py
=============================
Per-paper extractor for:
    Favrod et al. 2012, "French version validation of the psychotic symptom
    rating scales (PSYRATS) for outpatients with persistent psychotic
    symptoms", BMC Psychiatry 12:161.

LAYOUT NOTE (why this isn't a simple table read)
-------------------------------------------------
There is no data table for the numbers we want. They sit in the first
paragraph of the "Results" section (page 3 of the PDF), which is printed in a
two-column layout. Naive whole-page text extraction interleaves the two
columns line-by-line (the Results column and the neighbouring Instruments
column end up mixed word-for-word), so we crop the page to its right-hand
column before extracting text. Within that column, this PDF's text extraction
also drops most inter-word spaces on some lines (a quirk of this file's
justified-text encoding) and keeps the mid-word hyphens from line-wrapping
(e.g. "delu-" / "sions" across a line break). To parse reliably we:
  1. crop each page to its right half (where "Results" lives on this page),
  2. strip ALL whitespace from the extracted text,
  3. match fixed regex patterns against that stripped text, allowing an
     optional hyphen at the one known line-wrap point ("delu-sions").

The sentence being parsed (as it reads in the paper, spaces restored):
  "The fifty-five participants with auditory hallucinations had a mean score
  of 26.5 (SD = 7.6; range = 8-38) on the auditory hallucination scale. The 94
  participants with delusions had a mean score of 15.1 (SD = 3.6; range:
  3-24) on the delusions scale."

The AHS sample size (55) is only ever written as the word "fifty-five" in this
sentence, never as a digit next to the mean. We treat a successful match of
the literal phrase "fifty-five" as confirmation of n=55 (WORD_TO_N below) --
if the paper's wording ever differed, the regex simply would not match, and
the extractor would fall through to the hardcoded/warning branch below rather
than silently emitting a wrong number.

Both scales here are for the WHOLE 103-person outpatient sample, not two
disjoint patient subsamples -- see PROMPT 1 discussion: AHS (n=55) and DS
(n=94) overlap by 48 participants who reported both symptoms. That's a
known, documented overlap (see sample_information in the concatenation step),
not a bug; we are never asked to sum AHS n + DS n together, so it doesn't
affect this extractor.
"""

from __future__ import annotations

import re

import pandas as pd
import pdfplumber

import scaffold

# ---------------------------------------------------------------------------
# Fixed, paper-specific facts confirmed with the user during PROMPT 1.
# ---------------------------------------------------------------------------
PUBLICATION = "Favrod et al. 2012"
SCALE = "PSYRATS"

# word -> n, for the one count that is only ever spelled out in this sentence.
WORD_TO_N = {"fifty-five": 55}

# regex patterns, matched against the RIGHT-COLUMN text with all whitespace
# stripped out (see module docstring for why).
AHS_PATTERN = re.compile(
    r"fifty-fiveparticipantswithauditoryhallucinationshad"
    r"ameanscoreof(?P<mean>[\d.]+)\(SD=(?P<sd>[\d.]+);"
    r"range=(?P<min>\d+)[\u2013-](?P<max>\d+)\)"
)
DS_PATTERN = re.compile(
    r"(?P<n>\d+)participantswithdelu-?sionshad"
    r"ameanscoreof(?P<mean>[\d.]+)\(SD=(?P<sd>[\d.]+);"
    r"range:(?P<min>\d+)[\u2013-](?P<max>\d+)\)"
)


def _right_column_text(page):
    """Return this page's right-half text with all whitespace stripped.

    Cropping to the right column avoids the column-interleaving that a plain
    page.extract_text() produces on this two-column page.
    """
    width, height = page.width, page.height
    right_half = page.crop((width / 2, 0, width, height))
    text = right_half.extract_text() or ""
    return re.sub(r"\s+", "", text)


def _find_results_sentence(pdf_path):
    """Scan the PDF's pages for the AHS/DS results sentence; return both matches.

    Returns (ahs_match, ds_match), either of which is None if not found.
    """
    ahs_match = None
    ds_match = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            stripped = _right_column_text(page)
            if ahs_match is None:
                ahs_match = AHS_PATTERN.search(stripped)
            if ds_match is None:
                ds_match = DS_PATTERN.search(stripped)
            if ahs_match and ds_match:
                break
    return ahs_match, ds_match


def extract(pdf_path):
    """Extract PSYRATS AHS/DS mean, sd, min, max for Favrod et al. 2012.

    Returns (raw_df, parsed_df, rows, hardcoded_flag) per the scaffold
    interface.
    """
    ahs_match, ds_match = _find_results_sentence(pdf_path)

    hardcoded = False
    if ahs_match is None or ds_match is None:
        # Parsing failed -- fall back to the hand-checked values from PROMPT 1
        # rather than silently returning nothing, but flag it loudly.
        hardcoded = True
        ahs = {"n": 55, "mean": 26.5, "sd": 7.6, "min": 8, "max": 38}
        ds = {"n": 94, "mean": 15.1, "sd": 3.6, "min": 3, "max": 24}
    else:
        ahs = {
            "n": WORD_TO_N["fifty-five"],
            "mean": float(ahs_match.group("mean")),
            "sd": float(ahs_match.group("sd")),
            "min": int(ahs_match.group("min")),
            "max": int(ahs_match.group("max")),
        }
        ds = {
            "n": int(ds_match.group("n")),
            "mean": float(ds_match.group("mean")),
            "sd": float(ds_match.group("sd")),
            "min": int(ds_match.group("min")),
            "max": int(ds_match.group("max")),
        }

    # --- RAW verification view: packed cells, as in the paper -------------
    raw_df = pd.DataFrame([
        {
            "scale_label": "Auditory Hallucination Scale (AHS)",
            "n": ahs["n"],
            "mean_sd": f"{ahs['mean']} ({ahs['sd']})",
            "range": f"{ahs['min']}-{ahs['max']}",
        },
        {
            "scale_label": "Delusion Scale (DS)",
            "n": ds["n"],
            "mean_sd": f"{ds['mean']} ({ds['sd']})",
            "range": f"{ds['min']}-{ds['max']}",
        },
    ])

    # --- PARSED verification view: split into separate fields -------------
    parsed_df = pd.DataFrame([
        {"scale": SCALE, "subscale": "AHS", "proposed_subsample": "whole_sample_AHS",
         "sample_type": "patients", "n": ahs["n"], "mean": ahs["mean"], "sd": ahs["sd"],
         "minimum": ahs["min"], "maximum": ahs["max"]},
        {"scale": SCALE, "subscale": "DS", "proposed_subsample": "whole_sample_DS",
         "sample_type": "patients", "n": ds["n"], "mean": ds["mean"], "sd": ds["sd"],
         "minimum": ds["min"], "maximum": ds["max"]},
    ])

    # --- long-format rows ---------------------------------------------------
    rows = []
    for subscale, stats, subsample, scale_old in [
        ("AHS", ahs, "whole_sample_AHS", "auditory hallucination scale"),
        ("DS", ds, "whole_sample_DS", "delusions scale"),
    ]:
        for data_type, value in [
            ("mean", stats["mean"]),
            ("sd", stats["sd"]),
            ("minimum", stats["min"]),
            ("maximum", stats["max"]),
        ]:
            rows.append(scaffold.make_row(
                publication=PUBLICATION,
                scale_old=scale_old,
                data_type=data_type,
                sample_type="patients",
                value=value,
                scale=SCALE,
                record_type="subscale",
                subsample=subsample,
                sample_size=stats["n"],
                subscale=subscale,
                scoring_rule="unverified",
                redundant_aggregate=False,
            ))

    return raw_df, parsed_df, rows, hardcoded
