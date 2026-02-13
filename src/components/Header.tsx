"use client";

import { GitCompareArrows } from "lucide-react";

export default function Header() {
  return (
    <header className="bg-[#003366] text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-white/10 p-2 rounded-lg">
            <GitCompareArrows className="w-7 h-7 text-[#f58220]" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">ComprisonTool</h1>
            <p className="text-xs text-blue-200 tracking-wide">
              ADVANCED FILE COMPARISON SYSTEM
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 text-xs text-blue-200">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            System Ready
          </div>
        </div>
      </div>
    </header>
  );
}
