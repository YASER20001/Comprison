import ExcelJS from "exceljs";
import { ComparisonResult } from "./types";

const COLORS = {
  added: { bg: "C6EFCE", font: "006100", label: "ADDED" },
  deleted: { bg: "FFC7CE", font: "9C0006", label: "DELETED" },
  modified: { bg: "FFE0B2", font: "E65100", label: "MODIFIED" },
  unchanged: { bg: "E0E0E0", font: "424242", label: "NO CHANGE" },
  headerBg: "003366",
  headerFont: "FFFFFF",
};

function stringify(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

export async function exportComparisonToExcel(
  result: ComparisonResult
): Promise<Blob> {
  const workbook = new ExcelJS.Workbook();

  // ── Sheet 1: Summary Dashboard ──
  const summarySheet = workbook.addWorksheet("Summary", {
    properties: { tabColor: { argb: "003366" } },
  });

  summarySheet.columns = [
    { header: "", key: "label", width: 25 },
    { header: "", key: "value", width: 30 },
  ];

  const titleRow = summarySheet.addRow(["FILE COMPARISON REPORT", ""]);
  titleRow.font = { bold: true, size: 16, color: { argb: "003366" } };
  summarySheet.mergeCells("A1:B1");

  summarySheet.addRow([]);
  summarySheet.addRow(["Before File:", result.beforeFileName]);
  summarySheet.addRow(["After File:", result.afterFileName]);
  summarySheet.addRow(["Compared At:", new Date(result.comparedAt).toLocaleString()]);
  summarySheet.addRow(["Key Column:", result.keyColumn]);
  summarySheet.addRow([]);

  const statsHeader = summarySheet.addRow(["CHANGE SUMMARY", ""]);
  statsHeader.font = { bold: true, size: 13, color: { argb: "003366" } };
  summarySheet.mergeCells(`A${statsHeader.number}:B${statsHeader.number}`);

  summarySheet.addRow([]);

  const statsRows = [
    ["Total Records", result.summary.total],
    ["Added (New)", result.summary.added],
    ["Deleted (Removed)", result.summary.deleted],
    ["Modified (Changed)", result.summary.modified],
    ["Unchanged", result.summary.unchanged],
  ];

  const statColors: Record<string, string> = {
    "Added (New)": COLORS.added.bg,
    "Deleted (Removed)": COLORS.deleted.bg,
    "Modified (Changed)": COLORS.modified.bg,
    Unchanged: COLORS.unchanged.bg,
  };

  for (const [label, value] of statsRows) {
    const row = summarySheet.addRow([label, value]);
    row.font = { bold: true, size: 11 };
    const colorKey = label as string;
    if (statColors[colorKey]) {
      row.getCell(1).fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: { argb: statColors[colorKey] },
      };
      row.getCell(2).fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: { argb: statColors[colorKey] },
      };
    }
  }

  // ── Sheet 2: Detailed Comparison ──
  const detailSheet = workbook.addWorksheet("Comparison Details", {
    properties: { tabColor: { argb: "0066CC" } },
  });

  const detailHeaders = ["Status", "Key", ...result.columns];
  const headerRow = detailSheet.addRow(detailHeaders);

  headerRow.eachCell((cell) => {
    cell.fill = {
      type: "pattern",
      pattern: "solid",
      fgColor: { argb: COLORS.headerBg },
    };
    cell.font = { bold: true, color: { argb: COLORS.headerFont }, size: 11 };
    cell.alignment = { horizontal: "center", vertical: "middle" };
    cell.border = {
      bottom: { style: "thin", color: { argb: "000000" } },
    };
  });

  // Set column widths
  detailSheet.columns = detailHeaders.map((h) => ({
    header: h,
    key: h,
    width: Math.max(15, h.length + 5),
  }));

  for (const compRow of result.rows) {
    const color = COLORS[compRow.status];
    const data = compRow.afterData || compRow.beforeData || {};
    const rowValues: string[] = [
      color.label,
      compRow.keyValue,
      ...result.columns.map((col) => stringify(data[col])),
    ];

    const excelRow = detailSheet.addRow(rowValues);

    excelRow.eachCell((cell) => {
      cell.fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: { argb: color.bg },
      };
      cell.font = { color: { argb: color.font } };
      cell.border = {
        bottom: { style: "hair", color: { argb: "CCCCCC" } },
      };
    });

    // Highlight modified cells specifically
    if (compRow.status === "modified") {
      for (const change of compRow.changes) {
        const colIdx = result.columns.indexOf(change.column);
        if (colIdx >= 0) {
          const cell = excelRow.getCell(colIdx + 3); // +3 for Status and Key columns
          cell.value = `${stringify(change.oldValue)} → ${stringify(change.newValue)}`;
          cell.font = { bold: true, color: { argb: "E65100" } };
          cell.fill = {
            type: "pattern",
            pattern: "solid",
            fgColor: { argb: "FFD180" },
          };
        }
      }
    }
  }

  // Auto-filter
  detailSheet.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: result.rows.length + 1, column: detailHeaders.length },
  };

  // Freeze the header row
  detailSheet.views = [{ state: "frozen", ySplit: 1, xSplit: 2 }];

  // ── Sheet 3: Changes Only ──
  const changesSheet = workbook.addWorksheet("Changes Only", {
    properties: { tabColor: { argb: "F58220" } },
  });

  const changesHeaders = ["Status", "Key", "Column", "Before Value", "After Value"];
  const changesHeaderRow = changesSheet.addRow(changesHeaders);

  changesHeaderRow.eachCell((cell) => {
    cell.fill = {
      type: "pattern",
      pattern: "solid",
      fgColor: { argb: COLORS.headerBg },
    };
    cell.font = { bold: true, color: { argb: COLORS.headerFont }, size: 11 };
    cell.alignment = { horizontal: "center", vertical: "middle" };
  });

  changesSheet.columns = [
    { header: "Status", key: "Status", width: 15 },
    { header: "Key", key: "Key", width: 25 },
    { header: "Column", key: "Column", width: 25 },
    { header: "Before Value", key: "Before Value", width: 30 },
    { header: "After Value", key: "After Value", width: 30 },
  ];

  for (const compRow of result.rows) {
    if (compRow.status === "unchanged") continue;

    if (compRow.status === "modified") {
      for (const change of compRow.changes) {
        const row = changesSheet.addRow([
          COLORS.modified.label,
          compRow.keyValue,
          change.column,
          stringify(change.oldValue),
          stringify(change.newValue),
        ]);
        row.eachCell((cell) => {
          cell.fill = {
            type: "pattern",
            pattern: "solid",
            fgColor: { argb: COLORS.modified.bg },
          };
          cell.font = { color: { argb: COLORS.modified.font } };
        });
      }
    } else {
      const color = COLORS[compRow.status];
      const row = changesSheet.addRow([
        color.label,
        compRow.keyValue,
        "—",
        compRow.status === "deleted" ? "(entire row)" : "",
        compRow.status === "added" ? "(entire row)" : "",
      ]);
      row.eachCell((cell) => {
        cell.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: { argb: color.bg },
        };
        cell.font = { color: { argb: color.font } };
      });
    }
  }

  changesSheet.views = [{ state: "frozen", ySplit: 1 }];

  // Generate the file
  const arrayBuffer = await workbook.xlsx.writeBuffer();
  return new Blob([arrayBuffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}
