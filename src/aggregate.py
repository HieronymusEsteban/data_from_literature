"""
aggregate.py
============
Combines per-paper values from the consolidated table into summary values,
using a SAMPLE-SIZE-WEIGHTED average across papers:

    weighted_average = sum(value_i * n_i) / sum(n_i)

Bigger studies get proportionally more influence. The result reports what was
aggregated (mean_of_means or mean_of_medians) so it is never ambiguous.

WHAT IT AGGREGATES
------------------
Only `mean` and `median` are allowed. `sd`, `minimum`, `maximum` are refused,
because averaging those across studies is not statistically meaningful
(you cannot recover a pooled SD by averaging SDs).

Note on medians: a weighted mean of medians is a reasonable summary, but it is
NOT the true median of the pooled data (that would need the raw data, which we
do not have). The output labels it `mean_of_medians` to make this explicit.

DEFAULT GROUPING (most granular)
--------------------------------
    scale, subscale, record_type, sample_type, subsample

This keeps every smallest subsample as its own result row — the safe starting
point. To aggregate UPWARD (e.g. pool all subsamples of a sample_type), pass a
coarser `group_cols` that omits `subsample`.

`scoring_rule` is deliberately NOT in the grouping: it is often undefined in the
source papers, and we still want to include those studies.

REDUNDANT ROWS
--------------
Rows flagged `redundant_aggregate == True` (whole-sample values that overlap
their own subsamples) are removed before aggregating, so people are not counted
twice.

MAIN FUNCTION
-------------
  aggregate(df, data_type="mean") -> DataFrame
"""

import pandas as pd

# Only these statistics may be aggregated.
ALLOWED_DATA_TYPES = {"mean", "median"}

# The most granular default grouping.
DEFAULT_GROUP_COLS = ["scale", "subscale", "record_type",
                      "sample_type", "subsample"]


# ---------------------------------------------------------------------------
# The weighted average within each group.
# ---------------------------------------------------------------------------
def weighted_average_by_group(df, group_cols, value_col="value",
                              weight_col="sample_size"):
    """Sample-size-weighted average of `value_col` within each group.

    Returns one row per group with:
        weighted_value : the weighted average
        n_studies      : how many rows (papers) went into the group
        total_n        : the summed sample size of the group
    Rows with a missing value or weight are dropped first (with a note).
    """
    work = df.copy()

    # Weights and values must be numeric; anything unparseable becomes NaN.
    work[weight_col] = pd.to_numeric(work[weight_col], errors="coerce")
    work[value_col] = pd.to_numeric(work[value_col], errors="coerce")

    before = len(work)
    work = work.dropna(subset=[weight_col, value_col])
    dropped = before - len(work)
    if dropped:
        print(f"note: dropped {dropped} row(s) with missing value/weight")

    results = []
    for group_key, group in work.groupby(group_cols, dropna=False):
        weights = group[weight_col]
        values = group[value_col]
        weighted_value = (values * weights).sum() / weights.sum()

        # group_key is a single value if grouping on one column, else a tuple.
        if not isinstance(group_key, tuple):
            group_key = (group_key,)

        row = dict(zip(group_cols, group_key))
        row["weighted_value"] = weighted_value
        row["n_studies"] = len(group)
        row["total_n"] = weights.sum()
        results.append(row)

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# The main entry point: pick a data_type, filter, then aggregate.
# ---------------------------------------------------------------------------
def aggregate(df, data_type="mean", group_cols=None):
    """Weighted-average one statistic across papers, grouped.

    Parameters
    ----------
    df : DataFrame
        The consolidated table.
    data_type : "mean" or "median"
        Which statistic to aggregate. Anything else is refused.
    group_cols : list of column names, optional
        Grouping columns. Defaults to the most granular grouping
        (scale, subscale, record_type, sample_type, subsample).
        Pass a shorter list to aggregate upward.

    Returns
    -------
    DataFrame with the group columns plus weighted_value, n_studies, total_n,
    and an `aggregated_stat` column recording what was computed
    (e.g. "mean_of_means", "mean_of_medians").
    """
    # Refuse statistics that must not be averaged across studies.
    if data_type not in ALLOWED_DATA_TYPES:
        raise ValueError(
            f"data_type {data_type!r} cannot be aggregated. "
            f"Allowed: {sorted(ALLOWED_DATA_TYPES)}. "
            "(SD / minimum / maximum are excluded on purpose.)")

    if group_cols is None:
        group_cols = DEFAULT_GROUP_COLS

    # 1. Keep only rows of the requested statistic.
    subset = df[df["data_type"] == data_type]
    if subset.empty:
        raise ValueError(f"no rows with data_type == {data_type!r}")

    # 2. Drop redundant whole-sample rows so people are not counted twice.
    #    (Only if the column exists — older data may not have it.)
    if "redundant_aggregate" in subset.columns:
        subset = subset[subset["redundant_aggregate"] != True]  # noqa: E712

    # 3. Weighted average within each group.
    result = weighted_average_by_group(subset, group_cols)

    # 4. Record what was aggregated, so the output is self-explaining.
    result["aggregated_stat"] = f"mean_of_{data_type}s"

    return result
