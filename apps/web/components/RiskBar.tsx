import { cn } from "../lib/cn";

/** Horizontal 0-100 bar coloured by score band. */
export function RiskBar({
  score,
  className,
  showValue = true,
}: {
  score: number;
  className?: string;
  showValue?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, score));
  const colour =
    pct >= 80
      ? "bg-red-500"
      : pct >= 65
        ? "bg-orange-500"
        : pct >= 40
          ? "bg-amber-400"
          : "bg-emerald-500";

  return (
    <div className={cn("flex items-center gap-3 min-w-[140px]", className)}>
      <div className="flex-1 h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", colour)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showValue && (
        <span className="text-xs tabular-nums text-zinc-600 dark:text-zinc-300 w-8 text-right">
          {pct}
        </span>
      )}
    </div>
  );
}
