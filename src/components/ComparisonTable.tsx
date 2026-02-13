"use client";

import { useState, useMemo } from "react";
import {
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  ArrowRight,
} from "lucide-react";
import { ComparisonResult, ComparisonRow, ChangeStatus } from "@/lib/types";

interface ComparisonTableProps {
  result: ComparisonResult;
}

const STATUS_CONFIG: Record<
  ChangeStatus,
  { label: string; rowClass: string; badgeClass: string }
> = {
  added: {
    label: "ADDED",
    rowClass: "row-added",
    badgeClass: "badge-added",
  },
  deleted: {
    label: "DELETED",
    rowClass: "row-deleted",
    badgeClass: "badge-deleted",
  },
  modified: {
    label: "MODIFIED",
    rowClass: "row-modified",
    badgeClass: "badge-modified",
  },
  unchanged: {
    label: "NO CHANGE",
    rowClass: "row-unchanged",
    badgeClass: "badge-unchanged",
  },
};

function stringify(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

export default function ComparisonTable({ result }: ComparisonTableProps) {
  const [filter, setFilter] = useState<ChangeStatus | "all">("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const filteredRows = useMemo(() => {
    let rows = result.rows;
    if (filter !== "all") {
      rows = rows.filter((r) => r.status === filter);
    }
    if (searchTerm) {
      const lower = searchTerm.toLowerCase();
      rows = rows.filter((r) => {
        const data = r.afterData || r.beforeData || {};
        return (
          r.keyValue.toLowerCase().includes(lower) ||
          Object.values(data).some((v) =>
            stringify(v).toLowerCase().includes(lower)
          )
        );
      });
    }
    return rows;
  }, [result.rows, filter, searchTerm]);

  const pagedRows = filteredRows.slice(
    page * pageSize,
    (page + 1) * pageSize
  );
  const totalPages = Math.ceil(filteredRows.length / pageSize);

  return (
    <div className="animate-fade-in">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search records..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(0);
            }}
            className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm
                       focus:outline-none focus:ring-2 focus:ring-[#0066cc] bg-white"
          />
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          {(["all", "added", "deleted", "modified", "unchanged"] as const).map(
            (f) => (
              <button
                key={f}
                onClick={() => {
                  setFilter(f);
                  setPage(0);
                }}
                className={`
                  px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide
                  transition-all border
                  ${
                    filter === f
                      ? f === "all"
                        ? "bg-[#003366] text-white border-[#003366]"
                        : f === "added"
                        ? "bg-green-100 text-green-700 border-green-300"
                        : f === "deleted"
                        ? "bg-red-100 text-red-700 border-red-300"
                        : f === "modified"
                        ? "bg-orange-100 text-orange-700 border-orange-300"
                        : "bg-gray-200 text-gray-600 border-gray-300"
                      : "bg-white text-gray-500 border-gray-200 hover:bg-gray-50"
                  }
                `}
              >
                {f === "all" ? "All" : f}
              </button>
            )
          )}
        </div>
      </div>

      {/* Results count */}
      <p className="text-xs text-gray-500 mb-2">
        Showing {pagedRows.length} of {filteredRows.length} records
        {filter !== "all" && (
          <span className="ml-1">(filtered by: {filter})</span>
        )}
      </p>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
        <table className="comparison-table w-full text-sm">
          <thead>
            <tr>
              <th className="px-4 py-3 text-left sticky left-0 z-10">
                Status
              </th>
              <th className="px-4 py-3 text-left">{result.keyColumn}</th>
              {result.columns
                .filter((c) => c !== result.keyColumn)
                .map((col) => (
                  <th key={col} className="px-4 py-3 text-left whitespace-nowrap">
                    {col}
                  </th>
                ))}
              <th className="px-4 py-3 text-center w-10" />
            </tr>
          </thead>
          <tbody>
            {pagedRows.map((row, idx) => (
              <TableRow
                key={`${row.keyValue}-${idx}`}
                row={row}
                columns={result.columns.filter(
                  (c) => c !== result.keyColumn
                )}
                keyColumn={result.keyColumn}
                isExpanded={expandedRow === idx}
                onToggle={() =>
                  setExpandedRow(expandedRow === idx ? null : idx)
                }
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg
                       disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg
                       disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function TableRow({
  row,
  columns,
  keyColumn,
  isExpanded,
  onToggle,
}: {
  row: ComparisonRow;
  columns: string[];
  keyColumn: string;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const config = STATUS_CONFIG[row.status];
  const data = row.afterData || row.beforeData || {};
  const changedCols = new Set(row.changes.map((c) => c.column));

  return (
    <>
      <tr className={`${config.rowClass} transition-colors`}>
        <td className="px-4 py-2.5 sticky left-0 z-10">
          <span
            className={`${config.badgeClass} px-2 py-0.5 rounded text-xs font-bold`}
          >
            {config.label}
          </span>
        </td>
        <td className="px-4 py-2.5 font-medium text-gray-800">
          {row.keyValue}
        </td>
        {columns.map((col) => {
          const isChanged = changedCols.has(col);
          return (
            <td
              key={col}
              className={`px-4 py-2.5 whitespace-nowrap ${
                isChanged ? "font-semibold text-orange-700" : "text-gray-600"
              }`}
            >
              {isChanged ? (
                <span className="flex items-center gap-1">
                  <span className="line-through text-red-400 text-xs">
                    {stringify(
                      row.changes.find((c) => c.column === col)?.oldValue
                    )}
                  </span>
                  <ArrowRight className="w-3 h-3 text-orange-400" />
                  <span className="text-green-600">
                    {stringify(
                      row.changes.find((c) => c.column === col)?.newValue
                    )}
                  </span>
                </span>
              ) : (
                stringify(data[col])
              )}
            </td>
          );
        })}
        <td className="px-4 py-2.5 text-center">
          {row.status === "modified" && row.changes.length > 0 && (
            <button
              onClick={onToggle}
              className="text-gray-400 hover:text-[#003366] transition-colors"
            >
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
          )}
        </td>
      </tr>
      {isExpanded && row.status === "modified" && (
        <tr className="bg-orange-50/50">
          <td
            colSpan={columns.length + 3}
            className="px-6 py-3"
          >
            <div className="text-xs font-bold text-[#003366] uppercase tracking-wider mb-2">
              Change Details
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {row.changes.map((change) => (
                <div
                  key={change.column}
                  className="bg-white rounded-lg border border-orange-200 p-3"
                >
                  <p className="text-xs font-semibold text-gray-500 uppercase">
                    {change.column}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-sm text-red-500 line-through">
                      {stringify(change.oldValue) || "(empty)"}
                    </span>
                    <ArrowRight className="w-3 h-3 text-orange-400 shrink-0" />
                    <span className="text-sm text-green-600 font-medium">
                      {stringify(change.newValue) || "(empty)"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
