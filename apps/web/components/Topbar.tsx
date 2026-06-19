"use client";

import { Cpu, Loader2 } from "lucide-react";
import { useHealth, useLLMInfo } from "../lib/api/hooks";

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { data: health } = useHealth();
  const { data: llm, isLoading: llmLoading } = useLLMInfo();

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 px-8 py-5 border-b border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-950/60 backdrop-blur-xl">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</p>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs">
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <Cpu className="size-3.5 text-zinc-500" />
          {llmLoading ? (
            <Loader2 className="size-3 animate-spin text-zinc-400" />
          ) : (
            <span className="font-mono text-[11px]">
              LLM:{" "}
              <span className="font-semibold">{llm?.provider ?? "?"}</span>
              {llm?.model && (
                <span className="text-zinc-500"> · {llm.model}</span>
              )}
              <span
                className={
                  llm?.available
                    ? "ml-1.5 inline-block size-2 rounded-full bg-emerald-500"
                    : "ml-1.5 inline-block size-2 rounded-full bg-red-500"
                }
              />
            </span>
          )}
        </div>
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <span className="font-mono text-[11px]">
            API{" "}
            <span
              className={
                health
                  ? "ml-1 inline-block size-2 rounded-full bg-emerald-500"
                  : "ml-1 inline-block size-2 rounded-full bg-red-500"
              }
            />
          </span>
        </div>
      </div>
    </header>
  );
}
