"""
concatenate.py
==============
Gathers all per-paper long-format CSVs and stacks them into ONE combined table
(all scales, all papers). That single table is what you query and aggregate.

MAIN FUNCTIONS
--------------
  consolidate()          - find per-paper CSVs, stack into one combined table.
  add_publication()      - add ONE new publication's data to the combined table:
                           assign the next pub_id and derive the illness columns
                           from pub_info_table.
"""

from pathlib import Path

import pandas as pd

EXPECTED_COLUMNS = [
    "publication", "scale_old", "data_type", "sample_type", "subsample",
    "sample_size", "value", "source_file", "scale", "subscale", "item_name",
    "record_type", "redcap_item_number", "scoring_rule", "item_score_reversed",
    "redundant_aggregate",
]


def find_long_csvs(input_dir, pattern="*/*_long.csv"):
    """Return a sorted list of per-paper long-format CSV paths under input_dir."""
    return sorted(Path(input_dir).glob(pattern))


def load_and_concatenate(files):
    """Read each CSV, check its columns, and stack them into one dataframe."""
    if not files:
        raise ValueError("no input CSV files found — check input_dir / pattern")
    frames = []
    for f in files:
        df = pd.read_csv(f)
        missing = set(EXPECTED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"{f.name} is missing columns: {sorted(missing)}")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def write_combined(combined, output_path):
    """Write the whole combined dataframe to one CSV. Returns the path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)
    print(f"consolidated: {len(combined)} rows -> {output_path}")
    return output_path


def consolidate(input_dir, output_path, pattern="*/*_long.csv"):
    """Full consolidation: find -> concatenate -> write single combined CSV."""
    files = find_long_csvs(input_dir, pattern)
    combined = load_and_concatenate(files)
    write_combined(combined, output_path)
    print(f"\nconcatenated {len(files)} file(s), {len(combined)} rows total")
    return combined, output_path


# ===========================================================================
# Adding a new publication with pub_id and illness flags
# ===========================================================================
# Two publication-level facts live in a separate table, `pub_info_table`
# (one row per publication):
#     pub_id, publication, sample_information,
#     sample_with_mental_illness, sample_with_schizophrenia
#
# When we add a new publication's data to the combined table we:
#   1. give it the next pub_id (max existing + 1),
#   2. copy pub_id onto every one of its data rows,
#   3. DERIVE the two illness columns on the data rows from pub_info_table,
#      applying the rule: the publication's flag value for `patients` rows,
#      and 0 for `healthy_controls` rows.
# Deriving (rather than typing the flags twice) means the data rows can never
# disagree with pub_info_table.


# Columns whose values come from pub_info_table and are derived per data row.
ILLNESS_COLUMNS = ["sample_with_mental_illness", "sample_with_schizophrenia"]


# ---------------------------------------------------------------------------
# Work out the next publication id.
# ---------------------------------------------------------------------------
def next_pub_id(pub_info_table):
    """Return the next integer pub_id (max existing + 1, or 0 if table empty)."""
    if pub_info_table.empty:
        return 0
    return int(pub_info_table["pub_id"].max()) + 1


# ---------------------------------------------------------------------------
# Add one new publication row to pub_info_table.
# ---------------------------------------------------------------------------
def add_pub_info_row(pub_info_table, publication, sample_information,
                     mental_illness_subsamples, schizophrenia_subsamples):
    """Return pub_info_table with one new publication row appended.

    The two subsample lists say WHICH subsamples of this publication are
    mentally ill / are schizophrenia. The pub_info_table stores publication-
    level 0/1 flags meaning "the study contains at least one such sample":
      sample_with_mental_illness = 1 if mental_illness_subsamples is non-empty
      sample_with_schizophrenia  = 1 if schizophrenia_subsamples  is non-empty

    Consistency: every schizophrenia subsample must also be a mental-illness
    subsample (schizophrenia is a mental illness) — we check that.

    Returns (updated_pub_info_table, new_pub_id).
    """
    if publication in pub_info_table["publication"].values:
        raise ValueError(
            f"'{publication}' is already in pub_info_table "
            f"(pub_id {pub_info_table.loc[pub_info_table['publication'] == publication, 'pub_id'].tolist()}). "
            "Not adding it again. Re-read pub_info_table from disk if you are re-running.")

    missing = set(schizophrenia_subsamples) - set(mental_illness_subsamples)
    if missing:
        raise ValueError(
            f"these schizophrenia subsamples are not also listed as "
            f"mental-illness subsamples: {sorted(missing)}")

    mental_illness = 1 if len(mental_illness_subsamples) > 0 else 0
    schizophrenia = 1 if len(schizophrenia_subsamples) > 0 else 0

    new_id = next_pub_id(pub_info_table)
    new_row = {
        "pub_id": new_id,
        "publication": publication,
        "sample_information": sample_information,
        "sample_with_mental_illness": mental_illness,
        "sample_with_schizophrenia": schizophrenia,
    }
    updated = pd.concat(
        [pub_info_table, pd.DataFrame([new_row])], ignore_index=True)
    return updated, new_id


# ---------------------------------------------------------------------------
# Derive the illness columns on a new publication's data rows.
# ---------------------------------------------------------------------------
# def _derive_illness_columns(new_data, pub_info_row):
#     """Fill the illness columns on new_data from one pub_info_table row.

