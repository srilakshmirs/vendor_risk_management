"use client";

import { motion } from "framer-motion";
import { Bell, Cpu, Loader2 } from "lucide-react";
import Link from "next/link";
import { useAlertCounts, useHealth, useLLMInfo } from "../lib/api/hooks";
import { cn } from "../lib/cn";

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { data: health } = useHealth();
  const { data: llm, isLoading: llmLoading } = useLLMInfo();
  const { data: counts } = useAlertCounts();

  const urgent = (counts?.open_critical ?? 0) + (counts?.open_high ?? 0);
  const tone =
    (counts?.open_critical ?? 0) > 0 ? "critical" : urgent > 0 ? "warn" : "calm";

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 px-8 py-5 border-b border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-950/60 backdrop-blur-xl">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</p>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs">
        {/* Alert badge — links to /alerts, pulses on CRITICAL */}
        <Link
          href="/alerts"
          aria-label={`${urgent} urgent alerts`}
          className={cn(
            "relative inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border bg-white dark:bg-zinc-900 transition-colors",
            tone === "critical"
              ? "border-red-300 dark:border-red-800 text-red-700 dark:text-red-300 hover:bg-red-50/60 dark:hover:bg-red-950/30"
              : tone === "warn"
                ? "border-amber-300 dark:border-amber-800 text-amber-700 dark:text-amber-300 hover:bg-amber-50/60 dark:hover:bg-amber-950/30"
                : "border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800",
          )}
        >
          <Bell className="size-3.5" />
          <span className="font-mono text-[11px]">
            {counts ? `${counts.open_critical} crit · ${counts.open_high} high` : "alerts"}
          </span>
          {tone === "critical" && (
            <motion.span
              className="absolute -top-1 -right-1 size-2.5 rounded-full bg-red-500"
              animate={{ scale: [1, 1.6, 1], opacity: [0.9, 0.4, 0.9] }}
              transition={{ duration: 1.4, repeat: Infinity }}
            />
          )}
        </Link>

        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <Cpu className="size-3.5 text-zinc-500" />
          {llmLoading ? (
            <Loader2 className="size-3 animate-spin text-zinc-400" />
          ) : (
            <span className="font-mono text-[11px]">
              LLM:{" "}
              <span className="font-semibold">{llm?.provider ?? "?"}</span>
              {llm?.model && (
                <span className="text-zinc-500"> · {llm.model}</span>
              )}
              <span
                className={
                  llm?.available
                    ? "ml-1.5 inline-block size-2 rounded-full bg-emerald-500"
                    : "ml-1.5 inline-block size-2 rounded-full bg-red-500"
                }
              />
            </span>
          )}
        </div>
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <span className="font-mono text-[11px]">
            API{" "}
            <span
              className={
                health
                  ? "ml-1 inline-block size-2 rounded-full bg-emerald-500"
                  : "ml-1 inline-block size-2 rounded-full bg-red-500"
              }
            />
          </span>
        </div>
      </div>
    </header>
  );
}
