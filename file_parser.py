"""File parsing module supporting Excel, CSV, TSV, and JSON files."""

import json
import re
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import range_boundaries, get_column_letter
from openpyxl.styles import Font, PatternFill


SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb", ".csv", ".tsv", ".json"}
MAX_HEADER_ROWS = 8


def parse_file(filepath, filename, header_row=None):
    """
    Parse an uploaded file and return structured data.

    Args:
        filepath: path to the file
        filename: original filename
        header_row: optional override like "1" or "3-4" for header row(s)

    Returns a dict with:
      - fileName: original filename
      - headers: list of column names
      - data: list of row dicts
      - sheetNames: list of sheet names (Excel only)
      - selectedSheet: active sheet name (Excel only)
      - preview: first 12 rows as raw values (Excel only)
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("xlsx", "xlsm", "xlsb"):
        return _parse_excel_openpyxl(filepath, filename, header_row_override=header_row)
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


# ═══════════════════════════════════════════════════════════════════
# OPENPYXL HELPERS
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
# MULTI-STRATEGY HEADER DETECTION
# ═══════════════════════════════════════════════════════════════════

def _strategy_autofilter(ws):
    """
    Strategy 1: Excel AutoFilter.
    If the sheet has AutoFilter enabled, the first row of the filter range
    is always the header row. This is the most reliable signal.
    Returns (header_start, header_end) or None.
    """
    af = ws.auto_filter
    if af and af.ref:
        ref = str(af.ref)
        # Parse range like "A1:AJ500" or "A3:Z100"
        match = re.match(r'[A-Z]+(\d+):', ref)
        if match:
            header_row = int(match.group(1))
            return header_row, header_row
    return None


def _strategy_tables(ws):
    """
    Strategy 2: Excel Table objects.
    If the sheet has a Table, the first row of the table range is the header.
    Returns (header_start, header_end) or None.
    """
    if hasattr(ws, 'tables') and ws.tables:
        for table in ws.tables.values():
            ref = str(table.ref)
            match = re.match(r'[A-Z]+(\d+):', ref)
            if match:
                header_row = int(match.group(1))
                return header_row, header_row
    return None


def _strategy_formatting(ws, merge_map, max_scan=15):
    """
    Strategy 3: Cell formatting (bold font, background fill).
    Header rows typically have DIFFERENT formatting than data rows.
    We look for formatting that is present in the top rows but NOT in
    subsequent data rows — the transition point marks the end of headers.
    Returns (header_start, header_end) or None.
    """
    max_col = min(ws.max_column or 1, 50)
    max_row = min(ws.max_row or 1, max_scan)

    row_scores = []
    for r in range(1, max_row + 1):
        bold_count = 0
        fill_count = 0
        non_empty = 0

        for c in range(1, max_col + 1):
            cell = ws.cell(row=r, column=c)
            val = _get_merged_cell_value(ws, r, c, merge_map)
            if val is not None and str(val).strip():
                non_empty += 1

            if cell.font and cell.font.bold:
                bold_count += 1

            if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb:
                rgb = str(cell.fill.fgColor.rgb)
                if rgb not in ("00000000", "0", "None", "00FFFFFF"):
                    fill_count += 1

        score = 0
        if non_empty > 0:
            if bold_count / max(non_empty, 1) >= 0.5:
                score += 2
            if fill_count / max(non_empty, 1) >= 0.3:
                score += 2
            if bold_count >= 3:
                score += 1
            if fill_count >= 3:
                score += 1

        row_scores.append({
            "row": r, "score": score, "non_empty": non_empty,
            "bold": bold_count, "fill": fill_count,
        })

    # Look for a formatting TRANSITION: rows where the score DROPS.
    # If ALL rows have the same high score, there's no useful signal.
    header_start = None
    header_end = None
    total_scored = sum(1 for s in row_scores if s["score"] >= 2 and s["non_empty"] > 0)
    total_nonempty = sum(1 for s in row_scores if s["non_empty"] > 0)

    # If all non-empty rows have the same formatting, no signal
    if total_nonempty > 0 and total_scored == total_nonempty:
        return None

    for i, info in enumerate(row_scores):
        if info["score"] >= 2 and info["non_empty"] > 0:
            if header_start is None:
                header_start = info["row"]
            header_end = info["row"]
        elif header_start is not None:
            if info["non_empty"] == 0 and (header_end - header_start + 1) <= 2:
                continue
            break

    if header_start is not None and header_end is not None:
        if (header_end - header_start + 1) > MAX_HEADER_ROWS:
            return None
        return header_start, header_end
    return None


def _strategy_merges(ws, merge_map, max_scan=25):
    """
    Strategy 4: Merged cell patterns.
    Header rows have horizontal/vertical merges. Data rows don't.
    Only considers merges that START within the first MAX_HEADER_ROWS+2 rows
    to avoid being fooled by merges in the data area.
    Returns (header_start, header_end) or None.
    """
    max_col = ws.max_column or 1
    merge_row_limit = MAX_HEADER_ROWS + 2  # Only look at merges starting in top rows

    h_merges = {}
    v_merges = {}
    for merged_range in ws.merged_cells.ranges:
        min_col, min_row, max_col_r, max_row_r = range_boundaries(str(merged_range))
        # Only consider merges that START in the top rows
        if min_row > merge_row_limit:
            continue
        # Clamp the end row to merge_row_limit
        clamped_max_row = min(max_row_r, merge_row_limit)
        if max_col_r > min_col:
            for r in range(min_row, clamped_max_row + 1):
                h_merges.setdefault(r, []).append((min_col, max_col_r, min_row, max_row_r))
        if max_row_r > min_row:
            for r in range(min_row, clamped_max_row + 1):
                v_merges.setdefault(r, []).append((min_col, max_col_r, min_row, max_row_r))

    all_merge_rows = set(h_merges.keys()) | set(v_merges.keys())
    if not all_merge_rows:
        return None

    header_start = min(all_merge_rows)
    header_end = max(all_merge_rows)

    # Skip title rows: single horizontal merge spanning >70% of columns
    while header_start < header_end:
        merges_on_row = h_merges.get(header_start, [])
        if len(merges_on_row) == 1:
            mc_min, mc_max, _, _ = merges_on_row[0]
            span = mc_max - mc_min + 1
            if span > max_col * 0.7:
                header_start += 1
                continue
        break

    # Skip blank rows at start
    while header_start < header_end:
        has_content = False
        for c in range(1, max_col + 1):
            val = _get_merged_cell_value(ws, header_start, c, merge_map)
            if val is not None and str(val).strip():
                has_content = True
                break
        if has_content:
            break
        header_start += 1

    # Final sanity check
    if (header_end - header_start + 1) > MAX_HEADER_ROWS:
        return None

    return header_start, header_end


def _strategy_content_pattern(ws, merge_map, max_scan=20):
    """
    Strategy 5 (fallback): Content pattern analysis.
    Look at the first N rows. The header row is the first row where
    most cells are SHORT text strings (column names are typically short).
    Data rows that follow will have different value patterns.
    Returns (header_start, header_end).
    """
    max_col = min(ws.max_column or 1, 50)
    max_row = min(ws.max_row or 1, max_scan)

    for r in range(1, max_row + 1):
        non_empty = 0
        for c in range(1, max_col + 1):
            val = ws.cell(row=r, column=c).value
            if val is not None and str(val).strip():
                non_empty += 1
        if non_empty >= 3:
            return r, r

    return 1, 1


def _validate_result(result):
    """Reject a strategy result if the header span is unreasonably large."""
    if result is None:
        return None
    start, end = result
    if (end - start + 1) > MAX_HEADER_ROWS:
        return None  # Reject — too many rows to be a real header
    return result


def _detect_header_block(ws, merge_map, max_scan=25):
    """
    Multi-strategy header detection. Tries strategies in order of reliability:
    1. AutoFilter (most reliable — Excel stores the exact header row)
    2. Table objects (Excel tables have explicit header rows)
    3. Cell formatting (bold/colored rows = headers)
    4. Merged cell patterns (horizontal merges = group headers)
    5. Content pattern fallback (first row with 3+ values)

    All results are validated: max 8 header rows. Any strategy returning
    more than that is rejected (likely detecting the whole sheet as headers).

    Returns (header_start_row, header_end_row) — both 1-indexed inclusive.
    """
    # Strategy 1: AutoFilter
    result = _strategy_autofilter(ws)
    if result:
        af_start, af_end = result
        # Check if merges extend above the autofilter row (group headers)
        merge_result = _validate_result(_strategy_merges(ws, merge_map, max_scan))
        if merge_result:
            m_start, m_end = merge_result
            if m_start <= af_start and m_end >= af_start:
                return m_start, m_end
            if m_end < af_start:
                return m_start, af_end
        return result

    # Strategy 2: Table objects
    result = _strategy_tables(ws)
    if result:
        return result

    # Strategy 3: Cell formatting (with validation)
    result = _validate_result(_strategy_formatting(ws, merge_map))
    if result:
        return result

    # Strategy 4: Merged cell patterns (with validation)
    result = _validate_result(_strategy_merges(ws, merge_map, max_scan))
    if result:
        return result

    # Strategy 5: Content pattern fallback
    return _strategy_content_pattern(ws, merge_map, max_scan)


# ═══════════════════════════════════════════════════════════════════
# EXCEL PARSING
# ═══════════════════════════════════════════════════════════════════

def _extract_preview_rows(ws, merge_map, num_rows=12):
    """Extract the first N rows as raw values for preview in the UI."""
    max_col = ws.max_column or 1
    preview = []
    for r in range(1, min((ws.max_row or 1) + 1, num_rows + 1)):
        row_vals = []
        for c in range(1, max_col + 1):
            val = _get_merged_cell_value(ws, r, c, merge_map)
            row_vals.append(str(val).strip() if val is not None else "")
        preview.append(row_vals)
    return preview


def _build_headers_and_data(ws, merge_map, header_start, header_end):
    """Given header row range, build headers list and data list."""
    max_col = ws.max_column or 1
    max_row = ws.max_row or 1

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

    # Strip trailing blank Column_N headers
    while headers and headers[-1].startswith("Column_"):
        headers.pop()
    max_col = len(headers)

    # Deduplicate
    seen = {}
    for i, h in enumerate(headers):
        if h in seen:
            seen[h] += 1
            headers[i] = f"{h}_{seen[h]}"
        else:
            seen[h] = 0

    # Read data rows
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

    return headers, data


def _parse_excel_openpyxl(filepath, filename, header_row_override=None):
    """
    Parse Excel files using openpyxl to handle merged cells and multi-row headers.
    If header_row_override is provided (e.g. "3" or "3-4"), use that instead of auto-detect.
    """
    wb = load_workbook(filepath, read_only=False, data_only=True)
    sheet_names = wb.sheetnames
    ws = wb[sheet_names[0]]

    merge_map = _build_merge_map(ws)

    # Determine header rows
    if header_row_override:
        # Parse "3" or "3-4"
        parts = str(header_row_override).split("-")
        header_start = int(parts[0])
        header_end = int(parts[-1])
    else:
        header_start, header_end = _detect_header_block(ws, merge_map)

    headers, data = _build_headers_and_data(ws, merge_map, header_start, header_end)

    # Get preview rows for the UI (so user can see raw data and pick header row)
    preview = _extract_preview_rows(ws, merge_map)

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
        "preview": preview,
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


# ═══════════════════════════════════════════════════════════════════
# CSV / JSON PARSING
# ═══════════════════════════════════════════════════════════════════

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