#     Rule: a data row gets the publication's flag value if it is a `patients`
#     row, and 0 if it is a `healthy_controls` row. (Community was folded into
#     healthy_controls, so only these two sample_types occur.)
#     """
#     data = new_data.copy()
#     is_patient = data["sample_type"] == "patients"

#     for col in ILLNESS_COLUMNS:
#         pub_value = pub_info_row[col]              # publication-level flag
#         # patients -> publication's value; everyone else (controls) -> 0
#         data[col] = 0
#         data.loc[is_patient, col] = pub_value

#     return data


# ---------------------------------------------------------------------------
# Add one new publication's data to the combined table.
# ---------------------------------------------------------------------------
def add_publication(combined, new_data, pub_info_table,
                    publication, sample_information,
                    mental_illness_subsamples, schizophrenia_subsamples):
    """Add one new publication's data rows to the combined table.

    Steps:
      1. append the publication to pub_info_table (gets the next pub_id),
      2. stamp that pub_id on every new data row,
      3. set the two illness columns on the data rows FROM THE SUBSAMPLE LISTS:
           sample_with_mental_illness = 1 where subsample is in
               mental_illness_subsamples, else 0
           sample_with_schizophrenia  = 1 where subsample is in
               schizophrenia_subsamples, else 0
         (healthy_controls rows are in neither list, so they get 0.)
      4. concatenate the new data onto the combined table.

    Parameters
    ----------
    combined : the existing combined data table (may be empty).
    new_data : the new publication's long-format dataframe.
    pub_info_table : the publication-level table.
    publication : the citation string, e.g. "Igra et al. 2023".
    sample_information : the copied-from-paper sample description (lives only
                        in pub_info_table).
    mental_illness_subsamples : list of subsample names that are mentally ill.
    schizophrenia_subsamples  : list of subsample names that are schizophrenia.

    Returns
    -------
    (updated_combined, updated_pub_info_table, new_pub_id)
    """
    # 1. record the publication and get its id
    pub_info_table, new_id = add_pub_info_row(
        pub_info_table, publication, sample_information,
        mental_illness_subsamples, schizophrenia_subsamples)

    # 2. stamp pub_id on every new data row
    new_data = new_data.copy()
    new_data["pub_id"] = new_id

    # 3. set the illness columns per row, from the subsample lists
    new_data["sample_with_mental_illness"] = (
        new_data["subsample"].isin(mental_illness_subsamples).astype(int))
    new_data["sample_with_schizophrenia"] = (
        new_data["subsample"].isin(schizophrenia_subsamples).astype(int))

    # 4. add the new data to the combined table
    updated_combined = pd.concat([combined, new_data], ignore_index=True)

    print(f"added '{publication}' as pub_id {new_id}: {len(new_data)} rows "
          f"(mental_illness subsamples={mental_illness_subsamples}, "
          f"schizophrenia subsamples={schizophrenia_subsamples})")

    return updated_combined, pub_info_table, new_id
