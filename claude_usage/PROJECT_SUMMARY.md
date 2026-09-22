# Project Summary — Psychological Scales Data Extraction, Aggregation & Presentation

Upload this at the start of a fresh conversation to restore context. Also attach
the relevant `src/` modules and data files for any code-level work.

## Who I am / how to work with me
- Biologist with some data science and Python knowledge — NOT a software
  developer or computer scientist. Code must be readable and debuggable by me,
  well documented, modular, following best practices — but NOT over-engineered.
  Stability for current use matters more than being future-proof.
- Be concise by default. Do NOT use option/questionnaire cards — ask in plain
  English if you need something. Explain things in terms I can follow; avoid
  unexplained jargon and metaphors.
- Keep a clear distinction: a bug / value-misalignment is a CORRECTNESS problem
  (never acceptable); where things sit on a page is a separate LAYOUT question.
- After editing any .py that a notebook imported, RESTART THE KERNEL — otherwise
  the old version stays in memory (this caused a confusing "fix didn't work"
  moment).

## Goal
Extract descriptive statistics (mean, median, SD, min, max, individual item
values) for psychological questionnaire/interview scales from scholarly papers
(mostly PDFs), consolidate into one long-format table, then query, aggregate,
run plausibility checks, and produce a reader-friendly Excel presentation.

## Modules (all in src/)
1. **scaffold.py** — STABLE extraction engine. `make_row(...)` builds one
   long-format row; `run_extraction(pdf_path, extractor, ...)` runs a per-paper
   extractor, writes a verification view (raw_extracted/) + per-publication long
   CSV (consolidated/). Per-paper extractor modules are named after the PDF
   (hyphens→underscores), expose `extract(pdf_path)` returning
   `(raw_df, parsed_df, rows, hardcoded_flag)`. Parse from the PDF; if
   impossible, hardcode + HARDCODED=True (writes a warning file).
2. **concatenate.py** — `consolidate(...)` stacks per-paper CSVs into one
   combined table. `add_publication(...)` adds one publication: assigns next
   `pub_id`, sets the two illness columns per row from subsample lists, appends
   a pub_info_table row. Helpers: `add_pub_info_row(...)`, `next_pub_id(...)`.
