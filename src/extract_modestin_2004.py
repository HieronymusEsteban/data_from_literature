import re
import pandas as pd
import pdfplumber

from scaffold import make_row, split_paren

PUBLICATION = "Modestin & Erni 2004 (doi:10.1016/j.psychres.2001.12.001)"
SCALE = "DES-T"
TABLE_PAGE_INDEX = 3            # Table 1 is on PDF page 4 (0-based index 3)
HARDCODED = False              # set True only if you give up and type values by hand

# printed row label -> (sample, subsample). sample=None means "use current block".
ROW_MAP = {
    "Nonpatients": ("healthy_controls", "whole_sample"),
    "Patients":    ("patients",          "whole_sample"),
    "T":           (None,                "taxon_member"),
    "Non-T":       (None,                "non_taxon_member"),
}


def _read_table_lines(pdf_path):
    """Return the six data lines of Table 1 as token lists, with block tracking."""
    page = pdfplumber.open(pdf_path).pages[TABLE_PAGE_INDEX]
    parsed, current_sample = [], None
    for line in page.extract_text().split("\n"):
        toks = line.split()
        if not toks or toks[0] not in ROW_MAP or len(toks) != 9:
            continue
        sample, subsample = ROW_MAP[toks[0]]
        if sample is not None:
            current_sample = sample
        parsed.append((current_sample, subsample, toks))
    return parsed


def _build_dataframes(table_lines):
    """From token lists build (raw_df packed, parsed_df split)."""
    raw_records, parsed_records = [], []
    for sample, subsample, toks in table_lines:
        # DES-T columns by position: tok[5]='mean(sd)', tok[6]=median ; n from tok[1]='n(%)'
        n = int(re.match(r"^(\d+)", toks[1]).group(1))
        mean, sd = split_paren(toks[5])
        median = float(toks[6])
        # raw view: keep the packed cell exactly, with a space inserted for readability
        packed = toks[5].replace("(", " (")
        raw_records.append({
            "row_label": toks[0], "sample": sample, "subsample": subsample,
            "N (%)": toks[1].replace("(", " ("),
            "DES-T Mn (S.D.)": packed, "DES-T Md": median,
        })
        parsed_records.append({
            "sample": sample, "subsample": subsample, "n": n,
            "mean": mean, "sd": sd, "median": median,
        })
    return pd.DataFrame(raw_records), pd.DataFrame(parsed_records)


def _rows_for_group(sample, subsample, n, mean, sd, median):
    stats = {"mean": mean, "sd": sd, "median": median}
    return [make_row(PUBLICATION, SCALE, dt, sample,
                     value=stats[dt], subsample=subsample, sample_size=n)
            for dt in ("mean", "sd", "median")]


def extract(pdf_path):
    """Return (raw_df, parsed_df, rows, hardcoded_flag)."""
    table_lines = _read_table_lines(pdf_path)
    raw_df, parsed_df = _build_dataframes(table_lines)
    rows = []
    for _, r in parsed_df.iterrows():
        rows.extend(_rows_for_group(r["sample"], r["subsample"],
                                    int(r["n"]), r["mean"], r["sd"], r["median"]))
    return raw_df, parsed_df, rows, HARDCODED