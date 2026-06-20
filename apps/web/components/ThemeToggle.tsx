"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { cn } from "../lib/cn";

const ORDER = ["light", "dark", "system"] as const;
type Theme = (typeof ORDER)[number];

const LABEL: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

function Icon({ theme }: { theme: Theme }) {
  const Cmp = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return <Cmp className="size-3.5" />;
}

export function ThemeToggle() {
  const { theme = "system", setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Avoid hydration mismatch — render a fixed-size placeholder until client mounts
  if (!mounted) {
    return (
      <div
        aria-hidden
        className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 w-[88px] h-[26px]"
      />
    );
  }

  const current = (ORDER.includes(theme as Theme) ? theme : "system") as Theme;
  const idx = ORDER.indexOf(current);
  const next: Theme = ORDER[(idx + 1) % ORDER.length]!;

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`Theme: ${LABEL[current]} — click to switch to ${LABEL[next]}`}
      title={`Theme: ${LABEL[current]} — click for ${LABEL[next]}`}
      className={cn(
        "hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border bg-white dark:bg-zinc-900",
        "border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300",
        "hover:border-zinc-300 dark:hover:border-zinc-700 hover:text-zinc-900 dark:hover:text-zinc-100",
        "transition-colors font-mono text-[11px]",
      )}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={current}
          initial={{ opacity: 0, rotate: -90, scale: 0.6 }}
          animate={{ opacity: 1, rotate: 0, scale: 1 }}
          exit={{ opacity: 0, rotate: 90, scale: 0.6 }}
          transition={{ duration: 0.18 }}
          className="inline-flex"
        >
          <Icon theme={current} />
        </motion.span>
      </AnimatePresence>
      <span>{LABEL[current]}</span>
    </button>
  );
}
