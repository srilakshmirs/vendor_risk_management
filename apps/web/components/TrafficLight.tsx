import { cn } from "../lib/cn";
import type { TrafficLight as TrafficLightType } from "../lib/api/types";

const DOT: Record<TrafficLightType, string> = {
  Red: "bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.7)]",
  Yellow: "bg-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.6)]",
  Green: "bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.6)]",
};

export function TrafficLight({
  light,
  className,
}: {
  light: TrafficLightType;
  className?: string;
}) {
  return (
    <span
      aria-label={`Traffic light: ${light}`}
      className={cn("inline-block size-3 rounded-full", DOT[light], className)}
    />
  );
}
