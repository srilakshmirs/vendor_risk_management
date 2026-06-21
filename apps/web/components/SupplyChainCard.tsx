"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertOctagon,
  GitBranch,
  Loader2,
  Package,
  ShieldAlert,
  Upload,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useSWRConfig } from "swr";

import { api } from "../lib/api/client";
import { useVendorSboms } from "../lib/api/hooks";
import { cn } from "../lib/cn";
import { fmtDate } from "../lib/format";
import type { Sbom, SbomComponent, VulnSeverity } from "../lib/api/types";

const SEVERITY_ORDER: VulnSeverity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

const SEVERITY_STYLES: Record<string, { dot: string; text: string; bg: string }> = {
  CRITICAL: { dot: "bg-red-500", text: "text-red-700 dark:text-red-300", bg: "bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-900" },
  HIGH: { dot: "bg-orange-500", text: "text-orange-700 dark:text-orange-300", bg: "bg-orange-50 dark:bg-orange-950/40 border-orange-200 dark:border-orange-900" },
  MEDIUM: { dot: "bg-amber-400", text: "text-amber-700 dark:text-amber-300", bg: "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900" },
  LOW: { dot: "bg-sky-300", text: "text-sky-700 dark:text-sky-300", bg: "bg-sky-50 dark:bg-sky-950/40 border-sky-200 dark:border-sky-900" },
  NONE: { dot: "bg-emerald-400", text: "text-emerald-700 dark:text-emerald-300", bg: "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900" },
};

/**
 * Roll up CVE counts across every component in the most recent SBOM.
 * The scoring engine's operational_score is driven by CRITICAL + HIGH totals.
 */
function rollupCves(components: SbomComponent[]): Record<string, number> {
  const counts: Record<string, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  for (const c of components) {
    for (const v of c.vulnerabilities ?? []) {
      const sev = (v.severity || "").toUpperCase();
      if (sev in counts) counts[sev] = (counts[sev] ?? 0) + 1;
    }
  }
  return counts;
}