3. **query.py** — SQL-like selection. `select(df, col=value, ...)` (AND of
   conditions; a list value acts like IN), `distinct(df, col)`, `overview(df)`.
   Silent by default (return values, don't print).
4. **aggregate.py** — sample-size-WEIGHTED mean of means/medians.
   `aggregate(df, data_type="mean", group_cols=[...])`. Default grouping is most
   granular (scale, subscale, record_type, sample_type, subsample); pass a
   coarser group_cols to pool upward. Auto-excludes redundant_aggregate==True.
   Refuses sd/min/max. Output columns: the group cols + weighted_value,
   n_studies (user renamed to n_groups in their copy), total_n, aggregated_stat
   ("mean_of_means"/"mean_of_medians").
5. **plausibility.py** — self-contained checks (mean/median within [min,max],
   SD>=0, SD<=range, value numeric, sample_size>0), grouped by
   publication+scale+subscale+record_type+sample_type+subsample. Range checks
   only fire when min AND max are reported — "0 flags" is PARTIAL by design (the
   user infers scoring rules backward from observed ranges).
6. **presentation.py** — builds the reader-friendly Excel workbook (details
   below).

## Consolidated long-format schema (columns)
publication, scale_old, data_type, sample_type, subsample, sample_size, value,
source_file, scale, subscale, item_name, record_type, redcap_item_number,
scoring_rule, item_score_reversed, redundant_aggregate, pub_id,
sample_with_mental_illness, sample_with_schizophrenia

Conventions:
- `scale_old` = label as written in the paper; `scale`/`subscale` = normalized
  names the USER decides (ask; controlled vocab). For item rows, scale_old and
  item_name are identical.
- `data_type`: mean|median|sd|minimum|maximum|individual.
- `sample_type`: patients | healthy_controls (community folded into
  healthy_controls — no separate community category).
- `subsample`: a diagnosis/demographic group, or `whole_sample` when the sample
  is not subdivided. `subscale` = `none` when there is no subscale.
- `record_type`: total | subscale | item.
- `scoring_rule`: default "unverified"; if the paper states it explicitly, show
  exact quote + page (+ section title) and ask the user for the standardized
  wording. (raw_sum = plain summed items; arithmetic_mean; etc.)
- `redcap_item_number`: "none" unless items (user fills numbers later).
- `item_score_reversed`: "yes"/"no" for items, else "none".
- `redundant_aggregate` (bool): True for a whole-sample row that overlaps its
  own subsamples (would double-count). Aggregation drops these.

## pub_info_table (human-readable, one row per publication)
Columns: pub_id, publication, sample_information (copied-from-paper sample
description; lives ONLY here), sample_with_mental_illness,
sample_with_schizophrenia.
- Publication-level flags mean "the study contains at least one such SUBSAMPLE"
  (1 if the corresponding subsample list is non-empty).
- `add_publication` takes `mental_illness_subsamples` and
  `schizophrenia_subsamples` (LISTS of subsample names). A data row's flag is 1
  if its subsample is in the list, else 0 (so controls = 0). List order is
  irrelevant. Consistency check: every schizophrenia subsample must also be in
  the mental-illness list.
- OPEN EDGE CASE: a schizophrenia-only patient sample with no subsamples has
  subsample `whole_sample`; controls also use `whole_sample`, so a plain list
  match could mis-flag controls. Intended fix: also restrict flag-setting to
  `sample_type == "patients"`. (Confirm whether implemented.)

## Weighting rule ("Option B", agreed)
Every total = sample-size-weighted mean of the underlying NON-REDUNDANT
subsample means, pooled in one step (each subsample weighted by its own n).
Per-publication total pools that publication's subsamples; grand total pools all
publications' subsamples. Separately, a total ROW's `sample_size` is the SUM of
the distinct subsamples' n (each subsample counted once — NOT once per row, to
avoid inflation). Summing n and weighting the mean are independent, both valid.
- Weight only MEANS (clean). A weighted mean of medians is a defensible summary
  but NOT the true pooled median (no raw data) — label it. Do NOT weight/pool
  SDs (invalid).

## presentation.py — the Excel output
- One worksheet per scale. Publications stacked vertically. Each publication
  section: name, sample_type header (healthy_controls LEFT, patients RIGHT),
  column headers (sample_size, subsample, <subscales...>, "total score"), one
  row per subsample, then a `total` row. A GRAND TOTAL section at the end.
- The two blocks' `total` rows are ALIGNED on the same line (shorter block
  padded with blank rows via `_pad_blocks_to_align_totals`). If a publication
  lacks a sample_type, that block stays blank.
- Cells written to explicit openpyxl (row, col) coordinates — this fixed an
  earlier bug where values slid into the wrong columns when a block was empty
  or shorter.
- Total rows and the grand total report a SUMMED sample size (distinct
  subsamples, each once) via `_summed_sample_size`.
- Column order per scale via `subscale_orders={scale: [subscale,...]}` (listed
  first, others alphabetical, "total score" last). Example: CTQ_SF →
  ["EA","EN","PA","PN","SA","MD"] (EA/EN emotional, PA/PN physical).
- Values are full-precision floats; a rounding option was offered, not yet added.
- REUSABILITY: designed so a future ITEM-level view reuses the helpers with
  item_name as the columns instead of subscale (record_type="item"). Not built.
- Main call:
    from presentation import write_presentation_excel
    write_presentation_excel(df, "output.xlsx",
        subscale_orders={"CTQ_SF": ["EA","EN","PA","PN","SA","MD"]})

### Key internal helpers (for understanding / unit tests)
- `_measure_columns(scale_df, subscale_order=None)` — column list (subscales
  first, "total score" last).
