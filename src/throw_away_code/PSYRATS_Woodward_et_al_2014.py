"""
PSYRATS_Woodward_et_al_2014.py
==============================
Per-paper extractor for:

    Woodward et al. 2014, "Symptom Dimensions of the Psychotic Symptom Rating
    Scales in Psychosis: A Multisite Study", Schizophrenia Bulletin
    40(suppl 4):S265-S274. PSYRATS AHS and DS subscale total scores from Table 1.

Reads Table 1 DIRECTLY from the PDF (pdfplumber) and returns rows for the
normalized schema via scaffold.make_row().

WHY THIS PAPER NEEDED RE-EXTRACTION
-----------------------------------
Table 1 reports a SEPARATE sample size for each subscale (AHS has its own N,
DS has its own N), and they differ (e.g. site 8 London: AHS N=219, DS N=280).
So a site's AHS and DS are DIFFERENT subsamples. The subsample name therefore
includes the subscale, so each is unique and carries its own N:
    site{site}_{location}_{subscale}   e.g. "site8_London_DS"

TABLE 1 LAYOUT (page S267, 0-based PDF page index 2)
----------------------------------------------------
Each site row, after pdfplumber text extraction, is 14 whitespace tokens:

  token[0]  site number
  token[1]  testing location
  token[2]  AHS (N)          <- we use this
  token[3]  Age  (ignored)
  token[4]  DI   (ignored)
  token[5]  AHS Total        <- we use this  (mean AHS total score)
  token[6]  DS (N)           <- we use this
  token[7]  Age  (ignored)
  token[8]  DI   (ignored)
  token[9]  DS Total         <- we use this  (mean DS total score)
  token[10] AHS+DS (N)   (ignored — not recorded for this project)
  token[11] Age  (ignored)
  token[12] DI   (ignored)
  token[13] AHS+DS Total (ignored)

Absent blocks are filled with "n/a"; a subscale row is emitted only when that
subscale's N and Total are both numeric (not "n/a").

CONFIRMED NORMALIZATION (from the user)
---------------------------------------
  scale = "PSYRATS"; subscales "AHS" and "DS"; record_type = "subscale"
  scale_old = "PSYRATS_AHS" / "PSYRATS_DS" (label close to the paper)
  scoring_rule = "raw_sum" (paper, Table 1 note, p.S267: "Total score is
    computed by summing all items on the respective scales.")
  sample_type = "patients" (psychosis/schizophrenia patients; no controls)
  subsample = site{site}_{location}_{subscale}; no items; no redundant aggregates
"""

import pdfplumber

from scaffold import make_row

PUBLICATION = "Woodward et al. 2014"
SCALE = "PSYRATS"
TABLE_PAGE_INDEX = 2          # Table 1 is on PDF page S267 (0-based index 2)
HARDCODED = False
SCORING_RULE = "raw_sum"

# The locations that mark a valid data row (its first token is the site number).
LOCATIONS = {"Utrecht", "Perth", "Bern", "London", "Montreal",
             "Vancouver", "Swansea", "Cagliari", "Chicago"}

# Which token positions hold each subscale's N and Total.
# subscale -> (N token index, Total token index)
SUBSCALE_TOKENS = {
    "AHS": (2, 5),
    "DS":  (6, 9),
}


# ---------------------------------------------------------------------------
# Read Table 1's site rows from the PDF.
# ---------------------------------------------------------------------------
def _read_table(pdf_path):
    """Return a list of dicts, one per (site x subscale) that has data.

    Each dict: site, location, subscale, n, total.
    A subscale is only included for a site when both its N and Total are
    numeric (the paper writes 'n/a' where a subscale was not collected).
    """
    page = pdfplumber.open(pdf_path).pages[TABLE_PAGE_INDEX]

    records = []
    for line in page.extract_text().split("\n"):
        tokens = line.split()
        # a data row: first token a number, second token a known location
        if len(tokens) < 10 or not tokens[0].isdigit() or tokens[1] not in LOCATIONS:
            continue

        site = tokens[0]
        location = tokens[1]

        for subscale, (n_idx, total_idx) in SUBSCALE_TOKENS.items():
            n_raw = tokens[n_idx]
            total_raw = tokens[total_idx]
            # skip a subscale the site did not report ("n/a")
            if n_raw == "n/a" or total_raw == "n/a":
                continue
            records.append({
                "site": site,
                "location": location,
                "subscale": subscale,
                "n": int(n_raw),
                "total": float(total_raw),
            })
    return records


# ---------------------------------------------------------------------------
# Build the two verification views (raw packed + parsed).
# ---------------------------------------------------------------------------
def _build_verification(records):
    import pandas as pd

    # RAW view: one row per site, AHS and DS side by side (n/a where absent).
    by_site = {}
    for r in records:
        by_site.setdefault((r["site"], r["location"]), {})[r["subscale"]] = r

    raw_rows = []
    for (site, location), subs in sorted(by_site.items(), key=lambda x: int(x[0][0])):
        ahs = subs.get("AHS")
        ds = subs.get("DS")
        raw_rows.append({
            "Site": site, "Testing Location": location,
            "AHS (N)": ahs["n"] if ahs else "n/a",
            "AHS Total": ahs["total"] if ahs else "n/a",
            "DS (N)": ds["n"] if ds else "n/a",
            "DS Total": ds["total"] if ds else "n/a",
        })
    raw_df = pd.DataFrame(raw_rows)

    # PARSED view: one row per subsample (site x subscale), with its own N.
    parsed_df = pd.DataFrame([{
        "subsample": f"site{r['site']}_{r['location']}_{r['subscale']}",
        "subscale": r["subscale"],
        "sample_size": r["n"],
        "value": r["total"],
    } for r in records])

    return raw_df, parsed_df


# ---------------------------------------------------------------------------
# Turn one (site x subscale) record into its long-format row.
# ---------------------------------------------------------------------------
def _row_for_record(r):
    """Emit the single subscale-total long-format row for one table cell."""
    subsample = f"site{r['site']}_{r['location']}_{r['subscale']}"
    return make_row(
        publication=PUBLICATION,
        scale_old=f"PSYRATS_{r['subscale']}",
        data_type="mean",                 # the reported total score is a mean
        sample_type="patients",
        value=r["total"],
        scale=SCALE,
        record_type="subscale",
        subsample=subsample,
        sample_size=r["n"],
        subscale=r["subscale"],
        scoring_rule=SCORING_RULE,
        redundant_aggregate=False,
    )


# ---------------------------------------------------------------------------
# The entry point the scaffold calls.
# ---------------------------------------------------------------------------
def extract(pdf_path):
    """Return (raw_df, parsed_df, rows, hardcoded_flag)."""
    records = _read_table(pdf_path)
    raw_df, parsed_df = _build_verification(records)
    rows = [_row_for_record(r) for r in records]
    return raw_df, parsed_df, rows, HARDCODED
