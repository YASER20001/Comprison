import {
  ComparisonResult,
  ComparisonRow,
  CellChange,
  ParsedFile,
} from "./types";

function stringify(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

export function compareFiles(
  before: ParsedFile,
  after: ParsedFile,
  keyColumn: string
): ComparisonResult {
  const allColumns = Array.from(
    new Set([...before.headers, ...after.headers])
  );

  // Build maps keyed by the key column
  const beforeMap = new Map<string, Record<string, unknown>>();
  const afterMap = new Map<string, Record<string, unknown>>();

  for (const row of before.data) {
    const key = stringify(row[keyColumn]);
    if (key) beforeMap.set(key, row);
  }

  for (const row of after.data) {
    const key = stringify(row[keyColumn]);
    if (key) afterMap.set(key, row);
  }

  const allKeys = Array.from(
    new Set([...beforeMap.keys(), ...afterMap.keys()])
  );

  const rows: ComparisonRow[] = [];
  let added = 0;
  let deleted = 0;
  let modified = 0;
  let unchanged = 0;

  for (let i = 0; i < allKeys.length; i++) {
    const key = allKeys[i];
    const beforeRow = beforeMap.get(key) || null;
    const afterRow = afterMap.get(key) || null;

    if (!beforeRow && afterRow) {
      // Added
      rows.push({
        rowIndex: i,
        status: "added",
        keyValue: key,
        beforeData: null,
        afterData: afterRow,
        changes: [],
      });
      added++;
    } else if (beforeRow && !afterRow) {
      // Deleted
      rows.push({
        rowIndex: i,
        status: "deleted",
        keyValue: key,
        beforeData: beforeRow,
        afterData: null,
        changes: [],
      });
      deleted++;
    } else if (beforeRow && afterRow) {
      // Check for modifications
      const changes: CellChange[] = [];
      for (const col of allColumns) {
        const oldVal = stringify(beforeRow[col]);
        const newVal = stringify(afterRow[col]);
        if (oldVal !== newVal) {
          changes.push({
            column: col,
            oldValue: beforeRow[col] as string | number | boolean | null,
            newValue: afterRow[col] as string | number | boolean | null,
          });
        }
      }

      if (changes.length > 0) {
        rows.push({
          rowIndex: i,
          status: "modified",
          keyValue: key,
          beforeData: beforeRow,
          afterData: afterRow,
          changes,
        });
        modified++;
      } else {
        rows.push({
          rowIndex: i,
          status: "unchanged",
          keyValue: key,
          beforeData: beforeRow,
          afterData: afterRow,
          changes: [],
        });
        unchanged++;
      }
    }
  }

  // Sort: deleted first, modified, added, unchanged
  const statusOrder = { deleted: 0, modified: 1, added: 2, unchanged: 3 };
  rows.sort((a, b) => statusOrder[a.status] - statusOrder[b.status]);

  return {
    columns: allColumns,
    keyColumn,
    rows,
    summary: {
      total: allKeys.length,
      added,
      deleted,
      modified,
      unchanged,
    },
    beforeFileName: before.fileName,
    afterFileName: after.fileName,
    comparedAt: new Date().toISOString(),
  };
}
