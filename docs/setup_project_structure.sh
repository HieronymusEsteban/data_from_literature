#!/usr/bin/env bash
#
# setup_project_structure.sh
# ---------------------------
# Creates the full folder structure for the psych-scales project.
# Run this ONCE, from wherever you want the project to live.
#
# Usage:
#   bash setup_project_structure.sh
#
# By default it creates a folder called "psych-scales-project" in the CURRENT
# directory and builds everything inside it. Change PROJECT_NAME below if you
# want a different name.

# Stop immediately if any command fails (safer than plowing ahead on an error).
set -e

# --- Choose where the project lives ---------------------------------------
# This creates the project in the current folder. To put it somewhere specific,
# cd into that location first, e.g.:
#   mkdir -p ~/projects && cd ~/projects
# and THEN run this script.
PROJECT_NAME="psych-scales-project"

# Create the project root and step into it.
mkdir -p "$PROJECT_NAME"
cd "$PROJECT_NAME"

# --- Create the data sub-folders (one per pipeline stage) -----------------
mkdir -p data/external         # downloaded structured data (repository/supplement hits)
mkdir -p data/raw_pdfs         # source PDFs
mkdir -p data/raw_extracted    # raw, unverified extractor output
mkdir -p data/per_publication  # one cleaned + verified CSV per paper
mkdir -p data/consolidated     # one long-format CSV per scale

# --- Create the code / docs / notebook folders ----------------------------
mkdir -p src                   # reusable Python modules
mkdir -p tests                 # pytest unit tests
mkdir -p notebooks             # JupyterLab notebooks
mkdir -p docs                  # setup guides + the decision log

# --- Add .gitkeep so the empty data folders survive in git ----------------
# (Git ignores truly-empty folders; the placeholder gives it something to track.)
touch data/external/.gitkeep
touch data/raw_pdfs/.gitkeep
touch data/raw_extracted/.gitkeep
touch data/per_publication/.gitkeep
touch data/consolidated/.gitkeep

# --- Confirm what was built ------------------------------------------------
echo "Project structure created under: $(pwd)"
echo "----------------------------------------"
# 'find' lists everything; sort makes it readable. Shows folders + .gitkeep files.
find . -type d | sort
