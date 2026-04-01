#!/usr/bin/env python3
"""Convert .xlsx to .csv using only Python stdlib.

xlsx files are ZIP archives containing XML. This reads the shared strings
table and the first worksheet, then outputs CSV.

Usage:
    python3 xlsx2csv.py input.xlsx -o output.csv
"""

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
import zipfile

# xlsx XML namespace
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_shared_strings(zf):
    """Read shared strings table from xlsx."""
    try:
        with zf.open("xl/sharedStrings.xml") as f:
            tree = ET.parse(f)
    except KeyError:
        return []

    strings = []
    for si in tree.getroot().iter(f"{NS}si"):
        # Concatenate all <t> elements (handles rich text)
        parts = []
        for t in si.iter(f"{NS}t"):
            if t.text:
                parts.append(t.text)
        strings.append("".join(parts))

    return strings


def read_sheet(zf, shared_strings, sheet_path="xl/worksheets/sheet1.xml"):
    """Read a worksheet and yield rows as lists of strings."""
    with zf.open(sheet_path) as f:
        tree = ET.parse(f)

    rows = []
    for row_el in tree.getroot().iter(f"{NS}row"):
        cells = {}
        for cell in row_el.iter(f"{NS}c"):
            ref = cell.get("r", "")
            col = "".join(c for c in ref if c.isalpha())
            col_idx = col_to_index(col)

            cell_type = cell.get("t", "")
            value_el = cell.find(f"{NS}v")
            value = value_el.text if value_el is not None else ""

            if cell_type == "s" and value:
                # Shared string reference
                idx = int(value)
                value = shared_strings[idx] if idx < len(shared_strings) else ""

            cells[col_idx] = value

        if cells:
            max_col = max(cells.keys())
            row = [cells.get(i, "") for i in range(max_col + 1)]
            rows.append(row)

    return rows


def col_to_index(col_str):
    """Convert column letter(s) to 0-based index: A=0, B=1, ..., Z=25, AA=26."""
    result = 0
    for c in col_str.upper():
        result = result * 26 + (ord(c) - ord("A") + 1)
    return result - 1


def main():
    parser = argparse.ArgumentParser(description="Convert xlsx to csv")
    parser.add_argument("input", help="Input .xlsx file")
    parser.add_argument("-o", "--output", default="-",
                        help="Output .csv file (default: stdout)")
    args = parser.parse_args()

    with zipfile.ZipFile(args.input, "r") as zf:
        shared_strings = read_shared_strings(zf)
        rows = read_sheet(zf, shared_strings)

    if args.output == "-":
        out = sys.stdout
    else:
        out = open(args.output, "w", newline="", encoding="utf-8")

    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)

    if args.output != "-":
        out.close()
        print(f"Written {len(rows)} rows to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
