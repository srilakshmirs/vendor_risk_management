import { cn } from "../lib/cn";
import type { Severity } from "../lib/api/types";

const STYLES: Record<Severity, string> = {
  CRITICAL: "bg-red-600 text-white border-red-700",
  HIGH: "bg-orange-500 text-white border-orange-600",
  MEDIUM: "bg-amber-400 text-amber-950 border-amber-500",
  LOW: "bg-sky-200 text-sky-900 border-sky-300",
  NONE: "bg-emerald-100 text-emerald-900 border-emerald-300",
};

export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-md border tracking-wide uppercase",
        STYLES[severity],
        className,
      )}
    >
      {severity}
    </span>
  );
}
