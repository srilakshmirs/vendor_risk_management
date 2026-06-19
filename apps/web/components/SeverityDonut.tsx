"use client";

import { motion } from "framer-motion";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { Severity } from "../lib/api/types";

const COLORS: Record<Severity, string> = {
  CRITICAL: "#dc2626",
  HIGH: "#f97316",
  MEDIUM: "#facc15",
  LOW: "#7dd3fc",
  NONE: "#86efac",
};

const ORDER: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"];

/** Self-contained tooltip — full control over colours, immune to recharts defaults. */
function DonutTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number; payload?: { color?: string } }>;
  total: number;
}) {
  if (!active || !payload?.length) return null;
  const entry = payload[0]!;
  const value = Number(entry.value ?? 0);
  const colour = entry.payload?.color ?? "#a1a1aa";
  const pct = total > 0 ? ((value / total) * 100).toFixed(1) : "0.0";
  return (
    <div className="relative z-50 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-xl px-3 py-2 text-xs">
      <div className="flex items-center gap-2">
        <span
          className="inline-block size-2.5 rounded-sm"
          style={{ backgroundColor: colour }}
        />
        <span className="font-semibold text-zinc-900 dark:text-zinc-100">
          {String(entry.name)}
        </span>
      </div>
      <div className="mt-1 text-zinc-600 dark:text-zinc-300 tabular-nums">
        {value} vendor{value === 1 ? "" : "s"}{" "}
        <span className="text-zinc-400">· {pct}%</span>
      </div>
    </div>
  );
}

export function SeverityDonut({
  counts,
}: {
  counts: Record<Severity, number>;
}) {
  const data = ORDER.map((sev) => ({
    name: sev,
    value: counts[sev] || 0,
    color: COLORS[sev],
  })).filter((d) => d.value > 0);

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="relative h-64 w-full">
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={data}
            innerRadius={62}
            outerRadius={92}
            paddingAngle={2}
            dataKey="value"
            stroke="none"
            animationDuration={900}
            animationBegin={120}
          >
            {data.map((d) => (
              <Cell key={d.name} fill={d.color} />
            ))}
          </Pie>
          <Tooltip
            content={<DonutTooltip total={total} />}
            cursor={{ fill: "rgba(120,120,120,0.06)" }}
            offset={20}
            wrapperStyle={{ zIndex: 50 }}
          />
        </PieChart>
      </ResponsiveContainer>
      <motion.div
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.4, duration: 0.45, ease: "easeOut" }}
        className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
      >
        <p className="text-3xl font-bold tabular-nums">{total}</p>
        <p className="text-[11px] text-zinc-500 dark:text-zinc-400 uppercase tracking-widest">
          Vendors
        </p>
      </motion.div>
    </div>
  );
}

export function SeverityLegend({
  counts,
}: {
  counts: Record<Severity, number>;
}) {
  const total = ORDER.reduce((s, sev) => s + (counts[sev] || 0), 0);
  return (
    <ul className="grid grid-cols-2 gap-y-2.5 gap-x-4 text-sm">
      {ORDER.map((sev, i) => {
        const v = counts[sev] || 0;
        const pct = total > 0 ? ((v / total) * 100).toFixed(0) : "0";
        return (
          <motion.li
            key={sev}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 + i * 0.05, duration: 0.3 }}
            className="flex items-center gap-2"
          >
            <span
              className="inline-block size-2.5 rounded-sm shrink-0"
              style={{ backgroundColor: COLORS[sev] }}
            />
            <span className="text-zinc-600 dark:text-zinc-300">{sev}</span>
            <span className="ml-auto flex items-baseline gap-1.5">
              <span className="tabular-nums font-medium text-zinc-900 dark:text-zinc-100">
                {v}
              </span>
              <span className="text-[10px] tabular-nums text-zinc-400">{pct}%</span>
            </span>
          </motion.li>
        );
      })}
    </ul>
  );
}
