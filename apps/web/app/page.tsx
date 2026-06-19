"use client";

import Link from "next/link";
import {
  AlertOctagon,
  Building2,
  CheckCircle2,
  Loader2,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import useSWR from "swr";

import { AnimatedNumber } from "../components/AnimatedNumber";
import { KpiCard } from "../components/KpiCard";
import { PageTransition } from "../components/PageTransition";
import { RiskBar } from "../components/RiskBar";
import { SeverityBadge } from "../components/SeverityBadge";
import { SeverityDonut, SeverityLegend } from "../components/SeverityDonut";
import { Topbar } from "../components/Topbar";
import { api } from "../lib/api/client";
import { useEval } from "../lib/api/hooks";
import { fmtPct } from "../lib/format";
import type { Severity, Vendor } from "../lib/api/types";

const SEVS: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"];

function useSeverityCounts() {
  return useSWR("severity-counts", async () => {
    const ev = await api.eval();
    return ev.support_by_severity;
  });
}

function useTopRisky(limit = 10) {
  return useSWR(["top-risky", limit], () =>
    api.listVendors({
      sort: "preliminary_risk_score:desc",
      limit,
    }),
  );
}

export default function PortfolioPage() {
  const { data: ev } = useEval();
  const { data: counts } = useSeverityCounts();
  const { data: top } = useTopRisky();

  const criticalCount = counts?.CRITICAL ?? 0;
  const highCount = counts?.HIGH ?? 0;
  const totalAnomalies = ev ? Math.round(ev.binary_recall * ev.total) : 0;

  return (
    <>
      <Topbar
        title="Portfolio Overview"
        subtitle="Cross-vendor risk posture · refreshed continuously"
      />
      <PageTransition>
      <div className="px-8 py-6 space-y-6">
        {/* KPI strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            index={0}
            label="Total Vendors"
            value={ev ? <AnimatedNumber value={ev.total} /> : "—"}
            icon={<Building2 className="size-5" />}
            hint="100% coverage across the registry"
          />
          <KpiCard
            index={1}
            label="Critical Risk"
            value={<AnimatedNumber value={criticalCount} />}
            tone={criticalCount > 0 ? "bad" : "good"}
            icon={<AlertOctagon className="size-5" />}
            hint="Immediate action — breach + sensitive access"
          />
          <KpiCard
            index={2}
            label="High Risk"
            value={<AnimatedNumber value={highCount} />}
            tone={highCount > 0 ? "warn" : "good"}
            icon={<ShieldAlert className="size-5" />}
            hint="Remediate within 7 days"
          />
          <KpiCard
            index={3}
            label="Anomaly Accuracy"
            value={
              ev ? (
                <AnimatedNumber
                  value={ev.anomaly_accuracy * 100}
                  format={(n) => `${n.toFixed(0)}%`}
                />
              ) : (
                "—"
              )
            }
            tone={ev && ev.anomaly_accuracy >= 0.8 ? "good" : "warn"}
            icon={<CheckCircle2 className="size-5" />}
            hint={`${totalAnomalies} anomalies detected · F1 ${ev?.binary_f1.toFixed(3) ?? "—"}`}
          />
        </div>

        {/* Distribution + Rubric panel */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
            <div className="flex items-baseline justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold">Severity Distribution</h2>
                <p className="text-sm text-zinc-500">
                  Ranked risk register — tiered response model
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
              {counts ? (
                <>
                  <SeverityDonut counts={counts as Record<Severity, number>} />
                  <SeverityLegend counts={counts as Record<Severity, number>} />
                </>
              ) : (
                <div className="h-64 grid place-items-center md:col-span-2">
                  <Loader2 className="size-6 animate-spin text-zinc-400" />
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
            <h2 className="text-lg font-semibold mb-1">Rubric gates</h2>
            <p className="text-sm text-zinc-500 mb-4">
              Live vs ground-truth labels (N={ev?.total ?? "—"})
            </p>
            <ul className="space-y-2 text-sm">
              {ev ? (
                Object.entries(ev.rubric_pass).map(([gate, ok]) => (
                  <li
                    key={gate}
                    className="flex items-center gap-2 px-3 py-2 rounded-md border border-zinc-200 dark:border-zinc-800"
                  >
                    {ok ? (
                      <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                    ) : (
                      <XCircle className="size-4 text-red-500 shrink-0" />
                    )}
                    <span className="font-mono text-[11px]">{gate}</span>
                  </li>
                ))
              ) : (
                <Loader2 className="size-4 animate-spin text-zinc-400" />
              )}
            </ul>
            {ev && (
              <div className="mt-4 pt-4 border-t border-zinc-200 dark:border-zinc-800 text-xs space-y-1.5">
                {SEVS.map((sev) => (
                  <div
                    key={sev}
                    className="flex items-center justify-between gap-3"
                  >
                    <SeverityBadge severity={sev} />
                    <span className="font-mono text-zinc-500 tabular-nums">
                      recall {fmtPct(ev.recall_by_severity[sev] || 0, 1)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Top risky vendors */}
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold">Top 10 Risky Vendors</h2>
              <p className="text-sm text-zinc-500">
                By preliminary risk score (desc)
              </p>
            </div>
            <Link
              href="/vendors"
              className="text-sm text-zinc-700 dark:text-zinc-200 hover:underline"
            >
              View all →
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-500 border-b border-zinc-200 dark:border-zinc-800">
                  <th className="py-2 pr-3 font-medium">Vendor</th>
                  <th className="py-2 pr-3 font-medium">Type</th>
                  <th className="py-2 pr-3 font-medium">Country</th>
                  <th className="py-2 pr-3 font-medium">Tier</th>
                  <th className="py-2 pr-3 font-medium w-48">Risk</th>
                </tr>
              </thead>
              <tbody>
                {(top?.items as Vendor[] | undefined)?.map((v) => (
                  <tr
                    key={v.vendor_id}
                    className="border-b border-zinc-100 dark:border-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                  >
                    <td className="py-2.5 pr-3">
                      <Link
                        href={`/vendors/${v.vendor_id}`}
                        className="font-medium hover:underline"
                      >
                        {v.name}
                      </Link>
                      <span className="ml-2 text-[11px] font-mono text-zinc-400">
                        {v.vendor_id}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-zinc-600 dark:text-zinc-300">
                      {v.vendor_type}
                    </td>
                    <td className="py-2.5 pr-3 text-zinc-600 dark:text-zinc-300">
                      {v.country}
                    </td>
                    <td className="py-2.5 pr-3 text-zinc-600 dark:text-zinc-300">
                      {v.criticality}
                    </td>
                    <td className="py-2.5 pr-3">
                      <RiskBar score={v.preliminary_risk_score} />
                    </td>
                  </tr>
                ))}
                {!top && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-zinc-400">
                      <Loader2 className="size-5 animate-spin inline" />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      </PageTransition>
    </>
  );
}
