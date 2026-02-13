"""File parsing module supporting Excel, CSV, TSV, and JSON files."""

import json
import re
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import range_boundaries


SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb", ".csv", ".tsv", ".json"}


def parse_file(filepath, filename):
    """
    Parse an uploaded file and return structured data.

    Returns a dict with:
      - fileName: original filename
      - headers: list of column names
      - data: list of row dicts
      - sheetNames: list of sheet names (Excel only)
      - selectedSheet: active sheet name (Excel only)
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("xlsx", "xlsm", "xlsb"):
        return _parse_excel_openpyxl(filepath, filename)
    elif ext == "xls":
        return _parse_excel_xls(filepath, filename)
    elif ext == "csv":
        return _parse_csv(filepath, filename)
    elif ext == "tsv":
        return _parse_csv(filepath, filename, sep="\t")
    elif ext == "json":
        return _parse_json(filepath, filename)
    else:
        return _parse_csv(filepath, filename)


def _get_merged_cell_value(ws, row, col, merge_map):
    """Get the value of a cell, resolving merged cell references."""
    key = (row, col)
    if key in merge_map:
        master_row, master_col = merge_map[key]
        return ws.cell(row=master_row, column=master_col).value
    return ws.cell(row=row, column=col).value


def _build_merge_map(ws):
    """Build a mapping from every cell in a merged range to its master cell."""
    merge_map = {}
    for merged_range in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = range_boundaries(str(merged_range))
        for r in range(min_row, max_row + 1):
            for c in range(min_col, max_col + 1):
                if r != min_row or c != min_col:
                    merge_map[(r, c)] = (min_row, min_col)
    return merge_map


def _detect_header_rows(ws, merge_map, max_scan=10):
    """
    Auto-detect how many rows form the header block.

    Strategy: scan the first N rows. The header block ends at the first row
    where ALL non-empty cells look like data (numbers, dates) rather than
    labels, OR the first row after a fully-populated text row.
    We look for the transition from label rows to data rows.
    """
    max_col = ws.max_column or 1
    max_row_scan = min(ws.max_row or 1, max_scan)

    row_profiles = []
    for r in range(1, max_row_scan + 1):
        non_empty = 0
        looks_like_data = 0
        for c in range(1, max_col + 1):
            val = _get_merged_cell_value(ws, r, c, merge_map)
            if val is not None and str(val).strip():
                non_empty += 1
                sv = str(val).strip()
                # Looks like data: is a number, date-like, or very long
                try:
                    float(sv.replace(",", ""))
                    looks_like_data += 1
                    continue
                except ValueError:
                    pass
                if len(sv) > 60:
                    looks_like_data += 1
        row_profiles.append((non_empty, looks_like_data))

    # Find the first row where majority of cells are data-like
    # and the previous row had mostly text = that's the data start
    for i in range(1, len(row_profiles)):
        non_empty, data_like = row_profiles[i]
        if non_empty > 0 and data_like >= non_empty * 0.5:
            return i  # header rows = rows 1..i, data starts at row i+1

    # Fallback: assume 1 header row
    return 1


def _parse_excel_openpyxl(filepath, filename):
    """Parse Excel files using openpyxl to handle merged cells and multi-row headers."""
    wb = load_workbook(filepath, read_only=False, data_only=True)
    sheet_names = wb.sheetnames
    ws = wb[sheet_names[0]]

    merge_map = _build_merge_map(ws)
    num_header_rows = _detect_header_rows(ws, merge_map)

    max_col = ws.max_column or 1
    max_row = ws.max_row or 1

    # Build column headers by combining text from each header row
    headers = []
    for c in range(1, max_col + 1):
        parts = []
        for r in range(1, num_header_rows + 1):
            val = _get_merged_cell_value(ws, r, c, merge_map)
            if val is not None:
                s = str(val).strip()
                if s and s not in parts:
                    parts.append(s)
        header = " - ".join(parts) if parts else f"Column_{c}"
        headers.append(header)

    # Deduplicate header names
    seen = {}
    for i, h in enumerate(headers):
        if h in seen:
            seen[h] += 1
            headers[i] = f"{h}_{seen[h]}"
        else:
            seen[h] = 0

    # Read data rows
    data = []
    for r in range(num_header_rows + 1, max_row + 1):
        row_dict = {}
        all_empty = True
        for c in range(1, max_col + 1):
            val = _get_merged_cell_value(ws, r, c, merge_map)
            if val is not None:
                s = str(val).strip()
                row_dict[headers[c - 1]] = s
                if s:
                    all_empty = False
            else:
                row_dict[headers[c - 1]] = ""
        if not all_empty:
            data.append(row_dict)

    wb.close()

    return {
        "fileName": filename,
        "headers": headers,
        "data": data,
        "sheetNames": sheet_names,
        "selectedSheet": sheet_names[0],
        "rowCount": len(data),
        "colCount": len(headers),
        "headerRows": num_header_rows,
    }


def _parse_excel_xls(filepath, filename):
    """Parse old .xls files using pandas/xlrd (no merged cell support)."""
    xls = pd.ExcelFile(filepath)
    sheet_names = xls.sheet_names
    df = pd.read_excel(xls, sheet_name=sheet_names[0])
    df = df.fillna("")

    headers = list(df.columns.astype(str))
    data = df.astype(str).to_dict(orient="records")

    return {
        "fileName": filename,
        "headers": headers,
        "data": data,
        "sheetNames": sheet_names,
        "selectedSheet": sheet_names[0],
        "rowCount": len(data),
        "colCount": len(headers),
    }


def _parse_csv(filepath, filename, sep=","):
    """Parse CSV/TSV files."""
    df = pd.read_csv(filepath, sep=sep)
    df = df.fillna("")

    headers = list(df.columns.astype(str))
    data = df.astype(str).to_dict(orient="records")

    return {
        "fileName": filename,
        "headers": headers,
        "data": data,
        "sheetNames": None,
        "selectedSheet": None,
        "rowCount": len(data),
        "colCount": len(headers),
    }


def _parse_json(filepath, filename):
    """Parse JSON files (expects array of objects or single object)."""
    with open(filepath, "r") as f:
        parsed = json.load(f)

    if isinstance(parsed, dict):
        parsed = [parsed]

    if not isinstance(parsed, list) or len(parsed) == 0:
        return {
            "fileName": filename,
            "headers": [],
            "data": [],
            "sheetNames": None,
            "selectedSheet": None,
            "rowCount": 0,
            "colCount": 0,
        }

    # Convert all values to string for consistency
    data = []
    for row in parsed:
        data.append({str(k): str(v) if v is not None else "" for k, v in row.items()})

    headers = list(data[0].keys()) if data else []

    return {
        "fileName": filename,
        "headers": headers,
        "data": data,
        "sheetNames": None,
        "selectedSheet": None,
        "rowCount": len(data),
        "colCount": len(headers),
    }
