"""
DES_T_Modestin_et_al_2004.py
============================
Per-paper extractor for:

    Modestin & Erni 2004, "Testing the dissociative taxon",
    Psychiatry Research 126:77-82. DES-T scores from Table 1.

Reads the DES-T columns of Table 1 DIRECTLY from the PDF (pdfplumber) and
returns rows for the normalized schema via scaffold.make_row().

TABLE 1 LAYOUT (page 4, 0-based index 3)
----------------------------------------
Each data row, after pdfplumber's text extraction, is 9 whitespace tokens:

  token[0] : row label  (Nonpatients | T | Non-T | Patients)
  token[1] : N(%)       e.g. "276(100)"   -> we take the leading integer as n
  token[2] : DES total mean(sd)   } we IGNORE the DES-total block
  token[3] : DES total median     }
  token[4] : DES total >20 n(%)   }
  token[5] : DES-T mean(sd)   e.g. "5.0(9.3)"   <- we want this
  token[6] : DES-T median     e.g. "1.7"        <- and this
  token[7] : DES-T >15 n(%)   } ignored
  token[8] : DES-T >35 n(%)   } ignored

The six data rows come in two blocks. The first block (Nonpatients, T, Non-T)
is the healthy-control sample; the second (Patients, T, Non-T) is the patient
sample. A "whole sample" header row (Nonpatients / Patients) starts each block;
the T / Non-T rows are its subsamples and PARTITION it (they sum to the whole),
so the whole-sample rows are flagged redundant_aggregate=True.

CONFIRMED NORMALIZATION (from the user)
---------------------------------------
  scale = "DES_T", subscale = "none", record_type = "total"
  whole_sample rows -> redundant_aggregate=True
  patients n = 207 (paper's abstract says 204; table/methods say 207)
  no individual-item rows
"""

import re

import pdfplumber

from scaffold import make_row, split_paren

PUBLICATION = "Modestin & Erni 2004"
SCALE = "DES_T"
TABLE_PAGE_INDEX = 3          # Table 1 is on PDF page 4 (0-based index 3)
HARDCODED = False             # values are parsed straight from the PDF

# Row label -> (sample_type, subsample). sample_type=None means "whole-sample
# header row that opens a block"; the current block's sample_type is used.
ROW_MAP = {
    "Nonpatients": ("healthy_controls", "whole_sample"),
    "Patients":    ("patients",          "whole_sample"),
    "T":           (None,                "taxon"),
    "Non-T":       (None,                "non_taxon"),
}


# ---------------------------------------------------------------------------
# Read the six DES-T data rows from Table 1.
# ---------------------------------------------------------------------------
def _read_table(pdf_path):
    """Return a list of dicts, one per data row, with the DES-T numbers.

    Each dict: sample_type, subsample, n, mean, sd, median, is_whole.
    """
    page = pdfplumber.open(pdf_path).pages[TABLE_PAGE_INDEX]

    records = []
    current_sample_type = None
    for line in page.extract_text().split("\n"):
        tokens = line.split()
        # A data row starts with a known label AND has all 9 columns.
        if not tokens or tokens[0] not in ROW_MAP or len(tokens) != 9:
            continue

        sample_type, subsample = ROW_MAP[tokens[0]]
        is_whole = sample_type is not None
        if is_whole:
            current_sample_type = sample_type   # a header row opens a block

        n = int(re.match(r"^(\d+)", tokens[1]).group(1))   # leading int of "276(100)"
        mean, sd = split_paren(tokens[5])                  # DES-T "mean(sd)"
        median = float(tokens[6])                          # DES-T median

        records.append({
            "sample_type": current_sample_type,
            "subsample": subsample,
            "n": n,
            "mean": mean,
            "sd": sd,
            "median": median,
            "is_whole": is_whole,
        })
    return records


# ---------------------------------------------------------------------------
# Build the two verification views (raw packed + parsed).
# ---------------------------------------------------------------------------
def _build_verification(records):
    import pandas as pd

    raw_rows, parsed_rows = [], []
    for r in records:
        raw_rows.append({
            "Probands": r["subsample"] if not r["is_whole"] else r["sample_type"],
            "N": r["n"],
            "DES-T Mn (S.D.)": f"{r['mean']} ({r['sd']})",
            "DES-T Md": r["median"],
        })
        parsed_rows.append({
            "sample_type": r["sample_type"],
            "subsample": r["subsample"],
            "n": r["n"],
            "mean": r["mean"],
            "sd": r["sd"],
            "median": r["median"],
        })
    return pd.DataFrame(raw_rows), pd.DataFrame(parsed_rows)


# ---------------------------------------------------------------------------
# Turn one data row into its long-format rows (mean, sd, median).
# ---------------------------------------------------------------------------
def _rows_for_record(r):
    """Emit the mean / sd / median long-format rows for one table row."""
    stats = {"mean": r["mean"], "sd": r["sd"], "median": r["median"]}
    out = []
    for data_type in ("mean", "sd", "median"):
        out.append(make_row(
            publication=PUBLICATION,
            scale_old="DES-T",              # label as written in the paper
            data_type=data_type,
            sample_type=r["sample_type"],
            value=stats[data_type],
            scale=SCALE,                    # confirmed normalized name
            record_type="total",            # all rows here are total scores
            subsample=r["subsample"],
            sample_size=r["n"],
            subscale="none",
            # whole-sample rows are redundant with their T / Non-T subsamples
            redundant_aggregate=r["is_whole"],
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
