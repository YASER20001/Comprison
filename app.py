"""Flask application for ComprisonTool - Advanced File Comparison System."""

import os
import uuid
import json
from flask import Flask, render_template, request, jsonify, send_file
from openpyxl.utils import get_column_letter
from file_parser import parse_file, SUPPORTED_EXTENSIONS
from comparison_engine import compare_datasets, stringify
from excel_export import export_comparison

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# In-memory store for comparison results (keyed by session id)
_results_store = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Upload and parse a file. Returns headers, row count, preview, etc."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if f".{ext}" not in SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    header_row = request.form.get("headerRow")  # Optional manual override

    # Save to temp location
    uid = str(uuid.uuid4())
    safe_name = f"{uid}.{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
    file.save(filepath)

    try:
        parsed = parse_file(filepath, file.filename, header_row=header_row)
        # Store filepath for later re-parsing
        parsed["_filepath"] = filepath
        parsed["_uid"] = uid
        return jsonify(parsed)
    except Exception as e:
        os.remove(filepath)
        return jsonify({"error": str(e)}), 400


@app.route("/api/reparse", methods=["POST"])
def reparse_file():
    """Re-parse an already uploaded file with a different header row or transpose mode."""
    body = request.get_json()
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    filepath = body.get("filepath")
    filename = body.get("filename")
    header_row = body.get("headerRow")
    transpose = body.get("transpose", False)

    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "File not found. Please re-upload."}), 404

    try:
        parsed = parse_file(filepath, filename, header_row=header_row, transpose=transpose)
        parsed["_filepath"] = filepath
        return jsonify(parsed)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/compare", methods=["POST"])
def compare():
    """Compare two uploaded files."""
    body = request.get_json()
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    before_data = body.get("beforeData", [])
    after_data = body.get("afterData", [])
    key_column = body.get("keyColumn", "")
    before_headers = body.get("beforeHeaders", [])
    after_headers = body.get("afterHeaders", [])
    before_name = body.get("beforeFileName", "before")
    after_name = body.get("afterFileName", "after")

    if not key_column:
        return jsonify({"error": "keyColumn is required"}), 400

    # Debug logging
    print(f"[COMPARE] before_data: {len(before_data)} records, after_data: {len(after_data)} records")
    print(f"[COMPARE] key_column: '{key_column}'")
    print(f"[COMPARE] before_headers: {before_headers[:5]}...")
    print(f"[COMPARE] after_headers: {after_headers[:5]}...")
    if before_data:
        print(f"[COMPARE] Sample before record keys: {list(before_data[0].keys())[:5]}...")
        print(f"[COMPARE] Sample before key value: '{before_data[0].get(key_column, 'NOT FOUND')}'")

    all_columns = list(dict.fromkeys(before_headers + after_headers))

    # Diagnostic: check key column values before comparison
    before_key_vals = [stringify(r.get(key_column, "")) for r in before_data]
    after_key_vals = [stringify(r.get(key_column, "")) for r in after_data]
    before_non_empty = [v for v in before_key_vals if v]
    after_non_empty = [v for v in after_key_vals if v]

    print(f"[COMPARE] Key '{key_column}': before has {len(before_non_empty)}/{len(before_data)} non-empty, after has {len(after_non_empty)}/{len(after_data)} non-empty")
    if before_non_empty:
        print(f"[COMPARE] Sample before keys: {before_non_empty[:3]}")
    if after_non_empty:
        print(f"[COMPARE] Sample after keys: {after_non_empty[:3]}")

    # If key column has 0 values, check if the key exists in record keys at all
    if not before_non_empty and before_data:
        record_keys = list(before_data[0].keys())
        print(f"[COMPARE] WARNING: Key column '{key_column}' has NO values in before data!")
        print(f"[COMPARE] Available record keys: {record_keys}")
        # Check for similar key names (case/whitespace differences)
        for k in record_keys:
            if k.strip().lower() == key_column.strip().lower() and k != key_column:
                print(f"[COMPARE] FOUND similar key: '{k}' vs requested '{key_column}'")

    result = compare_datasets(before_data, after_data, key_column, all_columns)
    result["beforeFileName"] = before_name
    result["afterFileName"] = after_name

    # If 0 results, include diagnostic info in response
    if result["summary"]["total"] == 0:
        # Gather diagnostic info
        diag_keys = list(before_data[0].keys()) if before_data else []
        diag_sample = {}
        if before_data:
            for k, v in before_data[0].items():
                diag_sample[k] = v[:50] if isinstance(v, str) and len(v) > 50 else v
        result["diagnostic"] = {
            "message": f"Key column '{key_column}' produced 0 matches",
            "beforeKeyNonEmpty": len(before_non_empty),
            "afterKeyNonEmpty": len(after_non_empty),
            "beforeRecordKeys": diag_keys,
            "sampleRecord": diag_sample,
            "sampleBeforeKeyValues": before_key_vals[:5],
            "sampleAfterKeyValues": after_key_vals[:5],
        }

    # Store for export
    session_id = str(uuid.uuid4())
    _results_store[session_id] = result

    result["sessionId"] = session_id
    return jsonify(result)


