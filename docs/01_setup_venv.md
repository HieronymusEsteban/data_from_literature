# Setting up the virtual environment

A virtual environment (venv) keeps this project's Python packages isolated from
your system Python and from other projects. Run these commands once, from the
project root folder.

## 1. Create the venv

```bash
# Creates a folder called .venv containing an isolated Python.
# (.venv is conventional and is already in .gitignore so it won't be committed.)
python3 -m venv .venv
```

## 2. Activate it

```bash
# macOS / Linux:
source .venv/bin/activate

# Windows (PowerShell):
# .venv\Scripts\Activate.ps1
```

Your prompt should now show `(.venv)` at the start. Everything you pip-install
now goes into this venv, not your system Python.

## 3. Install the project's packages

```bash
# Upgrade pip first (good hygiene), then install everything in requirements.txt.
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Adding a new package later

```bash
# Install whatever you need...
pip install some-new-package

# ...then write the EXACT current set of installed packages + versions back
# into requirements.txt so the environment is reproducible.
pip freeze > requirements.txt
```

`pip freeze` snapshots every installed package with its exact version. Commit the
updated requirements.txt so you (or anyone else) can rebuild the same environment
later with `pip install -r requirements.txt`.

> Tip: `pip freeze` lists sub-dependencies too, so the file gets longer than the
> hand-written one. That's expected and fine — it's the price of reproducibility.

## 5. Leaving the venv

```bash
deactivate
```
