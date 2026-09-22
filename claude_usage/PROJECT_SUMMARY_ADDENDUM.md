# Addendum to PROJECT_SUMMARY.md — subsample-name uniqueness issue & re-extractions

Read this together with PROJECT_SUMMARY.md. It records a data-correction pattern
discovered after that summary was written.

## The problem: non-unique subsample names
Some publications report a SEPARATE sample size per subscale (each subscale was
answered by a different number of participants). In the long-format table the
values were still correct (each value has its own row with its own
sample_size), BUT the `subsample` names were built WITHOUT the subscale, so two
genuinely different subsamples (same site, different subscale, different n)
ended up with the SAME subsample name.

This is a ROOT-CAUSE data error, not just a display glitch: within a
publication you get the same subsample name attached to different sample sizes.
It stays invisible in the long-format management table but corrupts the
presentation output (the non-unique name collapses distinct subsamples).

The fix: make the subsample name unique by INCLUDING the subscale (and any
other distinguishing dimension) in it, then RE-EXTRACT that publication.

## Worked example — Woodward et al. 2014 (PSYRATS), Table 1
Table 1 gives AHS and DS their own N columns (e.g. site 8 London: AHS N=219,
DS N=280). Originally the subsample was site+location only, so a site's AHS and
DS collided. Corrected subsample naming:
    site{site}_{location}_{subscale}      e.g. "site8_London_DS"
Re-extracted result: 19 rows (12 AHS + 7 DS; sites 1,2,3,11,12 are AHS-only),
record_type="subscale", scoring_rule="raw_sum" (paper states totals = sum of
items), sample_type="patients". Verification: AHS N sum = 711, DS N sum = 520
(match the paper), and all 19 subsample names unique.

## How to check any publication for this problem
Within each (publication, scale, subscale, sample_type), no two different
sample sizes should share a subsample name. Quick check:
    df.groupby(["publication","scale","subscale","sample_type","subsample"])["sample_size"].nunique().max()
should be 1. Any subsample where different rows carry different sample_size is a
name-collision to fix by re-extracting with a subscale-inclusive subsample name.

## Cleanup when re-extracting a publication (IMPORTANT)
Before adding the re-extracted (correct) version, REMOVE the old (wrong) version
so you don't keep both:
- delete that publication's rows from all_consolidated.csv, and
- delete its row from pub_info_table,
then re-add via add_publication (which reassigns pub_id and derives the illness
columns). Verify uniqueness with the groupby check above afterwards.

## Currently being re-extracted
- Woodward et al. 2014 (PSYRATS) — DONE (extractor:
  PSYRATS_Woodward_et_al_2014.py).
- Favrod et al. 2012 (PSYRATS) — SAME problem; to be re-extracted next (run
  PROMPT 1 then PROMPT 2 with the current scaffold.py).

## Note on illness flags for these PSYRATS papers
All subsamples are patient groups with schizophrenia-spectrum diagnoses, so the
full list of subsample names typically goes into BOTH mental_illness_subsamples
and schizophrenia_subsamples. (Judgement call: the diagnostic mix includes
psychosis NOS, first-episode, at-risk, etc., not strictly schizophrenia — set
the schizophrenia flag according to how strictly you define it.)
