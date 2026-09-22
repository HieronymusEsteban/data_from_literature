"""
query.py
========
SQL-like querying of the consolidated long-format table, for a biologist who
thinks in SELECT ... WHERE terms. No SQL, no query strings: you pass plain
column=value filters.

Think of each function as one SQL idea:
  select()    -> SELECT * WHERE col=value AND col=value ...
  distinct()  -> SELECT DISTINCT col
  overview()  -> a quick "what is in this table?" summary

All functions RETURN a dataframe (so you can keep working with the result).
They do not print unless you ask (show=True), so the notebook stays tidy.
"""

import pandas as pd


# ---------------------------------------------------------------------------
# SELECT ... WHERE col=value AND col=value ...
# ---------------------------------------------------------------------------
def select(df, show=False, **filters):
    """Return the rows of `df` that match ALL the given column=value filters.

    Each keyword is a column name; its value is what that column must equal.
    A value may be a single value, or a list/tuple to mean "any of these"
    (like SQL's IN).

    Examples
    --------
    select(df, scale="DES_T", data_type="mean")
    select(df, sample_type="patients", subsample="taxon")
    select(df, data_type=["mean", "median"])          # IN-style

    Set show=True to also print the result.
    """
    # Guard against a mistyped column name: fail loudly instead of silently
    # returning nothing.
    unknown = set(filters) - set(df.columns)
    if unknown:
        raise KeyError(f"unknown column(s): {sorted(unknown)}. "
                       f"available: {list(df.columns)}")

    # Start with "keep every row", then narrow down one filter at a time.
    keep = pd.Series(True, index=df.index)
    for column, wanted in filters.items():
        if isinstance(wanted, (list, tuple, set)):
            keep = keep & df[column].isin(wanted)      # column IN (...)
        else:
            keep = keep & (df[column] == wanted)       # column = value

    result = df[keep]

    if show:
        if result.empty:
            print("(no rows match)")
        else:
            print(f"{len(result)} row(s) match")
            print(result.to_string(index=False))

    return result


# ---------------------------------------------------------------------------
# SELECT DISTINCT col
# ---------------------------------------------------------------------------
def distinct(df, column):
    """Return the sorted unique values in one column.

    Handy for discovering what you can filter on, e.g. distinct(df, "scale").
    """
    if column not in df.columns:
        raise KeyError(f"unknown column: {column!r}. available: {list(df.columns)}")
    return sorted(df[column].dropna().unique().tolist(), key=str)


# ---------------------------------------------------------------------------
# A quick "what's in this table?" summary.
# ---------------------------------------------------------------------------
def overview(df):
    """Return a small dataframe: for a few key columns, how many distinct values.

    A fast orientation before you start querying.
    """
    key_columns = ["publication", "scale", "subscale", "record_type",
                   "sample_type", "subsample", "data_type"]
    rows = []
    for col in key_columns:
        if col in df.columns:
            rows.append({"column": col,
                         "distinct_values": df[col].nunique(dropna=True)})
    return pd.DataFrame(rows)
