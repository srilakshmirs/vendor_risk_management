"use client";

import Link from "next/link";
import { useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "../lib/cn";

/**
 * Renders a streamed LLM answer with proper markdown formatting AND
 * preserves the `[V0276]` citation pattern as a clickable internal link.
 *
 * Pre-processes the raw text by rewriting bare `[V0276]` into a proper
 * markdown link `[V0276](/vendors/V0276)` before handing it to react-markdown.
 * The custom `<a>` renderer then recognises `/vendors/...` hrefs and renders
 * them as Next.js `<Link>` pills (no full-page navigation).
 */
const VENDOR_REF = /\[(V\d{4})\](?!\()/g; // [V0276] not already a link

function preprocessCitations(raw: string): string {
  return raw.replace(VENDOR_REF, "[$1](/vendors/$1)");
}

const components: Components = {
  // ── Inline pieces ───────────────────────────────────────────────
  a({ href, children, ...rest }) {
    const target = String(href ?? "");
    const isVendor = /^\/vendors\/V\d{4}$/.test(target);
    if (isVendor) {
      return (
        <Link
          href={target}
          className="inline-flex items-center px-1.5 mx-0.5 text-[11px] font-mono rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-700 dark:hover:text-red-300 transition-colors align-baseline no-underline"
        >
          {children}
        </Link>
      );
    }
    return (
      <a
        href={target}
        target="_blank"
        rel="noreferrer"
        className="text-red-600 dark:text-red-400 hover:underline"
        {...rest}
      >
        {children}
      </a>
    );
  },
  strong({ children }) {
    return <strong className="font-semibold text-zinc-900 dark:text-zinc-100">{children}</strong>;
  },
  em({ children }) {
    return <em className="italic text-zinc-700 dark:text-zinc-300">{children}</em>;
  },
  code({ className, children, ...rest }) {
    // Inline code (no language class)
    if (!className) {
      return (
        <code
          className="px-1 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-[0.85em] font-mono text-red-700 dark:text-red-300"
          {...rest}
        >
          {children}
        </code>
      );
    }
    // Block code (handled by `pre` below)
    return (
      <code className={cn("font-mono", className)} {...rest}>
        {children}
      </code>
    );
  },
  pre({ children }) {
    return (
      <pre className="my-2 rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/60 p-3 overflow-x-auto text-[12px] leading-relaxed">
        {children}
      </pre>
    );
  },

  // ── Block pieces ────────────────────────────────────────────────
  p({ children }) {
    return <p className="my-2 leading-relaxed">{children}</p>;
  },
  ul({ children }) {
    return <ul className="my-2 ml-5 list-disc space-y-1">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="my-2 ml-5 list-decimal space-y-1">{children}</ol>;
  },
  li({ children }) {
    return <li className="leading-relaxed">{children}</li>;
  },
  h1({ children }) {
    return <h1 className="mt-4 mb-2 text-lg font-semibold text-zinc-900 dark:text-zinc-100">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="mt-4 mb-2 text-base font-semibold text-zinc-900 dark:text-zinc-100">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="mt-3 mb-1 text-sm font-semibold text-zinc-900 dark:text-zinc-100">{children}</h3>;
  },
  blockquote({ children }) {
    return (
      <blockquote className="my-2 border-l-2 border-zinc-300 dark:border-zinc-700 pl-3 text-zinc-600 dark:text-zinc-400 italic">
        {children}
      </blockquote>
    );
  },
  hr() {
    return <hr className="my-3 border-zinc-200 dark:border-zinc-800" />;
  },
  // ── Tables (via remark-gfm) ─────────────────────────────────────
  table({ children }) {
    return (
      <div className="my-2 overflow-x-auto">
        <table className="w-full text-[13px] border-collapse">{children}</table>
      </div>
    );
  },
  thead({ children }) {
    return <thead className="bg-zinc-100 dark:bg-zinc-800/60">{children}</thead>;
  },
  th({ children }) {
    return <th className="px-2 py-1.5 text-left font-semibold border border-zinc-200 dark:border-zinc-800">{children}</th>;
  },
  td({ children }) {
    return <td className="px-2 py-1.5 border border-zinc-100 dark:border-zinc-900 align-top">{children}</td>;
  },
};

export function MarkdownAnswer({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  const processed = useMemo(() => preprocessCitations(text), [text]);
  return (
    <div className={cn("text-sm text-zinc-800 dark:text-zinc-200", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {processed}
      </ReactMarkdown>
    </div>
  );
}
