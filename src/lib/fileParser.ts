import * as XLSX from "xlsx";
import { ParsedFile } from "./types";

export function parseExcelBuffer(
  buffer: ArrayBuffer,
  fileName: string,
  sheetName?: string
): ParsedFile {
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheetNames = workbook.SheetNames;
  const selected = sheetName || sheetNames[0];
  const worksheet = workbook.Sheets[selected];
  const jsonData = XLSX.utils.sheet_to_json<Record<string, unknown>>(worksheet, {
    defval: "",
  });
  const headers =
    jsonData.length > 0 ? Object.keys(jsonData[0]) : [];

  return {
    fileName,
    headers,
    data: jsonData,
    sheetNames,
    selectedSheet: selected,
  };
}

export function parseCSVBuffer(
  buffer: ArrayBuffer,
  fileName: string
): ParsedFile {
  const workbook = XLSX.read(buffer, { type: "array" });
  const worksheet = workbook.Sheets[workbook.SheetNames[0]];
  const jsonData = XLSX.utils.sheet_to_json<Record<string, unknown>>(worksheet, {
    defval: "",
  });
  const headers =
    jsonData.length > 0 ? Object.keys(jsonData[0]) : [];

  return {
    fileName,
    headers,
    data: jsonData,
  };
}

export function parseJSONBuffer(
  buffer: ArrayBuffer,
  fileName: string
): ParsedFile {
  const text = new TextDecoder().decode(buffer);
  const parsed = JSON.parse(text);
  const data: Record<string, unknown>[] = Array.isArray(parsed)
    ? parsed
    : [parsed];
  const headers = data.length > 0 ? Object.keys(data[0]) : [];

  return {
    fileName,
    headers,
    data,
  };
}

export async function parseFile(
  file: File,
  sheetName?: string
): Promise<ParsedFile> {
  const buffer = await file.arrayBuffer();
  const ext = file.name.split(".").pop()?.toLowerCase() || "";

  if (["xlsx", "xls", "xlsm", "xlsb"].includes(ext)) {
    return parseExcelBuffer(buffer, file.name, sheetName);
  } else if (ext === "csv" || ext === "tsv") {
    return parseCSVBuffer(buffer, file.name);
  } else if (ext === "json") {
    return parseJSONBuffer(buffer, file.name);
  } else {
    // Try to parse as CSV by default
    return parseCSVBuffer(buffer, file.name);
  }
}

export function getSupportedExtensions(): string[] {
  return [".xlsx", ".xls", ".xlsm", ".xlsb", ".csv", ".tsv", ".json"];
}
