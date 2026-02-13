"""Flask application for ComprisonTool - Advanced File Comparison System."""

import os
import uuid
import json
from flask import Flask, render_template, request, jsonify, send_file
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
    """Re-parse an already uploaded file with a different header row."""
    body = request.get_json()
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    filepath = body.get("filepath")
    filename = body.get("filename")
    header_row = body.get("headerRow")

    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "File not found. Please re-upload."}), 404

    try:
        parsed = parse_file(filepath, filename, header_row=header_row)
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

    all_columns = list(dict.fromkeys(before_headers + after_headers))

    result = compare_datasets(before_data, after_data, key_column, all_columns)
    result["beforeFileName"] = before_name
    result["afterFileName"] = after_name

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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
