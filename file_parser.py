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


def _is_numeric(val):
    """Check if a value looks like numeric data."""
    if val is None:
        return False
    sv = str(val).strip().replace(",", "")
    if not sv:
        return False
    try:
        float(sv)
        return True
    except ValueError:
        return False


def _row_cell_values(ws, r, max_col, merge_map):
    """Get all cell values for a row, resolving merges."""
    values = []
    for c in range(1, max_col + 1):
        val = _get_merged_cell_value(ws, r, c, merge_map)
        values.append(val)
    return values


def _build_row_merge_info(ws, merge_map, max_col):
    """
    For each row, build a set of columns that are merge-masters (origin cells)
    vs columns that are just part of a horizontal merge (filled by merge_map).
    Returns a dict: row -> set of columns that hold DISTINCT values.
    """
    row_distinct_cols = {}
    for merged_range in ws.merged_cells.ranges:
        min_col, min_row, max_col_r, max_row_r = range_boundaries(str(merged_range))
        for r in range(min_row, max_row_r + 1):
            if r not in row_distinct_cols:
                row_distinct_cols[r] = set()
            # Only the master cell is "distinct" for this row
            row_distinct_cols[r].add(min_col)
            # Mark all other cols in this merge as non-distinct for this row
            for c in range(min_col + 1, max_col_r + 1):
                row_distinct_cols.setdefault(r, set()).discard(c)
    return row_distinct_cols


def _count_distinct_cells(ws, r, max_col, merge_map):
    """
    Count the number of DISTINCT non-empty values in a row.
    Merged cells that span multiple columns count as 1, not N.
    Returns (distinct_text, distinct_numeric, distinct_total).
    """
    seen_values = set()
    text_count = 0
    numeric_count = 0

    for c in range(1, max_col + 1):
        # Skip cells that are part of a horizontal merge (not the master)
        if (r, c) in merge_map:
            master_r, master_c = merge_map[(r, c)]
            # If the master is on the SAME row, this is a horizontal merge — skip
            if master_r == r:
                continue
            # If master is on a DIFFERENT row, this is a vertical merge — use value

        val = _get_merged_cell_value(ws, r, c, merge_map)
        if val is not None and str(val).strip():
            sv = str(val).strip()
            # Avoid counting the same value multiple times from vertical merges
            cell_key = (c, sv)
            if cell_key in seen_values:
                continue
            seen_values.add(cell_key)

            if _is_numeric(val):
                numeric_count += 1
            else:
                text_count += 1

    return text_count, numeric_count, text_count + numeric_count


def _detect_header_block(ws, merge_map, max_scan=20):
    """
    Auto-detect where the header block starts and ends.

    Returns (header_start_row, header_end_row) — both 1-indexed inclusive.
    Data starts at header_end_row + 1.

    Strategy:
    1. Profile each row counting DISTINCT values (merged spans count as 1)
    2. Skip title rows (rows with very few distinct values like 1-2)
    3. Find the densest text-heavy row = likely the bottom header row
    4. Walk backwards to find where header block starts
    """
    max_col = ws.max_column or 1
    max_row = min(ws.max_row or 1, max_scan)

    profiles = []
    for r in range(1, max_row + 1):
        text, numeric, total = _count_distinct_cells(ws, r, max_col, merge_map)
        profiles.append({
            "row": r,
            "text": text,
            "numeric": numeric,
            "total": total,
        })

    # Find the row with the MOST distinct text cells.
    # This is the "densest header row" — the row with all individual column names.
    # Require at least 3 distinct cells to avoid picking up title rows.
    densest_row_idx = 0
    densest_text = 0
    for i, p in enumerate(profiles):
        if p["text"] > densest_text and p["text"] >= p["numeric"] and p["total"] >= 3:
            densest_text = p["text"]
            densest_row_idx = i

    header_end = profiles[densest_row_idx]["row"]

    # Walk backwards to find header start (skip blank/title rows)
    header_start = header_end
    for i in range(densest_row_idx - 1, -1, -1):
        p = profiles[i]
        if p["total"] == 0:
            break  # blank row
        if p["total"] <= 2 and p["text"] <= 2:
            break  # title row (only 1-2 values like a merged title)
        if p["numeric"] > p["text"]:
            break  # data row
        if p["text"] >= 2:
            header_start = p["row"]
        else:
            break

    # Walk forward from densest to catch any sub-header rows below
    for i in range(densest_row_idx + 1, len(profiles)):
        p = profiles[i]
        if p["total"] == 0:
            break
        if p["numeric"] > 0 and p["numeric"] >= p["text"]:
            break  # data row
        if p["text"] >= 2 and p["numeric"] == 0:
            header_end = p["row"]  # still a header row
        else:
            break

    return header_start, header_end


def _parse_excel_openpyxl(filepath, filename):
    """Parse Excel files using openpyxl to handle merged cells and multi-row headers."""
    wb = load_workbook(filepath, read_only=False, data_only=True)
    sheet_names = wb.sheetnames
    ws = wb[sheet_names[0]]

    merge_map = _build_merge_map(ws)
    max_col = ws.max_column or 1
    max_row = ws.max_row or 1

    header_start, header_end = _detect_header_block(ws, merge_map)

    # Build column headers by combining text from each header row
    headers = []
    for c in range(1, max_col + 1):
        parts = []
        for r in range(header_start, header_end + 1):
            val = _get_merged_cell_value(ws, r, c, merge_map)
            if val is not None:
                s = str(val).strip()
                if s and s not in parts:
                    parts.append(s)
        header = " - ".join(parts) if parts else f"Column_{c}"
        headers.append(header)

    # Strip out headers that are entirely blank (Column_N) from the end
    while headers and headers[-1].startswith("Column_"):
        headers.pop()
    max_col = len(headers)

    # Deduplicate header names
    seen = {}
    for i, h in enumerate(headers):
        if h in seen:
            seen[h] += 1
            headers[i] = f"{h}_{seen[h]}"
        else:
            seen[h] = 0

    # Read data rows (everything after header_end)
    data = []
    for r in range(header_end + 1, max_row + 1):
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
        "headerRows": f"{header_start}-{header_end}",
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
