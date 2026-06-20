"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertOctagon,
  Bell,
  Check,
  Loader2,
  PlayCircle,
  RotateCcw,
  ShieldAlert,
  Siren,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useSWRConfig } from "swr";

import { PageTransition } from "../../components/PageTransition";
import { SeverityBadge } from "../../components/SeverityBadge";
import { Topbar } from "../../components/Topbar";
import { api } from "../../lib/api/client";
import { useAlertCounts, useAlerts } from "../../lib/api/hooks";
import { cn } from "../../lib/cn";
import { fmtDate } from "../../lib/format";
import type { AlertStatus, Severity } from "../../lib/api/types";

const SEVERITY_TABS: (Severity | "ALL")[] = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];
const STATUS_TABS: (AlertStatus | "all")[] = ["open", "ack", "resolved", "all"];

export default function AlertsPage() {
  const [sev, setSev] = useState<Severity | "ALL">("ALL");
  const [status, setStatus] = useState<AlertStatus | "all">("open");
  const [busy, setBusy] = useState<null | "sweep" | "breach">(null);
  const { mutate } = useSWRConfig();

  const params = useMemo(
    () => ({
      severity: sev === "ALL" ? undefined : sev,
      status: status === "all" ? undefined : status,
      sort: "created_at:desc",
      limit: 100,
    }),
    [sev, status],
  );

  const { data, isLoading } = useAlerts(params);
  const { data: counts } = useAlertCounts();

  const refreshAll = () => {
    mutate((k) => Array.isArray(k) && k[0] === "alerts");
    mutate("alert-counts");
  };

  const trigger = async (kind: "sweep" | "breach") => {
    setBusy(kind);
    try {
      if (kind === "sweep") await api.alertsSweep();
      else await api.breachPoll();
      refreshAll();
    } finally {
      setBusy(null);
    }
  };

  const ack = async (id: number) => {
    await api.updateAlert(id, "ack");
    refreshAll();
  };

  const resolve = async (id: number) => {
    await api.updateAlert(id, "resolved");
    refreshAll();
  };

  return (
    <>
      <Topbar
        title="Alerts & Continuous Monitoring"
        subtitle="60 / 30 / 7 day expiry warnings · breach-feed ingestion · APScheduler-driven"
      />
      <PageTransition>
        <div className="px-8 py-6 space-y-6">
          {/* KPI strip — clickable shortcuts into filtered views */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <CountTile
              label="Open Critical"
              value={counts?.open_critical ?? 0}
              tone="bad"
              icon={<Siren className="size-5" />}
              onClick={() => {
                setSev("CRITICAL");
                setStatus("open");
              }}
            />
            <CountTile
              label="Open High"
              value={counts?.open_high ?? 0}
              tone="warn"
              icon={<ShieldAlert className="size-5" />}
              onClick={() => {
                setSev("HIGH");
                setStatus("open");
              }}
            />
            <CountTile
              label="Open (all)"
              value={counts?.open ?? 0}
              tone="neutral"
              icon={<Bell className="size-5" />}
              onClick={() => {
                setSev("ALL");
                setStatus("open");
              }}
            />
            <CountTile
              label="Resolved"
              value={counts?.resolved ?? 0}
              tone="good"
              icon={<Check className="size-5" />}
              onClick={() => {
                setSev("ALL");
                setStatus("resolved");
              }}
            />
          </div>

          {/* Toolbar */}
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md p-3 flex flex-wrap items-center gap-2 shadow-sm">
            <div className="flex items-center gap-1 mr-2">
              <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500 mr-2">
                Severity
              </span>
              {SEVERITY_TABS.map((s) => (
                <Pill key={s} active={sev === s} onClick={() => setSev(s)}>
                  {s}
                </Pill>
              ))}
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500 mr-2">
                Status
              </span>
              {STATUS_TABS.map((s) => (
                <Pill key={s} active={status === s} onClick={() => setStatus(s)}>
                  {s}
                </Pill>
              ))}
            </div>

            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={refreshAll}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800"
              >
                <RotateCcw className="size-3.5" />
                Refresh
              </button>
              <button
                onClick={() => trigger("sweep")}
                disabled={busy !== null}
                className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800",
                  busy === "sweep" && "opacity-60 cursor-wait",
                )}
              >
                {busy === "sweep" ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <PlayCircle className="size-3.5" />
                )}
                Run expiry sweep
              </button>
              <button
                onClick={() => trigger("breach")}
                disabled={busy !== null}
                className={cn(
                  "inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md text-white shadow-sm shadow-red-500/20",
                  "bg-linear-to-br from-red-500 to-amber-500 hover:opacity-95 disabled:opacity-60 disabled:cursor-wait",
                )}
              >
                {busy === "breach" ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Sparkles className="size-3.5" />
                )}
                Poll breach feed
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50/80 dark:bg-zinc-950/40 border-b border-zinc-200 dark:border-zinc-800">
                  <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
                    <th className="py-3 px-3 font-medium w-28">Severity</th>
                    <th className="py-3 px-3 font-medium">Vendor</th>
                    <th className="py-3 px-3 font-medium">Type</th>
                    <th className="py-3 px-3 font-medium">Message</th>
                    <th className="py-3 px-3 font-medium">Due</th>
                    <th className="py-3 px-3 font-medium">Status</th>
                    <th className="py-3 px-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading && !data ? (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-zinc-400">
                        <Loader2 className="size-5 animate-spin inline" />
                      </td>
                    </tr>
                  ) : data?.items.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-zinc-500">
                        No alerts match these filters.
                      </td>
                    </tr>
                  ) : (
                    <AnimatePresence initial={false}>
                      {data?.items.map((a, i) => (
                        <motion.tr
                          key={a.id}
                          layout
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, x: -8 }}
                          transition={{ delay: Math.min(i * 0.01, 0.2), duration: 0.2 }}
                          className="border-b border-zinc-100 dark:border-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                        >
                          <td className="py-2.5 px-3 align-top">
                            <SeverityBadge severity={a.severity} />
                          </td>
                          <td className="py-2.5 px-3 align-top">
                            <Link
                              href={`/vendors/${a.vendor_code}`}
                              className="font-medium hover:underline"
                            >
                              {a.vendor_name}
                            </Link>
                            <div className="text-[11px] font-mono text-zinc-400">
                              {a.vendor_code}
                            </div>
                          </td>
                          <td className="py-2.5 px-3 align-top">
                            <span className="font-mono text-[11px] text-zinc-600 dark:text-zinc-300">
                              {a.alert_type}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 align-top">
                            <p className="text-zinc-700 dark:text-zinc-200 leading-snug line-clamp-2">
                              {a.message}
                            </p>
                          </td>
                          <td className="py-2.5 px-3 align-top tabular-nums text-zinc-500">
                            {fmtDate(a.due_date)}
                          </td>
                          <td className="py-2.5 px-3 align-top">
                            <StatusPill status={a.status} />
                          </td>
                          <td className="py-2.5 px-3 align-top">
                            <div className="flex items-center justify-end gap-1.5">
                              {a.status === "open" && (
                                <button
                                  onClick={() => ack(a.id)}
                                  className="text-[11px] px-2 py-1 rounded-md border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800"
                                >
                                  Ack
                                </button>
                              )}
                              {a.status !== "resolved" && (
                                <button
                                  onClick={() => resolve(a.id)}
                                  className="text-[11px] px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/20"
                                >
                                  Resolve
                                </button>
                              )}
                            </div>
                          </td>
                        </motion.tr>
                      ))}
                    </AnimatePresence>
                  )}
                </tbody>
              </table>
            </div>
            {data && (
              <div className="px-4 py-2.5 border-t border-zinc-200 dark:border-zinc-800/80 text-xs text-zinc-500">
                Showing {data.items.length} of {data.total}
              </div>
            )}
          </div>
        </div>
      </PageTransition>
    </>
  );
}

