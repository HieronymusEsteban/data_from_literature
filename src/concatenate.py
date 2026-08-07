"""
concatenate.py
==============
STABLE module (step 3 of the pipeline). Gathers all per-paper long-format CSVs
and concatenates them into ONE consolidated CSV (all scales, all papers). This
single table is what you query downstream (filter by the `scale` column, etc.).

Optionally it can also write one CSV per scale (set split_per_scale=True), but
that is an extra, not the primary output.

Public functions:
  find_long_csvs()        - locate the per-paper *_long.csv files.
  load_and_concatenate()  - read them into one dataframe (with a source column).
  write_combined()        - write the single consolidated CSV.
  split_by_scale()        - (optional) write one CSV per scale.
  consolidate()           - the wrapper: find -> concatenate -> write.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Columns every per-paper long CSV is expected to have (matches the scaffold).
EXPECTED_COLUMNS = [
    "publication", "scale", "data_type", "sample",
    "subsample", "sample_size", "value",
]


# ---------------------------------------------------------------------------
# 1. Find the per-paper long CSVs.
# ---------------------------------------------------------------------------
def find_long_csvs(input_dir, pattern="*/*_long.csv"):
    """Return a sorted list of per-paper long-format CSV paths under input_dir.

    Default pattern matches the layout
    data/consolidated/<pdf_name>/<pdf_name>_long.csv
    Change `pattern` if your files are laid out differently (e.g. "*_long.csv"
    for a flat folder).
    """
    input_dir = Path(input_dir)
    files = sorted(input_dir.glob(pattern))
    return files


# ---------------------------------------------------------------------------
# 2. Load and concatenate, tagging each row with its source file.
# ---------------------------------------------------------------------------
def load_and_concatenate(files):
    """Read each CSV, check its columns, stack into one dataframe.

    Adds a `source_file` column so every row is traceable back to the paper it
    came from (useful for the spot-check step).
    """
    if not files:
        raise ValueError("no input CSV files found — check input_dir / pattern")

    frames = []
    for f in files:
        df = pd.read_csv(f)
        missing = set(EXPECTED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"{f.name} is missing columns: {sorted(missing)}")
        df["source_file"] = f.name
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    return combined


# ---------------------------------------------------------------------------
# 3. Write the single consolidated CSV (primary output).
# ---------------------------------------------------------------------------
def write_combined(combined, output_path):
    """Write the whole concatenated dataframe to one CSV. Returns the path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)
    print(f"consolidated: {len(combined)} rows -> {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# 4. (Optional) Split by scale into one CSV per scale.
# ---------------------------------------------------------------------------
def split_by_scale(combined, output_dir):
    """Write one CSV per distinct value in the `scale` column.

    Optional extra — the single combined file is the primary output.
    Returns a dict {scale_name: written_path}.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = {}
    for scale, group in combined.groupby("scale"):
        safe = str(scale).replace("/", "-").replace(" ", "_")
        out = output_dir / f"{safe}_consolidated.csv"
        group.to_csv(out, index=False)
        written[scale] = out
        print(f"  {scale}: {len(group)} rows -> {out}")
    return written


# ---------------------------------------------------------------------------
# 5. Wrapper: find -> concatenate -> write single file (optionally split).
# ---------------------------------------------------------------------------
def consolidate(input_dir, output_path, pattern="*/*_long.csv",
                split_per_scale=False, split_dir=None):
    """Full step 3.

    input_dir       : folder holding the per-paper *_long.csv files.
    output_path     : path of the single consolidated CSV to write.
    pattern         : glob for locating the per-paper files.
    split_per_scale : if True, also write one CSV per scale.
    split_dir       : folder for the per-scale files (required if splitting).

    Returns (combined_dataframe, output_path).
    """
    files = find_long_csvs(input_dir, pattern)
    combined = load_and_concatenate(files)
    write_combined(combined, output_path)

    if split_per_scale:
        if split_dir is None:
            raise ValueError("split_dir is required when split_per_scale=True")
        print("also splitting per scale:")
        split_by_scale(combined, split_dir)

    print(f"\nconcatenated {len(files)} file(s), {len(combined)} rows total")
    return combined, output_path
