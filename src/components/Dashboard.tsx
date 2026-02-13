"use client";

import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { ComparisonResult } from "@/lib/types";

interface DashboardProps {
  result: ComparisonResult;
}

const CHART_COLORS = {
  added: "#28a745",
  deleted: "#dc3545",
  modified: "#f58220",
  unchanged: "#9ca3af",
};

export default function Dashboard({ result }: DashboardProps) {
  const { summary } = result;

  const pieData = [
    { name: "Added", value: summary.added, color: CHART_COLORS.added },
    { name: "Deleted", value: summary.deleted, color: CHART_COLORS.deleted },
    { name: "Modified", value: summary.modified, color: CHART_COLORS.modified },
    {
      name: "Unchanged",
      value: summary.unchanged,
      color: CHART_COLORS.unchanged,
    },
  ].filter((d) => d.value > 0);

  const barData = [
    { name: "Added", count: summary.added, fill: CHART_COLORS.added },
    { name: "Deleted", count: summary.deleted, fill: CHART_COLORS.deleted },
    { name: "Modified", count: summary.modified, fill: CHART_COLORS.modified },
    { name: "Unchanged", count: summary.unchanged, fill: CHART_COLORS.unchanged },
  ];

  // Column-level change frequency
  const columnChangeFreq: Record<string, number> = {};
  for (const row of result.rows) {
    for (const change of row.changes) {
      columnChangeFreq[change.column] =
        (columnChangeFreq[change.column] || 0) + 1;
    }
  }

  const columnData = Object.entries(columnChangeFreq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([col, count]) => ({ column: col, changes: count }));

  const changeRate =
    summary.total > 0
      ? (
          ((summary.added + summary.deleted + summary.modified) /
            summary.total) *
          100
        ).toFixed(1)
      : "0";

  const stabilityRate =
    summary.total > 0
      ? ((summary.unchanged / summary.total) * 100).toFixed(1)
      : "0";

  return (
    <div className="animate-fade-in space-y-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Change Rate"
          value={`${changeRate}%`}
          sub="Records with changes"
          color="#f58220"
        />
        <MetricCard
          label="Stability Rate"
          value={`${stabilityRate}%`}
          sub="Records unchanged"
          color="#003366"
        />
        <MetricCard
          label="Columns Affected"
          value={Object.keys(columnChangeFreq).length.toString()}
          sub={`of ${result.columns.length} total`}
          color="#0066cc"
        />
        <MetricCard
          label="Total Changes"
          value={(
            summary.added +
            summary.deleted +
            summary.modified
          ).toString()}
          sub="Across all records"
          color="#dc3545"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pie Chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h3 className="font-bold text-sm text-[#003366] uppercase tracking-wider mb-4">
            Change Distribution
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={65}
                outerRadius={100}
                paddingAngle={3}
                dataKey="value"
                label={(props) =>
                  `${props.name ?? ""} ${(Number(props.percent ?? 0) * 100).toFixed(0)}%`
                }
              >
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Bar Chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h3 className="font-bold text-sm text-[#003366] uppercase tracking-wider mb-4">
            Change Breakdown
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} barSize={40}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {barData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Column Change Frequency */}
      {columnData.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h3 className="font-bold text-sm text-[#003366] uppercase tracking-wider mb-4">
            Most Changed Columns
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(200, columnData.length * 35)}>
            <BarChart data={columnData} layout="vertical" barSize={20}>
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="column"
                tick={{ fontSize: 11 }}
                width={150}
              />
              <Tooltip />
              <Legend />
              <Bar
                dataKey="changes"
                fill="#f58220"
                radius={[0, 6, 6, 0]}
                name="Changes"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <div
        className="w-8 h-1 rounded-full mb-3"
        style={{ backgroundColor: color }}
      />
      <p className="text-2xl font-bold" style={{ color }}>
        {value}
      </p>
      <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mt-1">
        {label}
      </p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  );
}
