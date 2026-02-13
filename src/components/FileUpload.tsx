"use client";

import { useCallback, useState } from "react";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { parseFile, getSupportedExtensions } from "@/lib/fileParser";
import { ParsedFile } from "@/lib/types";

interface FileUploadProps {
  label: "before" | "after";
  onFileParsed: (parsed: ParsedFile) => void;
  parsed: ParsedFile | null;
}

export default function FileUpload({
  label,
  onFileParsed,
  parsed,
}: FileUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isBefore = label === "before";
  const accentColor = isBefore ? "#dc3545" : "#28a745";
  const labelText = isBefore ? "BEFORE (Original)" : "AFTER (Updated)";

  const handleFile = useCallback(
    async (file: File) => {
      setLoading(true);
      setError(null);
      try {
        const result = await parseFile(file);
        onFileParsed(result);
      } catch (e) {
        setError(
          e instanceof Error ? e.message : "Failed to parse file"
        );
      } finally {
        setLoading(false);
      }
    },
    [onFileParsed]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: accentColor }}
        />
        <h3 className="font-bold text-sm uppercase tracking-wider text-[#003366]">
          {labelText}
        </h3>
        {!isBefore && (
          <ArrowRight className="w-4 h-4 text-gray-400 -ml-1" />
        )}
      </div>

      <div
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center
          transition-all duration-200 cursor-pointer
          ${
            dragOver
              ? "drop-zone-active"
              : parsed
              ? "border-green-300 bg-green-50/50"
              : "border-gray-300 bg-white hover:border-[#0066cc] hover:bg-blue-50/30"
          }
        `}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() =>
          document.getElementById(`file-input-${label}`)?.click()
        }
      >
        <input
          id={`file-input-${label}`}
          type="file"
          className="hidden"
          accept={getSupportedExtensions().join(",")}
          onChange={handleInputChange}
        />

        {loading ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-10 h-10 text-[#0066cc] animate-spin" />
            <p className="text-sm text-gray-500">Parsing file...</p>
          </div>
        ) : parsed ? (
          <div className="flex flex-col items-center gap-3">
            <CheckCircle2 className="w-10 h-10 text-green-500" />
            <div>
              <p className="font-semibold text-gray-800 text-sm">
                {parsed.fileName}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {parsed.data.length} rows &middot; {parsed.headers.length}{" "}
                columns
                {parsed.sheetNames && (
                  <span> &middot; Sheet: {parsed.selectedSheet}</span>
                )}
              </p>
            </div>
            <p className="text-xs text-blue-500 mt-1">
              Click to replace file
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            {error ? (
              <>
                <XCircle className="w-10 h-10 text-red-400" />
                <p className="text-sm text-red-500">{error}</p>
                <p className="text-xs text-gray-400">Try another file</p>
              </>
            ) : (
              <>
                <div className="bg-gray-100 p-3 rounded-full">
                  {isBefore ? (
                    <FileSpreadsheet className="w-8 h-8 text-[#003366]" />
                  ) : (
                    <Upload className="w-8 h-8 text-[#003366]" />
                  )}
                </div>
                <div>
                  <p className="font-semibold text-gray-700 text-sm">
                    Drop file here or click to browse
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Supports: Excel (.xlsx, .xls), CSV, TSV, JSON
                  </p>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
