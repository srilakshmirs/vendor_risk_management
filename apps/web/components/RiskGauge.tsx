"use client";

import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { useEffect, useMemo } from "react";

/**
 * Half-donut gauge using a pure SVG arc (recharts can't easily animate
 * start/end angle). Score 0–100, banded:
 *   0–39 green · 40–64 amber · 65–79 orange · 80+ red.
 * The arc sweeps in on mount and re-sweeps whenever `score` changes.
 */
export function RiskGauge({ score }: { score: number }) {
  const target = Math.max(0, Math.min(100, score));

  const colour =
    target >= 80
      ? "#dc2626"
      : target >= 65
        ? "#f97316"
        : target >= 40
          ? "#facc15"
          : "#10b981";

  const animated = useMotionValue(0);
  const displayed = useTransform(animated, (v) => Math.round(v));

  // Arc geometry — semicircle, stroke-dasharray trick
  const SIZE = 200;
  const STROKE = 20;
  const RADIUS = (SIZE - STROKE) / 2;
  const CIRCUMFERENCE = Math.PI * RADIUS; // half circle
  const dashOffset = useTransform(animated, (v) =>
    CIRCUMFERENCE * (1 - v / 100),
  );

  useEffect(() => {
    const controls = animate(animated, target, {
      duration: 1.0,
      ease: [0.22, 0.61, 0.36, 1],
    });
    return () => controls.stop();
  }, [target, animated]);

  // Memo the static SVG bits
  const arcPath = useMemo(() => {
    const cx = SIZE / 2;
    const cy = SIZE / 2;
    return `M ${cx - RADIUS},${cy} A ${RADIUS},${RADIUS} 0 0 1 ${cx + RADIUS},${cy}`;
  }, [RADIUS]);

  return (
    <div className="relative w-full flex justify-center" style={{ height: SIZE / 2 + 28 }}>
      <svg
        width={SIZE}
        height={SIZE / 2 + STROKE / 2}
        viewBox={`0 0 ${SIZE} ${SIZE / 2 + STROKE / 2}`}
        className="overflow-hidden"
        role="img"
        aria-label={`Risk score ${target} out of 100`}
      >
        {/* track */}
        <path
          d={arcPath}
          fill="none"
          stroke="currentColor"
          className="text-zinc-200 dark:text-zinc-800"
          strokeWidth={STROKE}
          strokeLinecap="round"
        />
        {/* animated fill */}
        <motion.path
          d={arcPath}
          fill="none"
          stroke={colour}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          style={{ strokeDashoffset: dashOffset, filter: `drop-shadow(0 0 6px ${colour}55)` }}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center pointer-events-none">
        <motion.span
          className="text-4xl font-bold tabular-nums leading-none"
          style={{ color: colour }}
        >
          {displayed}
        </motion.span>
        <span className="mt-1 text-[10px] text-zinc-500 dark:text-zinc-400 uppercase tracking-widest">
          Composite Risk
        </span>
      </div>
    </div>
  );
}
