"""
plausibility.py
===============
Self-contained sanity checks on the consolidated long-format table.
"Self-contained" means: no outside reference is needed (no per-scale legal
ranges). Every check only uses numbers already present in the data.
 
WHAT COUNTS AS ONE "MEASUREMENT"
--------------------------------
A single measurement is identified by ALL of these columns together:
 
    publication, scale, subscale, record_type, sample_type, subsample
 
This matters. After normalization, `scale` alone is NOT enough to tell an
item apart from a subscale or a total (they can share the same scale name,
e.g. "CTQ_SF"). If we grouped only by scale, we would wrongly compare an
item's mean against a total's min/max. Including `subscale` and `record_type`
keeps items, subscales, and totals separate, so every check compares like
with like.
 
Within one such measurement group, the rows differ by `data_type`
(mean, median, sd, minimum, maximum, ...). The checks look at those.
 
CHECKS PERFORMED
----------------
Group-level (need several data_types of the same measurement):
  - mean_outside_min_max   : mean not within [minimum, maximum]
  - median_outside_min_max : median not within [minimum, maximum]
  - sd_negative            : sd is below 0
  - sd_exceeds_range       : sd is larger than (maximum - minimum)
 
Row-level (each row on its own):
  - value_not_numeric      : the value cannot be read as a number
  - bad_sample_size        : sample_size is present but zero or negative
 
Each problem found becomes one row in the returned "flags" table.
An empty flags table means nothing was flagged.
 
MAIN FUNCTION
-------------
  run_checks(df, report=True) -> flags DataFrame
"""
 
import pandas as pd
 
 
# The columns that together identify one distinct measurement.
# (See the module docstring for why all of these are needed.)
GROUP_COLS = ["publication", "scale", "subscale", "record_type",
              "sample_type", "subsample"]
 
 
# ---------------------------------------------------------------------------
# Small helper: read one statistic (e.g. the mean) out of a measurement group.
# ---------------------------------------------------------------------------
def get_statistic(group, data_type):
    """Return the numeric value of one data_type within a group.
 
    `group` is the set of rows for one measurement.
    `data_type` is e.g. "mean", "sd", "minimum", "maximum".
 
    Returns the number if that data_type is present, otherwise None
    (so the caller can simply skip a check when a piece is missing).
    """
    matching_rows = group[group["data_type"] == data_type]
    if matching_rows.empty:
        return None
    # Convert to a number; if it can't be converted this becomes NaN.
    value = pd.to_numeric(matching_rows["value"], errors="coerce").iloc[0]
    if pd.isna(value):
        return None
    return value
 
 
# ---------------------------------------------------------------------------
# Small helper: turn a group's key into a labelled dict, and record a problem.
# ---------------------------------------------------------------------------
def make_flag(group_key, check_name, detail):
    """Build one flag record (a dict) describing a single problem found."""
    flag = dict(zip(GROUP_COLS, group_key))   # publication, scale, ... labelled
    flag["check"] = check_name
    flag["detail"] = detail
    return flag
 
 
# ---------------------------------------------------------------------------
# The group-level checks: compare mean / median / sd against min / max.
# ---------------------------------------------------------------------------
def check_one_group(group, group_key):
    """Return a list of flags for one measurement group (may be empty)."""
    flags = []
 
    mean = get_statistic(group, "mean")
    median = get_statistic(group, "median")
    sd = get_statistic(group, "sd")
    minimum = get_statistic(group, "minimum")
    maximum = get_statistic(group, "maximum")
 
    # We can only do range checks if BOTH minimum and maximum were reported.
    have_range = (minimum is not None) and (maximum is not None)
 
    # Check 1: mean must lie within [minimum, maximum].
    if mean is not None and have_range:
        if not (minimum <= mean <= maximum):
            flags.append(make_flag(
                group_key, "mean_outside_min_max",
                f"mean={mean} not in [{minimum}, {maximum}]"))
 
    # Check 2: median must lie within [minimum, maximum].
    if median is not None and have_range:
        if not (minimum <= median <= maximum):
            flags.append(make_flag(
                group_key, "median_outside_min_max",
                f"median={median} not in [{minimum}, {maximum}]"))
 
    # Check 3: a standard deviation cannot be negative.
    if sd is not None and sd < 0:
        flags.append(make_flag(
            group_key, "sd_negative", f"sd={sd}"))
 
    # Check 4: sd should not exceed the full range (max - min).
    if sd is not None and have_range and sd > (maximum - minimum):
        flags.append(make_flag(
            group_key, "sd_exceeds_range",
            f"sd={sd} > range({maximum - minimum})"))
 
    return flags
 
 
# ---------------------------------------------------------------------------
# The row-level checks: numeric value, and a sane sample size.
# ---------------------------------------------------------------------------
def check_one_row(row):
    """Return a list of flags for a single row (may be empty)."""
    flags = []
    group_key = tuple(row[column] for column in GROUP_COLS)
 
    # Check 5: the value should be a number.
    numeric_value = pd.to_numeric(row["value"], errors="coerce")
    if pd.isna(numeric_value):
        flags.append(make_flag(
            group_key, "value_not_numeric",
            f"value={row['value']!r} (data_type={row['data_type']})"))
 
    # Check 6: sample_size, if present, must be positive.
    # It may legitimately be missing ("NA"); we only flag a real number <= 0.
    numeric_n = pd.to_numeric(row["sample_size"], errors="coerce")
    if not pd.isna(numeric_n) and numeric_n <= 0:
        flags.append(make_flag(
            group_key, "bad_sample_size",
            f"sample_size={row['sample_size']!r}"))
 
    return flags
 
 
# ---------------------------------------------------------------------------
# Run all checks and (optionally) print a readable report.
# ---------------------------------------------------------------------------
def run_checks(df, report=True):
    """Run every plausibility check on the whole table.
 
    Returns a DataFrame of flags (one row per problem found; empty if none).
    If report=True, also prints a short summary.
    """
    all_flags = []
 
    # Group-level checks: one measurement group at a time.
    for group_key, group in df.groupby(GROUP_COLS, dropna=False):
        all_flags.extend(check_one_group(group, group_key))
 
    # Row-level checks: one row at a time.
    for _, row in df.iterrows():
        all_flags.extend(check_one_row(row))
 
    flags = pd.DataFrame(all_flags, columns=GROUP_COLS + ["check", "detail"])
 
    if report:
        if flags.empty:
            print("plausibility checks: all clear (0 flags)")
        else:
            print(f"plausibility checks: {len(flags)} flag(s)")
            for check_name, count in flags["check"].value_counts().items():
                print(f"  {check_name}: {count}")
            print("\ndetails:")
            print(flags.to_string(index=False))
 
    return flags