"""File parsing module supporting Excel, CSV, TSV, and JSON files."""

import json
import pandas as pd


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

    if ext in ("xlsx", "xls", "xlsm", "xlsb"):
        return _parse_excel(filepath, filename)
    elif ext == "csv":
        return _parse_csv(filepath, filename)
    elif ext == "tsv":
        return _parse_csv(filepath, filename, sep="\t")
    elif ext == "json":
        return _parse_json(filepath, filename)
    else:
        # Try CSV as fallback
        return _parse_csv(filepath, filename)


def _parse_excel(filepath, filename):
    """Parse Excel files (.xlsx, .xls, etc.)."""
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
