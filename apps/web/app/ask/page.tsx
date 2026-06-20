"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUp,
  Bot,
  Database,
  Loader2,
  Sparkles,
  Square,
  User,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { PageTransition } from "../../components/PageTransition";
import { Topbar } from "../../components/Topbar";
import { API_BASE } from "../../lib/api/client";
import { cn } from "../../lib/cn";
import type { AskCitation } from "../../lib/api/types";

const EXAMPLES = [
  "Which vendors have CRITICAL risk and handle PII?",
  "Show me vendors with expired SOC 2 certifications and sensitive data access.",
  "Which payment processors are under active investigation?",
  "What is our biggest GDPR exposure right now?",
];

type Turn = {
  id: string;
  question: string;
  answer: string;            // accumulates as tokens arrive
  citations: AskCitation[];
  status: "streaming" | "done" | "error";
  error?: string;
};

export default function AskPage() {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new tokens
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  const cancel = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
    setTurns((prev) => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      if (last && last.status === "streaming") {
        return [...prev.slice(0, -1), { ...last, status: "done" }];
      }
      return prev;
    });
  };

  const ask = async (question: string) => {
    if (!question.trim() || streaming) return;

    const id = crypto.randomUUID();
    const turn: Turn = {
      id,
      question,
      answer: "",
      citations: [],
      status: "streaming",
    };
    setTurns((t) => [...t, turn]);
    setInput("");
    setStreaming(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res = await fetch(`${API_BASE}/ask/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, k: 8 }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(
          (await res.text().catch(() => res.statusText)) || `HTTP ${res.status}`,
        );
      }
      await consumeSSE(res.body, (event, data) => {
        if (event === "citations") {
          const parsed = JSON.parse(data) as { chunks: AskCitation[] };
          setTurns((all) =>
            all.map((t) =>
              t.id === id ? { ...t, citations: parsed.chunks } : t,
            ),
          );
        } else if (event === "token") {
          setTurns((all) =>
            all.map((t) =>
              t.id === id ? { ...t, answer: t.answer + data } : t,
            ),
          );
        } else if (event === "done") {
          setTurns((all) =>
            all.map((t) => (t.id === id ? { ...t, status: "done" } : t)),
          );
        } else if (event === "error") {
          const parsed = JSON.parse(data) as { detail: string };
          setTurns((all) =>
            all.map((t) =>
              t.id === id
                ? { ...t, status: "error", error: parsed.detail }
                : t,
            ),
          );
        }
      });
    } catch (err: unknown) {
      if ((err as Error).name === "AbortError") return;
      const message = err instanceof Error ? err.message : String(err);
      setTurns((all) =>
        all.map((t) =>
          t.id === id ? { ...t, status: "error", error: message } : t,
        ),
      );
    } finally {
      abortRef.current = null;
      setStreaming(false);
    }
  };

  return (
    <>
      <Topbar
        title="Ask the Risk Analyst"
        subtitle="Streaming RAG over your vendor portfolio · cite-and-recall"
      />
      <PageTransition>
        <div className="flex flex-1 min-h-0">
          {/* Main column */}
          <div className="flex-1 flex flex-col min-w-0">
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
              {turns.length === 0 ? (
                <EmptyState onPick={ask} />
              ) : (
                turns.map((t) => <TurnView key={t.id} turn={t} />)
              )}
            </div>

            {/* Composer */}
            <div className="border-t border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-950/60 backdrop-blur-xl px-8 py-4">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  ask(input);
                }}
                className="max-w-3xl mx-auto flex items-end gap-2"
              >
                <div className="flex-1 relative">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        ask(input);
                      }
                    }}
                    placeholder="Ask about your vendors — try 'Which vendors are at CRITICAL risk?'"
                    rows={2}
                    disabled={streaming}
                    className="w-full resize-none px-4 py-3 pr-12 text-sm rounded-xl border border-zinc-300 dark:border-zinc-700/80 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-red-500/40 focus:border-zinc-400 dark:focus:border-zinc-500"
                  />
                </div>
                {streaming ? (
                  <button
                    type="button"
                    onClick={cancel}
                    className="inline-flex items-center gap-2 px-4 py-3 text-sm rounded-xl bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 hover:bg-zinc-300 dark:hover:bg-zinc-700"
                  >
                    <Square className="size-4" fill="currentColor" />
                    Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!input.trim()}
                    className={cn(
                      "inline-flex items-center gap-2 px-4 py-3 text-sm rounded-xl text-white shadow-md shadow-red-500/20",
                      "bg-linear-to-br from-red-500 to-amber-500",
                      "hover:opacity-95 disabled:opacity-40 disabled:cursor-not-allowed",
                    )}
                  >
                    <ArrowUp className="size-4" />
                    Ask
                  </button>
                )}
              </form>
              <p className="max-w-3xl mx-auto mt-2 text-[11px] text-zinc-400 dark:text-zinc-500">
                Answers are grounded in retrieved vendor profiles. Citations appear on the right.
              </p>
            </div>
          </div>

          {/* Citations sidebar */}
          <CitationsPanel turns={turns} />
        </div>
      </PageTransition>
    </>
  );
}

// ── Components ────────────────────────────────────────────────────────
function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="max-w-3xl mx-auto mt-16 space-y-6 text-center">
      <div className="inline-flex items-center justify-center size-12 rounded-xl bg-linear-to-br from-red-500 to-amber-500 text-white shadow-lg shadow-red-500/20">
        <Sparkles className="size-6" />
      </div>
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          Ask anything about your vendor portfolio
        </h2>
        <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
          The model retrieves the most relevant vendors first, then answers with citations.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-2xl mx-auto text-left">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="px-4 py-3 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-sm text-sm text-zinc-700 dark:text-zinc-200 hover:bg-white dark:hover:bg-zinc-800/80 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  return (
    <div className="max-w-3xl mx-auto space-y-3">
      {/* Question */}
      <div className="flex items-start gap-3">
        <div className="size-7 rounded-md bg-zinc-200 dark:bg-zinc-800 grid place-items-center text-zinc-600 dark:text-zinc-300 shrink-0">
          <User className="size-3.5" />
        </div>
        <p className="text-sm pt-1 text-zinc-900 dark:text-zinc-100">
          {turn.question}
        </p>
      </div>

      {/* Answer */}
      <div className="flex items-start gap-3">
        <div className="size-7 rounded-md bg-linear-to-br from-red-500 to-amber-500 grid place-items-center text-white shrink-0">
          <Bot className="size-3.5" />
        </div>
        <div className="flex-1 min-w-0 pt-0.5">
          {turn.status === "error" ? (
            <div className="rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-3 py-2 text-sm text-red-700 dark:text-red-300">
              {turn.error || "Something went wrong"}
            </div>
          ) : turn.answer ? (
            <div className="prose-sm whitespace-pre-wrap text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
              <CitedText text={turn.answer} />
              {turn.status === "streaming" && (
                <motion.span
                  animate={{ opacity: [0.2, 1, 0.2] }}
                  transition={{ duration: 1.2, repeat: Infinity }}
                  className="inline-block size-2 ml-1 align-middle rounded-full bg-zinc-600 dark:bg-zinc-300"
                />
              )}
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 text-sm text-zinc-500">
              <Loader2 className="size-3.5 animate-spin" />
              Retrieving relevant vendors…
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Renders the answer text, turning [V0123] markers into Vendor links. */
function CitedText({ text }: { text: string }) {
  const parts = text.split(/(\[V\d{4}\])/g);
  return (
    <>
      {parts.map((p, i) => {
        const m = p.match(/^\[(V\d{4})\]$/);
        if (!m) return <span key={i}>{p}</span>;
        const vid = m[1];
        return (
          <Link
            key={i}
            href={`/vendors/${vid}`}
            className="inline-flex items-center px-1.5 mx-0.5 text-[11px] font-mono rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-700 dark:hover:text-red-300 transition-colors align-baseline"
          >
            {vid}
          </Link>
        );
      })}
    </>
  );
}

function CitationsPanel({ turns }: { turns: Turn[] }) {
  const latest = turns[turns.length - 1];
  const citations = latest?.citations ?? [];

  return (
    <aside className="hidden xl:flex w-96 shrink-0 flex-col border-l border-zinc-200/80 dark:border-zinc-800/80 bg-zinc-50/60 dark:bg-zinc-950/40 backdrop-blur-md">
      <div className="px-5 py-4 border-b border-zinc-200/80 dark:border-zinc-800/80 flex items-center gap-2">
        <Database className="size-4 text-zinc-500" />
        <h2 className="text-sm font-semibold">Retrieved context</h2>
        {citations.length > 0 && (
          <span className="ml-auto text-[11px] font-mono text-zinc-500">
            {citations.length} chunk{citations.length === 1 ? "" : "s"}
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        <AnimatePresence initial={false}>
          {citations.length === 0 ? (
            <p className="text-xs text-zinc-400 px-2 mt-2">
              Citations will appear here once you ask a question.
            </p>
          ) : (
            citations.map((c, i) => (
              <motion.div
                key={`${c.vendor_id}-${i}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-3"
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <Link
                    href={`/vendors/${c.vendor_id}`}
                    className="text-[11px] font-mono font-semibold text-zinc-900 dark:text-zinc-100 hover:underline"
                  >
                    {c.vendor_id}
                  </Link>
                  <span className="text-[10px] tabular-nums text-zinc-500 font-mono">
                    sim {(c.similarity * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-[11px] text-zinc-600 dark:text-zinc-400 leading-snug line-clamp-6">
                  {c.chunk}
                </p>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </aside>
  );
}

// ── SSE parser ────────────────────────────────────────────────────────
async function consumeSSE(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: string, data: string) => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // Normalise CRLF → LF; sse-starlette uses \r\n line endings, our parser splits on \n\n
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    // SSE messages are separated by blank lines (\n\n after normalisation)
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const lines = raw.split("\n");
      let event = "message";
      const dataParts: string[] = [];
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataParts.push(line.slice(5).trimStart());
      }
      const data = dataParts.join("\n");
      if (event || data) onEvent(event, data);
    }
  }
}
