"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

export function KpiCard({
  label,
  value,
  hint,
  icon,
  tone = "neutral",
  className,
  index = 0,
  href,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
  className?: string;
  /** Used to stagger entrance animation when rendered in a grid */
  index?: number;
  /** If provided, the card becomes a clickable link */
  href?: string;
}) {
  const toneStyles = {
    neutral:
      "border-zinc-200 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60",
    good: "border-emerald-300/80 dark:border-emerald-800/70 bg-linear-to-br from-emerald-50/60 to-white/30 dark:from-emerald-950/30 dark:to-zinc-900/40",
    warn: "border-amber-300/80 dark:border-amber-800/70 bg-linear-to-br from-amber-50/60 to-white/30 dark:from-amber-950/30 dark:to-zinc-900/40",
    bad: "border-red-300/80 dark:border-red-800/70 bg-linear-to-br from-red-50/60 to-white/30 dark:from-red-950/30 dark:to-zinc-900/40",
  }[tone];

  const iconTone = {
    neutral: "text-zinc-400 dark:text-zinc-500",
    good: "text-emerald-500",
    warn: "text-amber-500",
    bad: "text-red-500",
  }[tone];

  const card = (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4, ease: [0.22, 0.61, 0.36, 1] }}
      whileHover={{ y: -2 }}
      className={cn(
        "group rounded-xl border backdrop-blur-md p-5 shadow-sm h-full flex flex-col",
        "transition-shadow hover:shadow-md hover:shadow-zinc-900/4 dark:hover:shadow-black/40",
        href && "cursor-pointer",
        toneStyles,
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-500 dark:text-zinc-400">
            {label}
          </p>
          <p className="text-3xl font-semibold tracking-tight tabular-nums">
            {value}
          </p>
        </div>
        {icon && (
          <div
            className={cn(
              "size-9 rounded-lg grid place-items-center transition-colors shrink-0",
              "bg-zinc-50 dark:bg-zinc-800/60 group-hover:bg-zinc-100 dark:group-hover:bg-zinc-800",
              iconTone,
            )}
          >
            {icon}
          </div>
        )}
      </div>
      <div className="flex-grow" />
      {hint && (
        <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">{hint}</p>
      )}
    </motion.div>
  );

  if (href) {
    return <Link href={href} className="block h-full no-underline">{card}</Link>;
  }
  return card;
}

