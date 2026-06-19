import { cn } from "../lib/cn";

const WEIGHTS: Record<string, number> = {
  breach: 0.3,
  data_access: 0.25,
  compliance: 0.2,
  financial: 0.15,
  operational: 0.1,
};

const LABELS: Record<string, string> = {
  breach: "Breach history",
  data_access: "Data access",
  compliance: "Compliance",
  financial: "Financial health",
  operational: "Operational",
};

export function ComponentBreakdown({
  components,
}: {
  components: Record<string, number>;
}) {
  const rows = Object.entries(WEIGHTS).map(([key, weight]) => {
    const raw = components[key] ?? 0;
    const weighted = Math.round(raw * weight * 10) / 10;
    return { key, raw, weighted, weight };
  });

  return (
    <ul className="space-y-3">
      {rows.map(({ key, raw, weighted, weight }) => {
        const colour =
          raw >= 80
            ? "bg-red-500"
            : raw >= 65
              ? "bg-orange-500"
              : raw >= 40
                ? "bg-amber-400"
                : "bg-emerald-500";
        return (
          <li key={key}>
            <div className="flex items-baseline justify-between text-xs mb-1">
              <span className="text-zinc-700 dark:text-zinc-200 font-medium">
                {LABELS[key]}
              </span>
              <span className="text-zinc-500 tabular-nums">
                {raw}/100
                <span className="ml-2 text-zinc-400">
                  · {(weight * 100).toFixed(0)}% wt · contribute {weighted}
                </span>
              </span>
            </div>
            <div className="h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={cn("h-full rounded-full", colour)}
                style={{ width: `${raw}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
