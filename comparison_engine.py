"""Core comparison engine for detecting changes between two datasets."""

from datetime import datetime


def stringify(value):
    """Convert any value to string for comparison."""
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return ""
    return str(value)


def compare_datasets(before_data, after_data, key_column, columns):
    """
    Compare two datasets row-by-row using a key column.

    Returns a dict with:
      - columns: list of all column names
      - keyColumn: the key column used
      - rows: list of comparison row dicts
      - summary: counts of added/deleted/modified/unchanged
    """
    # Build lookup maps
    before_map = {}
    for row in before_data:
        key = stringify(row.get(key_column, ""))
        if key:
            before_map[key] = row

    after_map = {}
    for row in after_data:
        key = stringify(row.get(key_column, ""))
        if key:
            after_map[key] = row

    all_keys = list(dict.fromkeys(list(before_map.keys()) + list(after_map.keys())))

    rows = []
    added = 0
    deleted = 0
    modified = 0
    unchanged = 0

    for i, key in enumerate(all_keys):
        before_row = before_map.get(key)
        after_row = after_map.get(key)

        if before_row is None and after_row is not None:
            rows.append({
                "rowIndex": i,
                "status": "added",
                "keyValue": key,
                "beforeData": None,
                "afterData": after_row,
                "changes": [],
            })
            added += 1

        elif before_row is not None and after_row is None:
            rows.append({
                "rowIndex": i,
                "status": "deleted",
                "keyValue": key,
                "beforeData": before_row,
                "afterData": None,
                "changes": [],
            })
            deleted += 1

        elif before_row is not None and after_row is not None:
            changes = []
            for col in columns:
                old_val = stringify(before_row.get(col, ""))
                new_val = stringify(after_row.get(col, ""))
                if old_val != new_val:
                    changes.append({
                        "column": col,
                        "oldValue": before_row.get(col, ""),
                        "newValue": after_row.get(col, ""),
                    })

            if changes:
                rows.append({
                    "rowIndex": i,
                    "status": "modified",
                    "keyValue": key,
                    "beforeData": before_row,
                    "afterData": after_row,
                    "changes": changes,
                })
                modified += 1
            else:
                rows.append({
                    "rowIndex": i,
                    "status": "unchanged",
                    "keyValue": key,
                    "beforeData": before_row,
                    "afterData": after_row,
                    "changes": [],
                })
                unchanged += 1

    # Sort: deleted, modified, added, unchanged
    status_order = {"deleted": 0, "modified": 1, "added": 2, "unchanged": 3}
    rows.sort(key=lambda r: status_order.get(r["status"], 4))

    return {
        "columns": columns,
        "keyColumn": key_column,
        "rows": rows,
        "summary": {
            "total": len(all_keys),
            "added": added,
            "deleted": deleted,
            "modified": modified,
            "unchanged": unchanged,
        },
        "comparedAt": datetime.now().isoformat(),
    }
