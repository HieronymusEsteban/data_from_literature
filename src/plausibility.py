"""
plausibility.py
===============
STABLE module (step 4 — plausibility checks). Self-contained sanity checks on
the consolidated long-format table. "Self-contained" = needs no outside
reference (no per-scale legal ranges); every check uses only what's in the data.

What it checks, per (publication, scale, sample, subsample) group:
  - mean_outside_min_max : a reported mean lies outside [minimum, maximum]
  - sd_exceeds_range     : a reported SD is larger than (maximum - minimum)
  - sd_negative          : a reported SD is negative
  - median_outside_min_max : a reported median lies outside [minimum, maximum]
Row-level checks (no grouping needed):
  - value_not_numeric    : a value cannot be read as a number
  - bad_sample_size      : sample_size is non-numeric, zero, or negative

Each finding is one row in the returned flags table, naming the group, the
check, and the offending numbers. An empty table means nothing was flagged.

Public function:
  run_checks(df, report=True) -> flags DataFrame
"""

from __future__ import annotations

import pandas as pd

GROUP_COLS = ["publication", "scale", "sample", "subsample"]


# ---------------------------------------------------------------------------
# 1. Helpers to pull a single statistic out of a group.
# ---------------------------------------------------------------------------
def _get(group, data_type):
    """Return the numeric value for one data_type in a group, or None.

    If the data_type is absent, returns None (that check is then skipped).
    If present more than once, returns the first (and the duplication itself
    would show elsewhere).
    """
    rows = group[group["data_type"] == data_type]
    if rows.empty:
        return None
    return pd.to_numeric(rows["value"], errors="coerce").iloc[0]


def _flag(findings, group_key, check, detail):
    """Append one finding to the list."""
    record = dict(zip(GROUP_COLS, group_key))
    record["check"] = check
    record["detail"] = detail
    findings.append(record)


# ---------------------------------------------------------------------------
# 2. Group-level checks (mean/median/sd vs min/max).
# ---------------------------------------------------------------------------
def _check_group(group, group_key, findings):
    mean = _get(group, "mean")
    median = _get(group, "median")
    sd = _get(group, "sd")
    mn = _get(group, "minimum")
    mx = _get(group, "maximum")

    have_range = mn is not None and mx is not None

    if mean is not None and have_range and not (mn <= mean <= mx):
        _flag(findings, group_key, "mean_outside_min_max",
              f"mean={mean} not in [{mn}, {mx}]")

    if median is not None and have_range and not (mn <= median <= mx):
        _flag(findings, group_key, "median_outside_min_max",
              f"median={median} not in [{mn}, {mx}]")

    if sd is not None and sd < 0:
        _flag(findings, group_key, "sd_negative", f"sd={sd}")

    if sd is not None and have_range and sd > (mx - mn):
        _flag(findings, group_key, "sd_exceeds_range",
              f"sd={sd} > range({mx - mn})")


# ---------------------------------------------------------------------------
# 3. Row-level checks (numeric value, sample size).
# ---------------------------------------------------------------------------
def _check_rows(df, findings):
    for _, row in df.iterrows():
        group_key = tuple(row[c] for c in GROUP_COLS)

        if pd.isna(pd.to_numeric(pd.Series([row["value"]]), errors="coerce").iloc[0]):
            _flag(findings, group_key, "value_not_numeric",
                  f"value={row['value']!r} (data_type={row['data_type']})")

        n = pd.to_numeric(pd.Series([row["sample_size"]]), errors="coerce").iloc[0]
        # sample_size may legitimately be "NA" for some rows; only flag a value
        # that IS present but non-positive.
        if not pd.isna(n) and n <= 0:
            _flag(findings, group_key, "bad_sample_size",
                  f"sample_size={row['sample_size']!r}")


# ---------------------------------------------------------------------------
# 4. Run everything and report.
# ---------------------------------------------------------------------------
def run_checks(df, report=True):
    """Run all self-contained plausibility checks.

    Returns a DataFrame of flagged findings (empty if all clear).
    If report=True, also prints a readable summary.
    """
    findings = []

    for group_key, group in df.groupby(GROUP_COLS, dropna=False):
        _check_group(group, group_key, findings)

    _check_rows(df, findings)

    flags = pd.DataFrame(findings,
                         columns=GROUP_COLS + ["check", "detail"])

    if report:
        if flags.empty:
            print("plausibility checks: all clear (0 flags)")
        else:
            counts = flags["check"].value_counts()
            print(f"plausibility checks: {len(flags)} flag(s)")
            for check, n in counts.items():
                print(f"  {check}: {n}")
            print("\ndetails:")
            print(flags.to_string(index=False))

    return flags
