# Decision & Assumptions Log — Psych-Scales Extraction Project

_Running record of what's been decided, what's assumed, and what's still open.
Update as the project evolves._

## The overall pipeline (4 data steps)
1. Export data from PDF / online source.
2. Per-publication output.
3. Consolidated long-format CSV per scale.
4. Selection / aggregation.

The discussion proceeds one step at a time, mirroring the data pipeline.

## Consolidated long-format schema (decided)
Columns, in order:
`publication, scale, data_type, sample, subsample, sample_size, value`
- `data_type` controlled vocabulary: mean, median, sd, minimum, maximum, individual
- `sample` controlled vocabulary: patients, healthy_controls
- `subsample`: specific diagnosis / demographic group, or "NA"
- `sample_size`: n for the group; needed for weighted aggregation in step 4
- missing-value marker: "NA"

## Folder convention (decided)
- `data/raw_pdfs/` — source PDFs
- `data/external/` — data found already-structured online (skips extraction)
- `data/raw_extracted/<pdf_name>/` — verification views (raw packed + parsed CSVs)
- `data/consolidated/<pdf_name>/` — long-format CSV per paper
- `src/` — scaffold.py + per-paper extractor modules
- `tests/` — pytest unit tests
- `notebooks/` — run_extraction.ipynb (the runner)

## Code architecture (decided)
- `scaffold.py` = STABLE part: schema, make_row, split_paren, validate_rows,
  write_verification, write_consolidated, run_extraction.
- Per-paper module `<pdf_name>.py` = SWAPPABLE part: exposes `extract(pdf_path)`
  returning `(raw_df, parsed_df, rows, hardcoded_flag)`.
- Code pitched to competent-biologist level: small functions, readable, debuggable.

## Extraction approach (decided)
- Prefer parsing values directly from the PDF (pdfplumber) — no hallucination,
  numbers traceable to printed cells.
- Visual verification by the user is load-bearing and done every paper.
- Fallback when clean parsing fails: hardcode values AND set HARDCODED=True,
  which triggers a visible warning + `*.HARDCODED_WARNING.txt`. Assistant also
  states this explicitly in chat.
- Online-vs-PDF decision is made by the user per paper (recorded), not auto-detected.

## Strategy (decided)
- Build statistics first from well-documented papers (clear scoring methods),
  then use those as reference ranges to sanity-check unclear papers.

## Verification / testing layers (decided)
- Unit tests (pytest): for deterministic transform logic, written as you go.
- Plausibility checks: on assembled real data, at the end (SD not larger than
  range, mean within min–max, values within scale bounds, group sizes sum).
- Visual inspection: human check of extraction fidelity, per paper, before data
  enters the pipeline.

## Open / still to decide
- Final column names (may amend).
- A possible `metric_type` column (raw sum vs mean-item vs T-score vs percentile)
  to avoid pooling incomparable numbers — flagged, not yet added.
- A nesting/parent-group marker for overlapping subgroups — flagged, not yet added.
- `sample_size` convention for individual-data-point rows (parent n, or NA).
- `run_extraction.py` SCRIPT path bug — PARKED (notebook works; fix later).
- Formal close of the step-one brainstorm.

## Worked example completed
- Modestin & Erni 2004 (doi:10.1016/j.psychres.2001.12.001), DES-T, Table 1.
- Parsed directly from PDF; 18 long-format rows; values eye-verified.
