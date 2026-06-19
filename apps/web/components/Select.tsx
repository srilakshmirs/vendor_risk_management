"use client";

import { ChevronDown } from "lucide-react";
import type { SelectHTMLAttributes } from "react";
import { cn } from "../lib/cn";

/**
 * Native <select> with appearance-none so we can render a proper dark-mode
 * surface + custom chevron. `color-scheme: dark` on the element makes the
 * popup menu itself pick the OS dark style (otherwise on macOS the options
 * render white-on-white in dark mode).
 */
export function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select
        {...props}
        className={cn(
          "appearance-none w-full pl-3 pr-9 py-2 text-sm rounded-md",
          "border border-zinc-300 dark:border-zinc-700/80",
          "bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100",
          "shadow-sm transition-colors",
          "hover:border-zinc-400 dark:hover:border-zinc-600",
          "focus:outline-none focus:ring-2 focus:ring-zinc-500/40 focus:border-zinc-400 dark:focus:border-zinc-500",
          "[color-scheme:light] dark:[color-scheme:dark]",
          className,
        )}
      >
        {children}
      </select>
      <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 size-4 text-zinc-400 pointer-events-none" />
    </div>
  );
}
