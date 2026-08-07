"""
aggregate.py
============
STABLE module (step 4 — aggregation). Combines per-paper values from the
consolidated long-format table into summary values.

Main operation: a SAMPLE-SIZE-WEIGHTED mean of means across papers. When several
papers each report a mean for the same (scale, sample), simply averaging those
means treats a study of n=20 the same as a study of n=500. Weighting by
sample_size gives larger studies proportionally more influence:

    weighted_mean = sum(value_i * n_i) / sum(n_i)

Default grouping is by (scale, sample); you can change it. You choose which
data_type to aggregate (e.g. only the rows where data_type == "mean").

For MANUAL selection instead of group-by, pre-filter with query.select() and
pass the result in — aggregation will then operate on just those rows.

Public functions:
  weighted_mean_by_group() - the weighted mean of means, grouped.
  aggregate()              - convenience wrapper with data_type filtering.
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# 1. Weighted mean of means, grouped by chosen columns.
# ---------------------------------------------------------------------------
def weighted_mean_by_group(df, group_cols=("scale", "sample"),
                           value_col="value", weight_col="sample_size"):
    """Sample-size-weighted mean of `value_col` within each group.

    Parameters
    ----------
    df : DataFrame
        Rows to aggregate (already filtered to one data_type — see aggregate()).
    group_cols : sequence of column names
        The grouping. Default ("scale", "sample"): one result row per
        scale-and-sample combination.
    value_col, weight_col : str
        Columns holding the value and the weight (sample size).

    Returns
    -------
    DataFrame with the group columns plus:
        weighted_mean : the weighted mean of means
        n_studies     : how many papers (rows) went into each group
        total_n       : the summed sample size of the group
    Rows whose weight is missing/non-numeric are dropped, with a note.
    """
    group_cols = list(group_cols)

    work = df.copy()
    # weights must be numeric; "NA" or blanks can't be weighted.
    work[weight_col] = pd.to_numeric(work[weight_col], errors="coerce")
    before = len(work)
    work = work.dropna(subset=[weight_col, value_col])
    dropped = before - len(work)
    if dropped:
        print(f"note: dropped {dropped} row(s) with missing value/weight")

    def _agg(group):
        w = group[weight_col]
        v = group[value_col]
        return pd.Series({
            "weighted_mean": (v * w).sum() / w.sum(),
            "n_studies": len(group),
            "total_n": w.sum(),
        })

    result = (work.groupby(group_cols, dropna=False)
                  .apply(_agg, include_groups=False)
                  .reset_index())
    return result


# ---------------------------------------------------------------------------
# 2. Convenience wrapper: pick the data_type, then aggregate.
# ---------------------------------------------------------------------------
def aggregate(df, data_type="mean", group_cols=("scale", "sample")):
    """Filter to one data_type, then weighted-mean-aggregate by group.

    Example
    -------
    # weighted mean of reported MEANS, per scale & sample:
    aggregate(df, data_type="mean")

    # aggregate a different statistic, e.g. medians, per scale only:
    aggregate(df, data_type="median", group_cols=["scale"])
    """
    if data_type is not None:
        subset = df[df["data_type"] == data_type]
        if subset.empty:
            raise ValueError(f"no rows with data_type == {data_type!r}")
    else:
        subset = df
    return weighted_mean_by_group(subset, group_cols=group_cols)
