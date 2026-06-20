import { cn } from "../lib/cn";

/**
 * Generic loading placeholder. Uses the shimmer keyframe defined in
 * globals.css (`.vrm-skeleton-shimmer`) rather than `animate-pulse` —
 * the shimmer reads as more polished and signals "data is moving" vs
 * "this thing is broken".
 */
export function Skeleton({
  className,
  rounded = "rounded-md",
}: {
  className?: string;
  rounded?: string;
}) {
  return <div className={cn("vrm-skeleton-shimmer", rounded, className)} />;
}

/** Vertical stack of skeleton lines — for paragraphs / narrative cards. */
export function SkeletonLines({
  count = 3,
  className,
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2.5", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn("h-3", i === count - 1 ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  );
}

/** Reusable card shell so loading + loaded states share the same chrome. */
export function SkeletonCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6",
        className,
      )}
    >
      {children}
    </div>
  );
}
