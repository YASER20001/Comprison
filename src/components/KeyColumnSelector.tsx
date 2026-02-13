"use client";

import { Key } from "lucide-react";

interface KeyColumnSelectorProps {
  columns: string[];
  selected: string;
  onChange: (column: string) => void;
}

export default function KeyColumnSelector({
  columns,
  selected,
  onChange,
}: KeyColumnSelectorProps) {
  return (
    <div className="animate-fade-in bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Key className="w-4 h-4 text-[#f58220]" />
        <h3 className="font-bold text-sm uppercase tracking-wider text-[#003366]">
          Key Column (Unique Identifier)
        </h3>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        Select the column that uniquely identifies each row. This is used to
        match rows between files.
      </p>
      <select
        value={selected}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm
                   bg-white focus:outline-none focus:ring-2 focus:ring-[#0066cc]
                   focus:border-transparent transition-all"
      >
        {columns.map((col) => (
          <option key={col} value={col}>
            {col}
          </option>
        ))}
      </select>
    </div>
  );
}
