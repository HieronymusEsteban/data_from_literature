# Activating the venv and launching JupyterLab

Run these every time you sit down to work.

## 1. Activate the venv

```bash
# From the project root.
# macOS / Linux:
source .venv/bin/activate

# Windows (PowerShell):
# .venv\Scripts\Activate.ps1
```

## 2. Launch JupyterLab

```bash
# Opens JupyterLab in your default web browser.
# It serves from the current folder, so start it from the project root
# to see the whole project tree in the file browser on the left.
jupyter lab
```

Create new notebooks inside the `notebooks/` folder. When you're done, save the
notebook, then stop the server with Ctrl-C in the terminal (it asks to confirm),
and `deactivate` the venv.
