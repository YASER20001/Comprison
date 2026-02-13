export type ChangeStatus = "added" | "deleted" | "modified" | "unchanged";

export interface CellChange {
  column: string;
  oldValue: string | number | boolean | null;
  newValue: string | number | boolean | null;
}

export interface ComparisonRow {
  rowIndex: number;
  status: ChangeStatus;
  keyValue: string;
  beforeData: Record<string, unknown> | null;
  afterData: Record<string, unknown> | null;
  changes: CellChange[];
}

export interface ComparisonResult {
  columns: string[];
  keyColumn: string;
  rows: ComparisonRow[];
  summary: {
    total: number;
    added: number;
    deleted: number;
    modified: number;
    unchanged: number;
  };
  beforeFileName: string;
  afterFileName: string;
  comparedAt: string;
}

export interface ParsedFile {
  fileName: string;
  headers: string[];
  data: Record<string, unknown>[];
  sheetNames?: string[];
  selectedSheet?: string;
}

export interface UploadedFile {
  file: File;
  label: "before" | "after";
  parsed?: ParsedFile;
}
