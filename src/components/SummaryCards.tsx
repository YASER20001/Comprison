"use client";

import { Plus, Minus, RefreshCw, Equal, BarChart3 } from "lucide-react";
import { ComparisonResult } from "@/lib/types";

interface SummaryCardsProps {
  result: ComparisonResult;
}

export default function SummaryCards({ result }: SummaryCardsProps) {
  const { summary } = result;

  const cards = [
    {
      label: "Total Records",
      value: summary.total,
      icon: BarChart3,
      bg: "bg-[#003366]",
      text: "text-white",
      iconColor: "text-blue-200",
    },
    {
      label: "Added",
      value: summary.added,
      icon: Plus,
      bg: "bg-green-50",
      text: "text-green-700",
      iconColor: "text-green-500",
      border: "border-green-200",
    },
    {
      label: "Deleted",
      value: summary.deleted,
      icon: Minus,
      bg: "bg-red-50",
      text: "text-red-700",
      iconColor: "text-red-500",
      border: "border-red-200",
    },
    {
      label: "Modified",
      value: summary.modified,
      icon: RefreshCw,
      bg: "bg-orange-50",
      text: "text-orange-700",
      iconColor: "text-orange-500",
      border: "border-orange-200",
    },
    {
      label: "Unchanged",
      value: summary.unchanged,
      icon: Equal,
      bg: "bg-gray-50",
      text: "text-gray-600",
      iconColor: "text-gray-400",
      border: "border-gray-200",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        const pct =
          summary.total > 0
            ? ((card.value / summary.total) * 100).toFixed(1)
            : "0";
        return (
          <div
            key={card.label}
            className={`
              ${card.bg} ${card.border ? `border ${card.border}` : ""}
              rounded-xl p-4 animate-fade-in
              ${idx === 0 ? "col-span-2 md:col-span-1" : ""}
            `}
            style={{ animationDelay: `${idx * 80}ms` }}
          >
            <div className="flex items-center justify-between mb-2">
              <Icon className={`w-5 h-5 ${card.iconColor}`} />
              {idx > 0 && (
                <span className={`text-xs ${card.text} opacity-70`}>
                  {pct}%
                </span>
              )}
            </div>
            <p className={`text-2xl font-bold ${card.text}`}>{card.value}</p>
            <p
              className={`text-xs mt-1 ${
                idx === 0 ? "text-blue-200" : card.text
              } opacity-80 uppercase tracking-wide`}
            >
              {card.label}
            </p>
          </div>
        );
      })}
    </div>
  );
}
