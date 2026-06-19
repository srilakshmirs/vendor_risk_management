"use client";

import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { PageTransition } from "../../components/PageTransition";
import { SeverityBadge } from "../../components/SeverityBadge";
import { Topbar } from "../../components/Topbar";
import { useEval } from "../../lib/api/hooks";
import { cn } from "../../lib/cn";
import { fmtPct } from "../../lib/format";
import type { Severity } from "../../lib/api/types";

const SEVS: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"];

export default function EvalPage() {
  const { data: ev, isLoading } = useEval();

  if (isLoading && !ev) {
    return (
      <>
        <Topbar title="Model Evaluation" />
        <div className="flex-1 grid place-items-center">
          <Loader2 className="size-6 animate-spin text-zinc-400" />
        </div>
      </>
    );
  }

  if (!ev) return null;

  return (
    <>
      <Topbar
        title="Model Evaluation"
        subtitle={`${ev.model_version} · N=${ev.total} · live against ground truth`}
      />
      <PageTransition>
      <div className="px-8 py-6 space-y-6">
        {/* Headline */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Stat label="Anomaly accuracy" value={fmtPct(ev.anomaly_accuracy, 1)} good={ev.anomaly_accuracy >= 0.8} />
          <Stat label="Severity accuracy" value={fmtPct(ev.severity_accuracy, 1)} good={ev.severity_accuracy >= 0.8} />
          <Stat label="Binary F1" value={ev.binary_f1.toFixed(3)} good={ev.binary_f1 >= 0.85} />
          <Stat label="Vendor coverage" value={`${ev.total}`} good={true} />
        </div>

        {/* Rubric gates */}
        <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-1">Rubric gates</h2>
          <p className="text-sm text-zinc-500 mb-4">
            Each gate is a hard requirement from the hackathon brief.
          </p>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {Object.entries(ev.rubric_pass).map(([gate, ok]) => (
              <li
                key={gate}
                className={cn(
                  "flex items-center gap-2 px-3 py-2.5 rounded-md border text-sm",
                  ok
                    ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50/40 dark:bg-emerald-950/30"
                    : "border-red-300 dark:border-red-800 bg-red-50/40 dark:bg-red-950/30",
                )}
              >
                {ok ? (
                  <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                ) : (
                  <XCircle className="size-4 text-red-500 shrink-0" />
                )}
                <span className="font-mono text-[12px]">{gate}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Per-severity bars */}
        <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-1">Per-severity performance</h2>
          <p className="text-sm text-zinc-500 mb-4">
            Recall is judged more harshly than precision — missing a breached
            high-access vendor is the worst possible outcome.
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
                <th className="py-2 pr-3 font-medium">Severity</th>
                <th className="py-2 pr-3 font-medium text-right">Support</th>
                <th className="py-2 pr-3 font-medium">Recall</th>
                <th className="py-2 pr-3 font-medium">Precision</th>
              </tr>
            </thead>
            <tbody>
              {SEVS.map((sev) => {
                const recall = ev.recall_by_severity[sev] ?? 0;
                const precision = ev.precision_by_severity[sev] ?? 0;
                const support = ev.support_by_severity[sev] ?? 0;
                return (
                  <tr key={sev} className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-3 pr-3">
                      <SeverityBadge severity={sev} />
                    </td>
                    <td className="py-3 pr-3 text-right tabular-nums text-zinc-600 dark:text-zinc-300">
                      {support}
                    </td>
                    <td className="py-3 pr-3 w-1/3">
                      <MetricBar value={recall} />
                    </td>
                    <td className="py-3 pr-3 w-1/3">
                      <MetricBar value={precision} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Reproduce */}
        <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-zinc-50/70 dark:bg-zinc-950/40 backdrop-blur-md shadow-sm p-6 text-sm">
          <h3 className="font-semibold mb-2">Reproduce these numbers</h3>
          <pre className="text-[12px] font-mono text-zinc-700 dark:text-zinc-300 bg-white dark:bg-zinc-900 rounded-md p-3 border border-zinc-200 dark:border-zinc-800 overflow-x-auto">
{`make eval            # ASCII report
make eval-json       # JSON → docs/eval_report.json
pytest -k rubric     # CI gate (fails if any metric drops)`}
          </pre>
        </div>
      </div>
      </PageTransition>
    </>
  );
}

function Stat({
  label,
  value,
  good,
}: {
  label: string;
  value: React.ReactNode;
  good: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border p-5",
        good
          ? "border-emerald-300 dark:border-emerald-700 bg-emerald-50/30 dark:bg-emerald-950/20"
          : "border-red-300 dark:border-red-700 bg-red-50/30 dark:bg-red-950/20",
      )}
    >
      <p className="text-[11px] uppercase tracking-wider text-zinc-500">
        {label}
      </p>
      <p className="text-3xl font-bold tabular-nums mt-1">{value}</p>
    </div>
  );
}

function MetricBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value));
  const colour =
    pct >= 0.95
      ? "bg-emerald-500"
      : pct >= 0.8
        ? "bg-amber-400"
        : "bg-red-500";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full", colour)}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
      <span className="text-xs tabular-nums w-14 text-right text-zinc-600 dark:text-zinc-300">
        {fmtPct(pct, 1)}
      </span>
    </div>
  );
}
