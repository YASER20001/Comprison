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
    """Upload and parse a file. Returns headers, row count, etc."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if f".{ext}" not in SUPPORTED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    # Save to temp location
    uid = str(uuid.uuid4())
    safe_name = f"{uid}.{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
    file.save(filepath)

    try:
        parsed = parse_file(filepath, file.filename)
        # Store filepath for later use
        parsed["_filepath"] = filepath
        parsed["_uid"] = uid
        return jsonify(parsed)
    except Exception as e:
        os.remove(filepath)
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
