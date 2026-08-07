"""
run_modestin_2004.py
====================
Runner: wires the paper-specific extractor to the stable scaffold and writes
the long-format CSV. One short runner like this per paper.

Run from the project root with the venv active:

    python src/run_modestin_2004.py
"""

from pathlib import Path

from scaffold import extract_publication
import extract_modestin_2004

# Project root = two levels up from this file (src/ -> project root).
ROOT = Path(__file__).resolve().parents[1]

PDF_PATH = ROOT / "data" / "raw_pdfs" / "DES-T_Modestin_et_al_2004.pdf"
OUTPUT_DIR = ROOT / "data" / "raw_extracted" / "DES-T_Modestin_et_al_2004"


def main():
    df = extract_publication(
        pdf_path=PDF_PATH,
        extractor=extract_modestin_2004.extract,
        output_dir=OUTPUT_DIR,
    )
    # Quick look so you can eyeball the result in the terminal too.
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
