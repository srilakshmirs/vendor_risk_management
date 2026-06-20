"use client";

import { motion } from "framer-motion";
import { FileDown, FileSearch, Loader2, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageTransition } from "../../components/PageTransition";
import { SeverityBadge } from "../../components/SeverityBadge";
import { Topbar } from "../../components/Topbar";
import { api } from "../../lib/api/client";
import { useVendors } from "../../lib/api/hooks";
import { cn } from "../../lib/cn";

export default function AuditPackPage() {
  const [q, setQ] = useState("");
  const params = useMemo(
    () => ({
      q: q || undefined,
      sort: "preliminary_risk_score:desc",
      limit: 25,
    }),
    [q],
  );
  const { data, isLoading } = useVendors(params);

  return (
    <>
      <Topbar
        title="Audit Pack"
        subtitle="One-click PDF export · all risk signals · ready for auditor review"
      />
      <PageTransition>
        <div className="px-8 py-6 space-y-6">
          {/* Hero explainer */}
          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md p-6 shadow-sm">
            <div className="flex items-start gap-4">
              <div className="size-12 rounded-xl bg-linear-to-br from-red-500 to-amber-500 grid place-items-center text-white shadow-md shadow-red-500/20 shrink-0">
                <FileSearch className="size-6" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold tracking-tight">
                  Generate a vendor audit pack
                </h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 leading-relaxed">
                  Each pack is a single PDF covering risk score + 5-component breakdown +
                  narrative + triggered rules + certifications + contract + 12-month breach
                  history + open alerts. Maps to the rubric's{" "}
                  <code className="text-[11px] px-1 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800">
                    &lt;15 min audit report
                  </code>{" "}
                  metric.
                </p>
              </div>
            </div>
          </div>

          {/* Search */}
          <div className="relative max-w-xl">
            <Search className="size-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Find a vendor to export…"
              className="w-full pl-9 pr-3 py-2.5 text-sm rounded-lg border border-zinc-300 dark:border-zinc-700/80 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 shadow-sm focus:outline-none focus:ring-2 focus:ring-red-500/40"
            />
          </div>

          {/* Vendor list */}
          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50/80 dark:bg-zinc-950/40 border-b border-zinc-200 dark:border-zinc-800">
                <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="py-3 px-3 font-medium">Vendor</th>
                  <th className="py-3 px-3 font-medium">Type</th>
                  <th className="py-3 px-3 font-medium">Tier</th>
                  <th className="py-3 px-3 font-medium">Prelim risk</th>
                  <th className="py-3 px-3 font-medium text-right">Export</th>
                </tr>
              </thead>
              <tbody>
                {isLoading && !data ? (
                  <tr>
                    <td colSpan={5} className="py-10 text-center text-zinc-400">
                      <Loader2 className="size-5 animate-spin inline" />
                    </td>
                  </tr>
                ) : data?.items.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-10 text-center text-zinc-500">
                      No vendors match.
                    </td>
                  </tr>
                ) : (
                  data?.items.map((v, i) => (
                    <motion.tr
                      key={v.vendor_id}
                      initial={{ opacity: 0, y: 3 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: Math.min(i * 0.015, 0.2), duration: 0.2 }}
                      className="border-b border-zinc-100 dark:border-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                    >
                      <td className="py-2.5 px-3">
                        <Link
                          href={`/vendors/${v.vendor_id}`}
                          className="font-medium hover:underline"
                        >
                          {v.name}
                        </Link>
                        <div className="text-[11px] font-mono text-zinc-400">
                          {v.vendor_id}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-zinc-600 dark:text-zinc-300">
                        {v.vendor_type}
                      </td>
                      <td className="py-2.5 px-3 text-zinc-600 dark:text-zinc-300">
                        {v.criticality}
                      </td>
                      <td className="py-2.5 px-3 tabular-nums text-zinc-700 dark:text-zinc-200">
                        {v.preliminary_risk_score}/100
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <a
                          href={api.auditPackUrl(v.vendor_id)}
                          download
                          className={cn(
                            "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md text-white shadow-sm shadow-red-500/20",
                            "bg-linear-to-br from-red-500 to-amber-500 hover:opacity-95",
                          )}
                        >
                          <FileDown className="size-3.5" />
                          PDF
                        </a>
                      </td>
                    </motion.tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </PageTransition>
    </>
  );
}