- `_lookup(agg_df, **conditions)` — returns the single matching weighted_value,
  or None if NOT exactly one match. Builds a boolean mask (starts all-True with
  agg_df's index, ANDs each condition with &=). The "exactly one or None" rule
  is deliberate — it refuses to guess.
- `_measure_values(agg_df, measures, base_conditions)` — one value per column;
  subscale columns look up record_type="subscale" (this constraint fixed a bug
  where item rows with the same subscale name leaked into subscale columns, or
  blanked cells when both item+subscale rows matched); "total score" looks up
  record_type="total".
- `_subsample_size(...)` — n of ONE subsample (first numeric value found).
- `_summed_sample_size(...)` — sum of DISTINCT subsamples' n (dedupe then sum);
  could optionally be refactored to reuse `_subsample_size`.
- `_block_grid(...)` — builds one block (header + subsample rows + total row).
- `_pad_blocks_to_align_totals(...)` — pads shorter block so total rows align.
- `_write_grid(...)`, `_write_scale_sheet(...)` — explicit-coordinate writing.

## Recent bug fixed (Garcia-Fernandez CTQ_SF)
Subscale columns came out blank and a stray MD (item) value appeared. Cause:
`_measure_values` matched subscale columns on `subscale` alone; a subscale that
had BOTH an item row and a subscale row gave two matches → `_lookup` returned
None (blank); MD had only an item row → one match → item value shown. Fix:
subscale lookups now also require `record_type="subscale"`. Data was fine; bug
was in presentation.py.

## Extraction prompts (reusable files)
- PROMPT_0_context.txt — project context; paste first in a fresh extraction chat.
- PROMPT_1_extract_and_verify.txt — present raw+parsed verification views + CSV;
  no code yet; ask about items; confirm scale/subscale names; flag nesting /
  redundant aggregates; present sample_information quote+page and ask for the
  two illness flags.
- PROMPT_2_generate_code.txt — write the per-paper extractor module.
  Always attach the CURRENT scaffold.py to a fresh extraction chat.

## Data / scales in the set
CTQ_SF (subscales EA, EN, PA, PN, SA, MD + total), DERS (AWARENESS, CLARITY,
GOALS, IMPULSE, NONACCEPTANCE, STRATEGIES + total), DES_T (no subscales; total;
has item-level data), PSYRATS (AHS, DS; patients only). Consolidated file:
all_consolidated.csv (~553 rows, 19 columns).

## Environment
Project root has data/ (raw_pdfs, raw_extracted, consolidated, external,
screenshots_spot_checks, all_consolidated.csv), src/ (modules), notebooks/
(run_extraction.ipynb, presentation_walkthrough.ipynb, analysis notebooks).
venv is .venv. git ignores all data (data/**), *.pdf, *.xlsx, *.csv, keeping
folder structure via .gitkeep. Notebooks import modules via:
sys.path.append(str(Path.cwd().parent / "src")).

## Learning notes captured (things explained this session)
- pandas returns a container (Series/DataFrame), never auto-scalar, even for one
  match → use `.iloc[0]` to get the bare value.
- `.loc` = by label / boolean; `.iloc` = by integer position (i = integer).
- boolean-mask filtering: `mask = pd.Series(True, index=df.index)` then
  `mask &= df[col]==val`; a Series-with-index aligns by label (a plain list can
  misalign on a non-sequential index).
- `**conditions` collects keyword args into a dict → lets a function accept an
  unknown number of column=value filters.
- filtering gives a container not a value; empty-vs-one-vs-many matters (the
  "exactly one" guard).

## Open / deferred items
- Unit tests (user will write them; presentation_walkthrough.ipynb lists good
  candidates and what to assert).
- run_extraction.py SCRIPT path bug (parked; the notebook works).
- Duplicate-publication guard in add_pub_info_row (discussed; confirm it's in).
- patients-only restriction for illness-flag setting (whole_sample edge case).
- Item-level presentation view (reuse presentation.py helpers with item_name).
- Optional rounding of presentation values to 2 decimals.
- scale-name casing/duplicate cleanup habit (reveal via grouping, fix after).
