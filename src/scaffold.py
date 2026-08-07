"""
scaffold.py
===========
The STABLE part of the extraction pipeline. This code does not change from
paper to paper. It defines:

  1. The consolidated long-format schema (the column names, in one place).
  2. make_row()         - build one schema-conforming long-format row.
  3. split_paren()      - split a packed "mean(sd)" string into two numbers.
  4. validate_rows()    - structural checks before writing.
  5. write_verification() - write the eyeball-check tables (raw packed layout +
                          parsed layout) to raw_extracted/<pdf_name>/.
  6. write_consolidated() - validate and write the long-format CSV to
                          consolidated/<pdf_name>/, emitting a visible warning
                          (and a *.HARDCODED_WARNING.txt file) if values were
                          hardcoded rather than read from the PDF.
  7. run_extraction()   - the wrapper: runs a paper-specific extractor, then
                          writes both the verification view and the long-format
                          output.

A per-paper extractor returns (raw_df, parsed_df, rows, hardcoded_flag), where
`rows` are built with make_row(). Everything else is handled here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. The consolidated long-format schema — defined ONCE, here.
# ---------------------------------------------------------------------------
# Every row in the final per-scale CSV has exactly these columns, in this order.
SCHEMA_COLUMNS = [
    "publication",    # bibliographic id (DOI or author-year string)
    "scale",          # e.g. "DES-T"
    "data_type",      # mean | median | sd | minimum | maximum | individual
    "sample",         # patients | healthy_controls | community
    "subsample",      # specific diagnosis / demographic group, or "NA"
    "sample_size",    # n for this group (int), or "NA" where not applicable
    "value",          # the actual number
]

# Allowed values for `data_type`, kept explicit so a typo fails loudly.
ALLOWED_DATA_TYPES = {"mean", "median", "sd", "minimum", "maximum", "individual"}

# Allowed values for `sample`.
ALLOWED_SAMPLES = {"patients", "healthy_controls", "community"}

# The marker used for "not applicable" in text columns.
NA_MARKER = "NA"


# ---------------------------------------------------------------------------
# 1. Build one schema-conforming long-format row.
# ---------------------------------------------------------------------------

def make_row(publication, scale, data_type, sample, value,
             subsample=NA_MARKER, sample_size=NA_MARKER):
    """Return one row (a dict) that conforms to SCHEMA_COLUMNS.

    Validates the controlled-vocabulary fields so mistakes surface immediately
    rather than silently entering the dataset.
    """
    if data_type not in ALLOWED_DATA_TYPES:
        raise ValueError(
            f"data_type {data_type!r} not allowed"
            )
    if sample not in ALLOWED_SAMPLES:
        raise ValueError(
            f"sample {sample!r} not allowed"
            )
    return {
        "publication": publication, 
        "scale": scale, 
        "data_type": data_type,
        "sample": sample, 
        "subsample": subsample,
        "sample_size": sample_size, 
        "value": value
    }

# ---------------------------------------------------------------------------
# 2. Split a packed "mean(sd)" cell into two floats.
# ---------------------------------------------------------------------------

def split_paren(tok):
    """'9.4(7.5)' -> (9.4, 7.5); comma-decimal safe."""
    tok = str(tok).replace(",", ".")
    m = re.match(r"^([-\d.]+)\(([-\d.]+)\)$", tok.strip())
    if not m:
        raise ValueError(f"cannot parse 'mean(sd)' from {tok!r}")
    return float(m.group(1)), float(m.group(2))

# ---------------------------------------------------------------------------
# 3. Validate the assembled frame before writing.
# ---------------------------------------------------------------------------

def validate_rows(df):
    missing = set(SCHEMA_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    df = df[SCHEMA_COLUMNS]
    if not pd.api.types.is_numeric_dtype(df["value"]):
        raise ValueError("`value` must be numeric")
    return df

# ---------------------------------------------------------------------------
# 4. Write the verification tables (raw + parsed) to raw_extracted/.
# ---------------------------------------------------------------------------

def write_verification(raw_df, parsed_df, pdf_stem, raw_extracted_dir):
    """Write the two eyeball-verification tables to raw_extracted/<pdf_stem>/.

    raw_df    : table mirroring the PDF (packed 'mean (sd)' cells)
    parsed_df : same data with mean/sd/median split into columns
    """
    out_dir = Path(raw_extracted_dir) / pdf_stem
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path    = out_dir / f"{pdf_stem}_verify_raw.csv"
    parsed_path = out_dir / f"{pdf_stem}_verify_parsed.csv"
    raw_df.to_csv(raw_path, index=False)
    parsed_df.to_csv(parsed_path, index=False)
    print(f"verification (raw)    -> {raw_path}")
    print(f"verification (parsed) -> {parsed_path}")

# ---------------------------------------------------------------------------
# 5. Write the long-format CSV to consolidated/ (with hardcoding warning).
# ---------------------------------------------------------------------------

def write_consolidated(rows, hardcoded, pdf_stem, consolidated_dir):
    """Validate rows and write the long-format CSV to consolidated/<pdf_stem>/.

    If hardcoded is True, also emit a loud warning + a *.HARDCODED_WARNING.txt
    so a non-PDF-read can never pass silently.
    """
    df = validate_rows(pd.DataFrame(rows))
    out_dir = Path(consolidated_dir) / pdf_stem
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{pdf_stem}_long.csv"
    df.to_csv(out, index=False)
    print(f"consolidated long-format -> {out}")

    warn = out_dir / f"{pdf_stem}.HARDCODED_WARNING.txt"
    if hardcoded:
        msg = ("WARNING: values for this publication were HARDCODED (typed by hand), "
               "NOT read from the PDF. Verify manually before use.")
        print("!!! " + msg)
        warn.write_text(msg + "\n")
    elif warn.exists():
        warn.unlink()
    return df

# ---------------------------------------------------------------------------
# 6. Wrapper: run a paper-specific extractor, then write both outputs.
# ---------------------------------------------------------------------------

def run_extraction(pdf_path, extractor, raw_extracted_dir, consolidated_dir):
    """Full step-1 for one paper: parse PDF -> verification view + long-format.

    `extractor` returns (raw_df, parsed_df, rows, hardcoded_flag).
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



