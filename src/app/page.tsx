"use client";

import { useState, useCallback, useMemo } from "react";
import {
  GitCompareArrows,
  Download,
  RotateCcw,
  BarChart3,
  Table,
  Loader2,
} from "lucide-react";
import Header from "@/components/Header";
import FileUpload from "@/components/FileUpload";
import KeyColumnSelector from "@/components/KeyColumnSelector";
import SummaryCards from "@/components/SummaryCards";
import ComparisonTable from "@/components/ComparisonTable";
import Dashboard from "@/components/Dashboard";
import { ParsedFile } from "@/lib/types";
import { ComparisonResult } from "@/lib/types";
import { compareFiles } from "@/lib/comparisonEngine";
import { exportComparisonToExcel } from "@/lib/excelExport";

type ViewMode = "table" | "dashboard";

export default function Home() {
  const [beforeFile, setBeforeFile] = useState<ParsedFile | null>(null);
  const [afterFile, setAfterFile] = useState<ParsedFile | null>(null);
  const [keyColumn, setKeyColumn] = useState<string>("");
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [comparing, setComparing] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Get common columns for key selection
  const commonColumns = useMemo(() => {
    if (!beforeFile || !afterFile) return [];
    return beforeFile.headers.filter((h) => afterFile.headers.includes(h));
  }, [beforeFile, afterFile]);

  // Auto-select first common column as key
  const handleBeforeParsed = useCallback(
    (parsed: ParsedFile) => {
      setBeforeFile(parsed);
      setResult(null);
      if (afterFile) {
        const common = parsed.headers.filter((h) =>
          afterFile.headers.includes(h)
        );
        if (common.length > 0 && !keyColumn) setKeyColumn(common[0]);
      }
    },
    [afterFile, keyColumn]
  );

  const handleAfterParsed = useCallback(
    (parsed: ParsedFile) => {
      setAfterFile(parsed);
      setResult(null);
      if (beforeFile) {
        const common = beforeFile.headers.filter((h) =>
          parsed.headers.includes(h)
        );
        if (common.length > 0 && !keyColumn) setKeyColumn(common[0]);
      }
    },
    [beforeFile, keyColumn]
  );

  const handleCompare = useCallback(async () => {
    if (!beforeFile || !afterFile || !keyColumn) return;
    setComparing(true);
    setTimeout(() => {
      const compResult = compareFiles(beforeFile, afterFile, keyColumn);
      setResult(compResult);
      setComparing(false);
    }, 100);
  }, [beforeFile, afterFile, keyColumn]);

  const handleExport = useCallback(async () => {
    if (!result) return;
    setExporting(true);
    try {
      const blob = await exportComparisonToExcel(result);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `comparison-report-${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }, [result]);

  const handleReset = useCallback(() => {
    setBeforeFile(null);
    setAfterFile(null);
    setKeyColumn("");
    setResult(null);
  }, []);

  return (
    <div className="min-h-screen bg-[#f8fafc]">
      <Header />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Step 1: File Upload */}
        {!result && (
          <div className="space-y-8">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-[#003366]">
                Upload Files to Compare
              </h2>
              <p className="text-sm text-gray-500 mt-2">
                Upload the original (before) and updated (after) files to begin
                comparison
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <FileUpload
                label="before"
                onFileParsed={handleBeforeParsed}
                parsed={beforeFile}
              />
              <FileUpload
                label="after"
                onFileParsed={handleAfterParsed}
                parsed={afterFile}
              />
            </div>

            {commonColumns.length > 0 && (
              <KeyColumnSelector
                columns={commonColumns}
                selected={keyColumn}
                onChange={setKeyColumn}
              />
            )}

            {beforeFile && afterFile && keyColumn && (
              <div className="flex justify-center animate-fade-in">
                <button
                  onClick={handleCompare}
                  disabled={comparing}
                  className="flex items-center gap-3 bg-[#003366] text-white px-8 py-3.5
                             rounded-xl font-bold text-sm uppercase tracking-wider
                             hover:bg-[#002244] transition-all shadow-lg
                             hover:shadow-xl disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {comparing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Comparing Files...
                    </>
                  ) : (
                    <>
                      <GitCompareArrows className="w-5 h-5" />
                      Run Comparison
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step 2: Results */}
        {result && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold text-[#003366]">
                  Comparison Results
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  {result.beforeFileName} vs {result.afterFileName}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex bg-gray-100 rounded-lg p-1">
                  <button
                    onClick={() => setViewMode("table")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold
                      transition-all ${
                        viewMode === "table"
                          ? "bg-white text-[#003366] shadow-sm"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                  >
                    <Table className="w-3.5 h-3.5" />
                    Table
                  </button>
                  <button
                    onClick={() => setViewMode("dashboard")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold
                      transition-all ${
                        viewMode === "dashboard"
                          ? "bg-white text-[#003366] shadow-sm"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                  >
                    <BarChart3 className="w-3.5 h-3.5" />
                    Dashboard
                  </button>
                </div>

                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="flex items-center gap-2 bg-[#28a745] text-white px-4 py-2
                             rounded-lg text-xs font-bold uppercase tracking-wider
                             hover:bg-green-600 transition-colors disabled:opacity-60"
                >
                  {exporting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4" />
                  )}
                  Export Excel
                </button>

                <button
                  onClick={handleReset}
                  className="flex items-center gap-2 bg-white text-gray-600 px-4 py-2
                             rounded-lg text-xs font-bold uppercase tracking-wider border
                             border-gray-300 hover:bg-gray-50 transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  New Comparison
                </button>
              </div>
            </div>

            <SummaryCards result={result} />

            {viewMode === "table" ? (
              <ComparisonTable result={result} />
            ) : (
              <Dashboard result={result} />
            )}
          </div>
        )}
      </main>

      <footer className="border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-6 py-4 text-center text-xs text-gray-400">
          ComprisonTool &copy; {new Date().getFullYear()} &mdash; Advanced File
          Comparison System
        </div>
      </footer>
    </div>
  );
}
