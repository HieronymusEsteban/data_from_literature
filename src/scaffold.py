"""
scaffold.py
===========
The STABLE part of the extraction pipeline. This code does NOT change from
paper to paper. Each paper gets its own small "extractor" module; this file
provides the shared machinery they all rely on.

WHAT THIS FILE PROVIDES
-----------------------
  make_row()          - build one long-format row (the normalized schema).
  split_paren()       - split a packed "mean(sd)" string into two numbers.
  validate_rows()     - basic structural checks before writing.
  write_verification()- write the eyeball-check tables to raw_extracted/.
  write_consolidated()- write the per-publication long CSV to consolidated/,
                        with a loud warning if values were hardcoded.
  run_extraction()    - the wrapper that ties a paper's extractor together
                        with all of the above.

A per-paper extractor returns four things:
    (raw_df, parsed_df, rows, hardcoded_flag)
where `rows` is a list of dicts built with make_row().

THE THREE-STAGE WORKFLOW (unchanged)
------------------------------------
  1. You verify the numbers by eye (from the assistant's presentation).
  2. raw_extracted/  : the data laid out like the publication (easy to check).
  3. consolidated/   : the long-format CSV, one per publication.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# The normalized long-format schema — defined ONCE, here.
# ---------------------------------------------------------------------------
# Every row in a per-publication long CSV has exactly these columns, in order.
SCHEMA_COLUMNS = [
    "publication",           # bibliographic id (author-year or DOI string)
    "scale_old",             # the label as written in the paper (close to source)
    "data_type",             # mean | median | sd | minimum | maximum | individual
    "sample_type",           # patients | healthy_controls | community
    "subsample",             # diagnosis / demographic group, or "whole_sample"
    "sample_size",           # n for this group (int), or "NA"
    "value",                 # the actual number
    "source_file",           # filled at consolidation (the long CSV's own name)
    "scale",                 # your normalized scale name (you decide it)
    "subscale",              # your normalized subscale name, or "none"
    "item_name",             # the item's text/label (only for item rows)
    "record_type",           # total | subscale | item
    "redcap_item_number",    # only for items; else "none" (you fill later)
    "scoring_rule",          # e.g. raw_sum | arithmetic_mean | "unverified"
    "item_score_reversed",   # only for items: "yes" | "no" | "none"
    "redundant_aggregate",   # True if this whole-sample value overlaps its subsamples
]

# Controlled vocabularies — kept explicit so a typo fails loudly instead of
# silently entering the data.
ALLOWED_DATA_TYPES = {"mean", "median", "sd", "minimum", "maximum", "individual"}
ALLOWED_SAMPLE_TYPES = {"patients", "healthy_controls", "community"}
ALLOWED_RECORD_TYPES = {"total", "subscale", "item"}

# The marker used for "not applicable" in text columns.
NA_MARKER = "NA"


# ---------------------------------------------------------------------------
# Build one schema-conforming long-format row.
# ---------------------------------------------------------------------------
def make_row(publication, scale_old, data_type, sample_type, value,
             scale, record_type,
             subsample="whole_sample",
             sample_size=NA_MARKER,
             source_file=NA_MARKER,
             subscale="none",
             item_name="none",
             redcap_item_number="none",
             scoring_rule="unverified",
             item_score_reversed="none",
             redundant_aggregate=False):
    """Build one long-format row (a dict) matching SCHEMA_COLUMNS.

    Only the first arguments are required; the item-specific and
    fill-in-later fields have sensible defaults, so a simple total-score row
    stays a short call. The controlled-vocabulary fields are checked so a
    typo is caught immediately.

    Required
    --------
    publication, scale_old, data_type, sample_type, value, scale, record_type

    Common optionals
    ----------------
    subsample     : defaults to "whole_sample"
    sample_size   : defaults to "NA"
    source_file   : usually filled at consolidation, defaults to "NA"

    Item / later-fill optionals (defaults are the agreed placeholders)
    ------------------------------------------------------------------
    subscale="none", item_name="none", redcap_item_number="none",
    scoring_rule="unverified", item_score_reversed="none",
    redundant_aggregate=False
    """
    # --- validate the controlled-vocabulary fields ---
    if data_type not in ALLOWED_DATA_TYPES:
        raise ValueError(f"data_type {data_type!r} not in {sorted(ALLOWED_DATA_TYPES)}")
    if sample_type not in ALLOWED_SAMPLE_TYPES:
        raise ValueError(f"sample_type {sample_type!r} not in {sorted(ALLOWED_SAMPLE_TYPES)}")
    if record_type not in ALLOWED_RECORD_TYPES:
        raise ValueError(f"record_type {record_type!r} not in {sorted(ALLOWED_RECORD_TYPES)}")

    # --- build the row in the canonical column order ---
    return {
        "publication": publication,
        "scale_old": scale_old,
        "data_type": data_type,
        "sample_type": sample_type,
        "subsample": subsample,
        "sample_size": sample_size,
        "value": value,
        "source_file": source_file,
        "scale": scale,
        "subscale": subscale,
        "item_name": item_name,
        "record_type": record_type,
        "redcap_item_number": redcap_item_number,
        "scoring_rule": scoring_rule,
        "item_score_reversed": item_score_reversed,
        "redundant_aggregate": redundant_aggregate,
    }


# ---------------------------------------------------------------------------
# Split a packed "mean(sd)" cell into two floats.
# ---------------------------------------------------------------------------
def split_paren(tok):
    """'9.4(7.5)' -> (9.4, 7.5). Handles a comma decimal separator too."""
    tok = str(tok).replace(",", ".")
    match = re.match(r"^([-\d.]+)\(([-\d.]+)\)$", tok.strip())
    if not match:
        raise ValueError(f"cannot parse 'mean(sd)' from {tok!r}")
    return float(match.group(1)), float(match.group(2))


# ---------------------------------------------------------------------------
# Validate the assembled frame before writing.
# ---------------------------------------------------------------------------
def validate_rows(df):
    """Check the frame has exactly the schema columns and a numeric value column.

    Returns the frame with columns put into the canonical order.
    """
    missing = set(SCHEMA_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")

    df = df[SCHEMA_COLUMNS]   # canonical order

    if not pd.api.types.is_numeric_dtype(df["value"]):
        raise ValueError("`value` column must be numeric")

    return df


# ---------------------------------------------------------------------------
# Write the two verification tables (raw + parsed) to raw_extracted/.
# ---------------------------------------------------------------------------
def write_verification(raw_df, parsed_df, pdf_stem, raw_extracted_dir):
    """Write the eyeball-check tables to raw_extracted/<pdf_stem>/.

    raw_df    : the data laid out like the publication (packed cells kept).
    parsed_df : the same data with mean/sd/median split into columns.
    """
    out_dir = Path(raw_extracted_dir) / pdf_stem
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / f"{pdf_stem}_verify_raw.csv"
    parsed_path = out_dir / f"{pdf_stem}_verify_parsed.csv"

    raw_df.to_csv(raw_path, index=False)
    parsed_df.to_csv(parsed_path, index=False)

    print(f"verification (raw)    -> {raw_path}")
    print(f"verification (parsed) -> {parsed_path}")


# ---------------------------------------------------------------------------
# Write the per-publication long CSV to consolidated/ (with hardcoding warning).
# ---------------------------------------------------------------------------
def write_consolidated(rows, hardcoded, pdf_stem, consolidated_dir):
    """Validate the rows and write the long CSV to consolidated/<pdf_stem>/.

    `source_file` is filled in here with the long CSV's own filename, so every
    row knows which file it came from.

    If `hardcoded` is True, a loud warning is printed and a
    *.HARDCODED_WARNING.txt file is written, so hand-typed values can never
    pass unnoticed.
    """
    df = pd.DataFrame(rows)

    out_dir = Path(consolidated_dir) / pdf_stem
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{pdf_stem}_long.csv"

    # Stamp every row with the name of the file it lives in.
    df["source_file"] = out.name

    df = validate_rows(df)
    df.to_csv(out, index=False)
    print(f"consolidated long-format -> {out}")

    warn = out_dir / f"{pdf_stem}.HARDCODED_WARNING.txt"
    if hardcoded:
        msg = ("WARNING: values for this publication were HARDCODED (typed by "
               "hand), NOT read from the PDF. Verify manually before use.")
        print("!!! " + msg)
        warn.write_text(msg + "\n")
    elif warn.exists():
        warn.unlink()   # clear a stale warning from a previous run

    return df


# ---------------------------------------------------------------------------
# Wrapper: run a paper-specific extractor, then write both outputs.
# ---------------------------------------------------------------------------
def run_extraction(pdf_path, extractor, raw_extracted_dir, consolidated_dir):
    """Full extraction for one paper: run its extractor, write both outputs.

    `extractor` is the paper-specific function; it returns
        (raw_df, parsed_df, rows, hardcoded_flag).

    Returns (raw_df, parsed_df, long_df, hardcoded_flag).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    stem = pdf_path.stem

    raw_df, parsed_df, rows, hardcoded = extractor(pdf_path)
    if not rows:
        raise ValueError("extractor returned no rows")

    write_verification(raw_df, parsed_df, stem, raw_extracted_dir)
    long_df = write_consolidated(rows, hardcoded, stem, consolidated_dir)

    return raw_df, parsed_df, long_df, hardcoded