@app.route("/api/export/<session_id>")
def export_excel(session_id):
    """Export comparison result as color-coded Excel file."""
    result = _results_store.get(session_id)
    if not result:
        return jsonify({"error": "Session not found. Please run comparison again."}), 404

    buffer = export_comparison(
        result,
        result.get("beforeFileName", "before"),
        result.get("afterFileName", "after"),
    )

    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"comparison-report.xlsx",
    )


@app.route("/debug")
def debug_page():
    return render_template("debug.html")


@app.route("/api/debug-upload", methods=["POST"])
def debug_upload():
    """Debug endpoint: shows raw cell values for the first 15 rows of an Excel file."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    uid = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "xlsx"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"{uid}.{ext}")
    file.save(filepath)

    try:
        from openpyxl import load_workbook
        from openpyxl.utils import range_boundaries
        from file_parser import (
            _build_merge_map, _get_merged_cell_value,
            _strategy_autofilter, _strategy_tables,
            _strategy_formatting, _strategy_merges,
            _strategy_content_pattern, _detect_header_block,
        )

        wb = load_workbook(filepath, read_only=False, data_only=True)
        ws = wb[wb.sheetnames[0]]
        merge_map = _build_merge_map(ws)

        max_col = min(ws.max_column or 1, 40)
        max_row = min(ws.max_row or 1, 15)

        rows = []
        for r in range(1, max_row + 1):
            cells = []
            for c in range(1, max_col + 1):
                raw = ws.cell(row=r, column=c).value
                resolved = _get_merged_cell_value(ws, r, c, merge_map)
                cell = ws.cell(row=r, column=c)
                bold = cell.font.bold if cell.font else False
                fill_rgb = None
                if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb:
                    rgb = str(cell.fill.fgColor.rgb)
                    if rgb not in ("00000000", "0", "None", "00FFFFFF"):
                        fill_rgb = rgb
                cells.append({
                    "col": c,
                    "raw": str(raw) if raw is not None else None,
                    "resolved": str(resolved) if resolved is not None else None,
                    "bold": bold,
                    "fill": fill_rgb,
                })
            rows.append({"row": r, "cells": cells})

        # Show merged ranges
        merges = [str(m) for m in ws.merged_cells.ranges]

        # Show detection results
        af_ref = str(ws.auto_filter.ref) if ws.auto_filter and ws.auto_filter.ref else None
        table_refs = []
        if hasattr(ws, 'tables') and ws.tables:
            for t in ws.tables.values():
                table_refs.append(str(t.ref))

        strategies = {
            "autofilter": {"ref": af_ref, "result": _strategy_autofilter(ws)},
            "tables": {"refs": table_refs, "result": _strategy_tables(ws)},
            "formatting": {"result": _strategy_formatting(ws, merge_map)},
            "merges": {"result": _strategy_merges(ws, merge_map)},
            "content_pattern": {"result": _strategy_content_pattern(ws, merge_map)},
        }

        header_start, header_end = _detect_header_block(ws, merge_map)

        wb.close()
        os.remove(filepath)

        return jsonify({
            "sheetName": wb.sheetnames[0] if wb.sheetnames else "",
            "allSheets": wb.sheetnames,
            "maxRow": ws.max_row,
            "maxCol": ws.max_column,
            "mergedRanges": merges,
            "rows": rows,
            "strategies": strategies,
            "detectedHeaders": f"rows {header_start}-{header_end}",
        })
    except Exception as e:
        os.remove(filepath)
        return jsonify({"error": str(e)}), 400


@app.route("/api/diagnose", methods=["POST"])
def diagnose_file():
    """Scan an uploaded file and report ALL cell values, searching for specific fields."""
    body = request.get_json()
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    filepath = body.get("filepath")
    search_field = body.get("searchField", "SP ID")

    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "File not found. Please re-upload."}), 404

    try:
        from openpyxl import load_workbook

        wb_data = load_workbook(filepath, read_only=False, data_only=True)
        wb_raw = load_workbook(filepath, read_only=False, data_only=False)
        ws_data = wb_data[wb_data.sheetnames[0]]
        ws_raw = wb_raw[wb_raw.sheetnames[0]]

        max_row = ws_data.max_row or 1
        max_col = ws_data.max_column or 1

        result = {
            "sheet": wb_data.sheetnames[0],
            "allSheets": wb_data.sheetnames,
            "maxRow": max_row,
            "maxCol": max_col,
            "mergedRanges": [str(m) for m in ws_data.merged_cells.ranges],
            "searchField": search_field,
            "found": [],
        }

        # Scan EVERY cell for the search field
        for r in range(1, min(max_row + 1, 500)):
            for c in range(1, min(max_col + 1, 500)):
                val_data = ws_data.cell(row=r, column=c).value
                val_raw = ws_raw.cell(row=r, column=c).value

                for val in [val_data, val_raw]:
                    if val is not None and search_field.lower() in str(val).lower():
                        # Found the field! Get surrounding values
                        neighbors = {}
                        for dc in range(0, min(6, max_col - c + 1)):
                            neighbor_data = ws_data.cell(row=r, column=c + dc).value
                            neighbor_raw = ws_raw.cell(row=r, column=c + dc).value
                            col_letter = get_column_letter(c + dc)
                            neighbors[f"{col_letter}{r}"] = {
                                "data_only": str(neighbor_data) if neighbor_data is not None else None,
                                "raw": str(neighbor_raw) if neighbor_raw is not None else None,
                            }

                        # Also get values in the same column below (if field is a header)
                        below = {}
                        for dr in range(1, min(6, max_row - r + 1)):
                            below_data = ws_data.cell(row=r + dr, column=c).value
                            below_raw = ws_raw.cell(row=r + dr, column=c).value
                            below[f"row{r+dr}"] = {
                                "data_only": str(below_data) if below_data is not None else None,
                                "raw": str(below_raw) if below_raw is not None else None,
                            }

                        # Also get values in the same row to the right (if field is a row header)
                        right = {}
                        for dc in range(1, min(6, max_col - c + 1)):
                            right_data = ws_data.cell(row=r, column=c + dc).value
                            right_raw = ws_raw.cell(row=r, column=c + dc).value
                            col_letter = get_column_letter(c + dc)
                            right[f"{col_letter}{r}"] = {
                                "data_only": str(right_data) if right_data is not None else None,
                                "raw": str(right_raw) if right_raw is not None else None,
                            }

                        result["found"].append({
                            "row": r,
                            "col": c,
                            "colLetter": get_column_letter(c),
                            "cellRef": f"{get_column_letter(c)}{r}",
                            "value_data_only": str(val_data) if val_data is not None else None,
                            "value_raw": str(val_raw) if val_raw is not None else None,
                            "neighbors": neighbors,
                            "below": below,
                            "right": right,
                        })
                        break  # Don't report same cell twice

        # Also dump column A values (all field names in transposed mode)
        col_a_values = []
        for r in range(1, min(max_row + 1, 100)):
            val = ws_data.cell(row=r, column=1).value
            val_raw = ws_raw.cell(row=r, column=1).value
            effective = val if val is not None else val_raw
            col_a_values.append({
                "row": r,
                "value": str(effective).strip() if effective is not None else None,
            })

        result["columnA"] = col_a_values

        wb_data.close()
        wb_raw.close()

        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 400


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
