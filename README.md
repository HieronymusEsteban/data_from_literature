# Psychological Scales — Data Extraction & Aggregation

Extract descriptive statistics (mean, median, SD, min, max, individual values)
for psychological questionnaire/interview scales from scholarly articles,
consolidate them into a long-format CSV per scale, and select/aggregate.

## Folder structure

```
.
├── data/
│   ├── external/         # data downloaded from repositories/supplements (already structured)
│   ├── raw_pdfs/         # the source PDF articles (not committed by default)
│   ├── raw_extracted/    # raw, unverified output straight from the extraction tools
│   ├── per_publication/  # one cleaned, verified CSV per publication
│   └── consolidated/     # one long-format CSV per scale (all publications combined)
├── src/                  # reusable Python modules (parsing, reshaping, aggregation)
├── tests/                # pytest unit tests for the src/ functions
├── notebooks/            # JupyterLab notebooks for exploration & visual verification
├── docs/                 # setup guides + decision-and-assumptions log
├── requirements.txt
└── README.md
```

## Getting started

See `docs/01_setup_venv.md` then `docs/02_run_jupyter.md`.
