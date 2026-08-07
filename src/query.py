"""
query.py
========
STABLE module (step 4 — selection). SQL-like querying of the consolidated
long-format table, by column values. No SQL and no query strings: you pass
plain column=value filters, like a SELECT ... WHERE in SQL.

Typical use (in a notebook):

    import pandas as pd
    from query import select

    df = pd.read_csv("data/all_consolidated.csv")

    # SELECT * WHERE scale='DES-T' AND sample='patients' AND data_type='mean'
    select(df, scale="DES-T", sample="patients", data_type="mean")

By default it prints a readable table AND returns the filtered dataframe, so you
can either just look, or keep the result for further work.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# 1. Core selection by column = value (the SQL-like WHERE).
# ---------------------------------------------------------------------------
def select(df, show=False, max_show=50, **filters):
    """Return rows of `df` matching ALL the given column=value filters.

    Parameters
    ----------
    df : pandas.DataFrame
        The consolidated table.
    show : bool
        If True, print a readable table of the result.
    max_show : int
        Cap on how many rows to print (the full result is still returned).
    **filters :
        column=value pairs. A value may be a single value (scale="DES-T")
        or a list/tuple of accepted values (sample=["patients", "community"]),
        which acts like SQL's IN (...).

    Returns
    -------
    pandas.DataFrame  (the filtered rows; original is not modified)

    Examples
    --------
    select(df, scale="DES-T", data_type="mean")
    select(df, sample=["patients", "community"])     # IN-style
    """
    # Guard against typos in column names — fail loudly, not silently empty.
    unknown = set(filters) - set(df.columns)
    if unknown:
        raise KeyError(f"unknown column(s): {sorted(unknown)}. "
                       f"available: {list(df.columns)}")

    mask = pd.Series(True, index=df.index)
    for column, wanted in filters.items():
        if isinstance(wanted, (list, tuple, set)):
            mask &= df[column].isin(wanted)        # column IN (...)
        else:
            mask &= df[column] == wanted           # column = value

    result = df[mask]

    if show:
        if result.empty:
            print("(no rows match)")
        else:
            print(f"{len(result)} row(s) match:")
            print(result.head(max_show).to_string(index=False))
            if len(result) > max_show:
                print(f"... ({len(result) - max_show} more rows not shown)")

    return result


# ---------------------------------------------------------------------------
# 2. Convenience: list the distinct values available in a column.
# ---------------------------------------------------------------------------
def distinct(df, column):
    """Show the unique values in a column — handy for knowing what to filter on.

    E.g. distinct(df, "scale") tells you which scales are in the table.
    """
    if column not in df.columns:
        raise KeyError(f"unknown column: {column!r}. available: {list(df.columns)}")
    values = sorted(df[column].dropna().unique().tolist(), key=str)
    # print(f"{column}: {values}")
    return values