export function SupplyChainCard({ vendorCode }: { vendorCode: string }) {
  const { data: sboms, isLoading, error } = useVendorSboms(vendorCode);
  const { mutate } = useSWRConfig();
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  const latest: Sbom | null = sboms?.[0] ?? null;
  const cveCounts = useMemo(
    () => rollupCves(latest?.components ?? []),
    [latest],
  );
  const critical = cveCounts.CRITICAL ?? 0;
  const high = cveCounts.HIGH ?? 0;

  const topVulnerable = useMemo(() => {
    if (!latest) return [];
    return [...latest.components]
      .filter((c) => (c.vulnerabilities?.length ?? 0) > 0)
      .sort((a, b) => {
        const rank = (s: string | null) =>
          s === "CRITICAL" ? 4 : s === "HIGH" ? 3 : s === "MEDIUM" ? 2 : s === "LOW" ? 1 : 0;
        const aw = rank(a.highest_severity);
        const bw = rank(b.highest_severity);
        if (aw !== bw) return bw - aw;
        return (b.vulnerabilities?.length ?? 0) - (a.vulnerabilities?.length ?? 0);
      })
      .slice(0, 5);
  }, [latest]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadErr(null);
    try {
      await api.uploadSbom(vendorCode, file);
      // Refresh SBOM list + the vendor's risk score (it just got recomputed server-side)
      await Promise.all([
        mutate(["sboms", vendorCode]),
        mutate(["latest-risk", vendorCode]),
        mutate(["vendor", vendorCode]),
      ]);
    } catch (err) {
      setUploadErr(err instanceof Error ? err.message : String(err));
      console.error("SBOM upload failed", err);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const tone =
    critical > 0 ? "critical" : high > 0 ? "warn" : latest ? "good" : "neutral";

  return (
    <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <GitBranch className="size-5 text-violet-500" />
          <h2 className="text-lg font-semibold">Supply Chain (SBOM)</h2>
          {latest && (
            <span
              className={cn(
                "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border",
                tone === "critical" && "border-red-300 text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-950/30",
                tone === "warn" && "border-orange-300 text-orange-700 dark:text-orange-300 bg-orange-50 dark:bg-orange-950/30",
                tone === "good" && "border-emerald-300 text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/30",
              )}
            >
              {tone === "critical" ? "Action required" : tone === "warn" ? "Review" : "Clean"}
            </span>
          )}
        </div>
        <label
          className={cn(
            "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md cursor-pointer transition-colors",
            "border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900",
            "hover:bg-zinc-50 dark:hover:bg-zinc-800",
            uploading && "opacity-60 cursor-wait",
          )}
        >
          {uploading ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Upload className="size-3.5 text-violet-500" />
          )}
          {uploading ? "Scanning…" : "Upload SBOM"}
          <input
            type="file"
            accept=".json,application/json"
            onChange={handleUpload}
            disabled={uploading}
            className="sr-only"
          />
        </label>
      </div>

      {/* Loading state */}
      {isLoading && !sboms && (
        <div className="flex items-center gap-2 text-sm text-zinc-500 py-2">
          <Loader2 className="size-4 animate-spin" />
          Loading supply chain data…
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <p className="text-sm text-red-600 dark:text-red-400">
          Couldn't load SBOM data: {String((error as Error).message ?? error)}
        </p>
      )}

      {/* Empty state */}
      {!isLoading && !error && !latest && (
        <div className="text-center py-6">
          <Package className="size-8 text-zinc-300 dark:text-zinc-700 mx-auto mb-2" />
          <p className="text-sm text-zinc-600 dark:text-zinc-300">
            No Software Bill of Materials on record for this vendor.
          </p>
          <p className="text-xs text-zinc-500 mt-1">
            Upload a CycloneDX or SPDX JSON to scan for known CVEs.
          </p>
        </div>
      )}

      {/* Populated state */}
      {latest && (
        <>
          {/* CVE rollup */}
          <div className="grid grid-cols-4 gap-2 mb-5">
            {SEVERITY_ORDER.map((sev) => {
              const n = cveCounts[sev] ?? 0;
              const s = SEVERITY_STYLES[sev]!;
              return (
                <div
                  key={sev}
                  className={cn(
                    "rounded-lg border px-3 py-2.5",
                    s.bg,
                  )}
                >
                  <p className="text-[10px] font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                    {sev}
                  </p>
                  <p className={cn("text-2xl font-semibold tabular-nums leading-none mt-1", s.text)}>
                    {n}
                  </p>
                </div>
              );
            })}
          </div>

          {/* SBOM meta */}
          <div className="flex items-center justify-between mb-3 text-xs text-zinc-500 dark:text-zinc-400">
            <span className="font-mono">
              {latest.format}
              {latest.version && ` · v${latest.version}`}
              {" · "}
              {latest.components.length} component{latest.components.length === 1 ? "" : "s"}
            </span>
            <span>Scanned {fmtDate(latest.created_at)}</span>
          </div>

          {/* Top vulnerable components */}
          {topVulnerable.length > 0 ? (
            <>
              <div className="flex items-center gap-1.5 mb-2">
                <AlertOctagon className="size-3.5 text-zinc-400" />
                <p className="text-[11px] uppercase tracking-wider text-zinc-500 font-medium">
                  Most vulnerable components
                </p>
              </div>
              <ul className="space-y-1.5">
                <AnimatePresence initial={false}>
                  {topVulnerable.map((c, i) => {
                    const sev = c.highest_severity ?? "NONE";
                    const s = SEVERITY_STYLES[sev] ?? SEVERITY_STYLES.NONE!;
                    return (
                      <motion.li
                        key={`${c.name}-${c.version}`}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04, duration: 0.25 }}
                        className="flex items-center gap-2.5 text-sm py-1.5 px-2 rounded-md hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                      >
                        <span className={cn("inline-block size-2 rounded-full shrink-0", s.dot)} />
                        <span className="font-medium text-zinc-900 dark:text-zinc-100 truncate">
                          {c.name}
                        </span>
                        <span className="text-[11px] font-mono text-zinc-400">
                          {c.version}
                        </span>
                        <span className="ml-auto flex items-center gap-2">
                          <span className={cn("text-[10px] uppercase tracking-wider font-semibold", s.text)}>
                            {sev}
                          </span>
                          <span className="text-[11px] tabular-nums text-zinc-500">
                            {c.vulnerabilities.length} CVE{c.vulnerabilities.length === 1 ? "" : "s"}
                          </span>
                        </span>
                      </motion.li>
                    );
                  })}
                </AnimatePresence>
              </ul>
            </>
          ) : (
            <div className="flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-400 py-2">
              <ShieldAlert className="size-3.5" />
              No known vulnerabilities in any of the {latest.components.length} components.
            </div>
          )}

          {/* CRITICAL/HIGH risk-score impact callout */}
          {(critical > 0 || high > 0) && (
            <div className="mt-4 pt-4 border-t border-zinc-200 dark:border-zinc-800">
              <p className="text-[11px] text-zinc-500 leading-relaxed">
                <span className="font-semibold text-zinc-700 dark:text-zinc-200">
                  Risk impact:
                </span>{" "}
                {critical > 0 && `+40 to operational score (${critical} CRITICAL CVEs). `}
                {critical === 0 && high > 0 && `+25 to operational score (${high} HIGH CVEs). `}
                Recompute risk to refresh the composite score.
              </p>
            </div>
          )}

          {uploadErr && (
            <p className="mt-3 text-xs text-red-600 dark:text-red-400">
              Upload failed: {uploadErr}
            </p>
          )}
        </>
      )}
    </div>
  );
}
