"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Activity,
  Bell,
  FileSearch,
  LayoutDashboard,
  MessagesSquare,
  ShieldAlert,
} from "lucide-react";
import { cn } from "../lib/cn";

const NAV = [
  { href: "/", label: "Portfolio", icon: LayoutDashboard, exact: true },
  { href: "/vendors", label: "Vendors", icon: ShieldAlert },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/ask", label: "Ask", icon: MessagesSquare },
  { href: "/eval", label: "Model Eval", icon: Activity },
  { href: "/audit", label: "Audit Pack", icon: FileSearch },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 shrink-0 border-r border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-950/60 backdrop-blur-xl min-h-screen p-4 flex flex-col">
      <div className="flex items-center gap-2.5 mb-8 px-2">
        <div className="size-9 rounded-lg bg-linear-to-br from-red-500 via-red-600 to-amber-500 grid place-items-center text-white font-bold text-sm shadow-md shadow-red-500/20">
          V
        </div>
        <div className="leading-tight">
          <p className="font-semibold text-sm tracking-tight">VRM Intelligence</p>
          <p className="text-[10px] text-zinc-500 dark:text-zinc-400 font-medium tracking-wide uppercase">Société Générale</p>
        </div>
      </div>
      <nav className="space-y-0.5">
        {NAV.map((item) => {
          const active = item.exact
            ? pathname === item.href
            : pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "relative flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg transition-colors duration-150",
                active
                  ? "text-zinc-900 dark:text-zinc-100 font-medium"
                  : "text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200",
              )}
            >
              {active && (
                <motion.div
                  layoutId="sidebar-active-pill"
                  className="absolute inset-0 rounded-lg bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/60 dark:border-zinc-700/50"
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                />
              )}
              <span className="relative z-10 flex items-center gap-2.5">
                <Icon className={cn("size-4", active && "text-red-500")} />
                <span>{item.label}</span>
              </span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto pt-4 border-t border-zinc-200/60 dark:border-zinc-800/60">
        <p className="text-[10px] text-zinc-400 dark:text-zinc-500 px-2 font-mono">
          rules-v1.1 · 400 vendors
        </p>
      </div>
    </aside>
  );
}
