"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CertStats } from "../lib/api/types";

function CertTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  return (
    <div className="relative z-50 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-xl px-4 py-3 text-sm">
      <div className="font-semibold text-zinc-900 dark:text-zinc-100 mb-2 border-b border-zinc-200 dark:border-zinc-800 pb-1">
        {label}
      </div>
      <div className="space-y-1.5">
        {payload.map((entry: any) => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span
                className="inline-block size-2.5 rounded-sm"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-zinc-600 dark:text-zinc-300 capitalize text-xs">
                {entry.name.replace("_", " ")}
              </span>
            </div>
            <span className="tabular-nums font-medium text-zinc-900 dark:text-zinc-100 text-xs">
              {entry.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CertChart({ data }: { data: CertStats[] }) {
  if (!data || data.length === 0) {
    return <div className="text-sm text-zinc-500">No certification data available.</div>;
  }

  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(120,120,120,0.15)" />
          <XAxis
            dataKey="cert_type"
            tick={{ fontSize: 12, fill: "#a1a1aa" }}
            tickLine={false}
            axisLine={{ stroke: "rgba(120,120,120,0.15)" }}
            dy={10}
          />
          <YAxis
            tick={{ fontSize: 12, fill: "#a1a1aa" }}
            tickLine={false}
            axisLine={false}
            dx={-10}
          />
          <Tooltip content={<CertTooltip />} cursor={{ fill: "rgba(120,120,120,0.06)" }} />
          <Legend
            iconType="circle"
            wrapperStyle={{ fontSize: "12px", paddingTop: "10px", color: "#a1a1aa" }}
          />
          <Bar dataKey="certified" name="Certified" stackId="a" fill="#34d399" radius={[0, 0, 4, 4]} />
          <Bar dataKey="pending" name="Pending" stackId="a" fill="#60a5fa" />
          <Bar dataKey="expired" name="Expired" stackId="a" fill="#fbbf24" />
          <Bar dataKey="not_certified" name="Not Certified" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
