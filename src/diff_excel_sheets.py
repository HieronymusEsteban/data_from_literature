"""
diff_excel_sheets.py
=====================
Compare specific worksheets between two .xlsx files, cell by cell.
Use this to confirm the unaffected sheets (CTQ_SF, DERS, DES_T) are byte-for-
byte identical between the old and new presentation.py output.

USAGE (from the command line, in your venv):
    python diff_excel_sheets.py old_output.xlsx new_output.xlsx CTQ_SF DERS DES_T

Prints "IDENTICAL" for a sheet with no differences, otherwise lists every
differing (or missing) cell with its old and new value.
"""

import sys

import openpyxl


def diff_sheet(ws_old, ws_new, sheet_name):
    """Compare two worksheets cell by cell. Returns a list of difference strings."""
    max_row = max(ws_old.max_row, ws_new.max_row)
    max_col = max(ws_old.max_column, ws_new.max_column)

    diffs = []
    for row in range(1, max_row + 1):
        for col in range(1, max_col + 1):
            old_val = ws_old.cell(row=row, column=col).value
            new_val = ws_new.cell(row=row, column=col).value
            if old_val != new_val:
                coord = ws_old.cell(row=row, column=col).coordinate
                diffs.append(f"  {sheet_name}!{coord}: old={old_val!r}  new={new_val!r}")
    return diffs


def main(old_path, new_path, sheet_names):
    wb_old = openpyxl.load_workbook(old_path, data_only=True)
    wb_new = openpyxl.load_workbook(new_path, data_only=True)

    for name in sheet_names:
        if name not in wb_old.sheetnames or name not in wb_new.sheetnames:
            print(f"{name}: MISSING from one of the workbooks -- skipped")
            continue
        diffs = diff_sheet(wb_old[name], wb_new[name], name)
        if not diffs:
            print(f"{name}: IDENTICAL")
        else:
            print(f"{name}: {len(diffs)} differing cell(s)")
            for d in diffs:
                print(d)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: python diff_excel_sheets.py old.xlsx new.xlsx SHEET1 [SHEET2 ...]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