// ── Sub-components ────────────────────────────────────────────────────
function CountTile({
  label,
  value,
  tone,
  icon,
  onClick,
}: {
  label: string;
  value: number;
  tone: "neutral" | "good" | "warn" | "bad";
  icon: React.ReactNode;
  onClick?: () => void;
}) {
  const tones = {
    neutral: "border-zinc-200 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60",
    good: "border-emerald-300/70 dark:border-emerald-800/70 bg-gradient-to-br from-emerald-50/60 to-white/30 dark:from-emerald-950/30 dark:to-zinc-900/40",
    warn: "border-amber-300/70 dark:border-amber-800/70 bg-gradient-to-br from-amber-50/60 to-white/30 dark:from-amber-950/30 dark:to-zinc-900/40",
    bad: "border-red-300/70 dark:border-red-800/70 bg-gradient-to-br from-red-50/60 to-white/30 dark:from-red-950/30 dark:to-zinc-900/40",
  }[tone];
  const iconTone = {
    neutral: "text-zinc-400 dark:text-zinc-500",
    good: "text-emerald-500",
    warn: "text-amber-500",
    bad: "text-red-500",
  }[tone];
  return (
    <button
      onClick={onClick}
      className={cn(
        "group text-left rounded-xl border backdrop-blur-md p-5 shadow-sm",
        "transition-shadow hover:shadow-md hover:shadow-zinc-900/[0.04] dark:hover:shadow-black/40",
        tones,
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-500 dark:text-zinc-400">
            {label}
          </p>
          <p className="text-3xl font-semibold tabular-nums">{value}</p>
        </div>
        <div
          className={cn(
            "size-9 rounded-lg grid place-items-center bg-zinc-50 dark:bg-zinc-800/60 group-hover:bg-zinc-100 dark:group-hover:bg-zinc-800",
            iconTone,
          )}
        >
          {icon}
        </div>
      </div>
    </button>
  );
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2.5 py-1 text-xs rounded-md font-medium transition-colors",
        active
          ? "bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
          : "text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800",
      )}
    >
      {children}
    </button>
  );
}

function StatusPill({ status }: { status: AlertStatus }) {
  const style = {
    open: "bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/30",
    ack: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30",
    resolved: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  }[status];
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider font-semibold rounded border",
        style,
      )}
    >
      {status}
    </span>
  );
}
