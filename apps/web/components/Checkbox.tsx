"use client";

import { Check } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

/**
 * Visually-replaced checkbox — keeps a real <input> for a11y + form integration
 * but shows our own styled square so the dark-mode rendering is consistent
 * across OSes.
 */
export function Checkbox({
  checked,
  onChange,
  label,
  className,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: ReactNode;
  className?: string;
}) {
  return (
    <label
      className={cn(
        "group inline-flex items-center gap-2 cursor-pointer select-none",
        className,
      )}
    >
      <span className="relative inline-flex items-center justify-center">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="peer sr-only"
        />
        <span
          className={cn(
            "size-4 rounded border transition-colors flex items-center justify-center",
            "border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-900",
            "group-hover:border-zinc-400 dark:group-hover:border-zinc-500",
            "peer-focus-visible:ring-2 peer-focus-visible:ring-zinc-500/40",
            "peer-checked:bg-red-500 peer-checked:border-red-500 peer-checked:text-white",
          )}
        >
          {checked && <Check className="size-3" strokeWidth={3} />}
        </span>
      </span>
      <span className="text-sm text-zinc-700 dark:text-zinc-300">{label}</span>
    </label>
  );
}
