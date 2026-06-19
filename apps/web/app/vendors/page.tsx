"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  Search,
  ShieldAlert,
} from "lucide-react";

import { Checkbox } from "../../components/Checkbox";
import { PageTransition } from "../../components/PageTransition";
import { RiskBar } from "../../components/RiskBar";
import { Select } from "../../components/Select";
import { Topbar } from "../../components/Topbar";
import { useVendors } from "../../lib/api/hooks";
import { cn } from "../../lib/cn";
import { fmtUSD } from "../../lib/format";

const VENDOR_TYPES = [
  "CloudProvider",
  "SaaS",
  "Contractor",
  "MSP",
  "PaymentProcessor",
  "IntegrationPartner",
  "Hardware",
  "Consulting",
  "DataAnalytics",
  "Marketing",
];
const TIERS = ["Tier1", "Tier2", "Tier3", "Tier4"];
const PAGE_SIZE = 25;

type SortField =
  | "preliminary_risk_score"
  | "name"
  | "vendor_type"
  | "annual_spend_usd"
  | "criticality";

export default function VendorsListPage() {
  const [q, setQ] = useState("");
  const [vendorType, setVendorType] = useState("");
  const [criticality, setCriticality] = useState("");
  const [underInvestigation, setUnderInvestigation] = useState<boolean | undefined>(undefined);
  const [sortField, setSortField] = useState<SortField>("preliminary_risk_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);

  const params = useMemo(
    () => ({
      q: q || undefined,
      vendor_type: vendorType || undefined,
      criticality: criticality || undefined,
      under_investigation: underInvestigation,
      sort: `${sortField}:${sortDir}`,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }),
    [q, vendorType, criticality, underInvestigation, sortField, sortDir, page],
  );

  const { data, isLoading } = useVendors(params);
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
    setPage(0);
  };

  const resetFilters = () => {
    setQ("");
    setVendorType("");
    setCriticality("");
    setUnderInvestigation(undefined);
    setPage(0);
  };

  return (
    <>
      <Topbar
        title="Vendor Registry"
        subtitle={`${total.toLocaleString()} vendors · filter, sort, drill in`}
      />

      <PageTransition>
      <div className="px-8 py-6 space-y-4">
        {/* Filters */}
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md p-4 flex flex-wrap items-center gap-3 shadow-sm">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="size-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(0);
              }}
              placeholder="Search by name or vendor ID…"
              className="w-full pl-9 pr-3 py-2 text-sm rounded-md border border-zinc-300 dark:border-zinc-700/80 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 shadow-sm focus:outline-none focus:ring-2 focus:ring-zinc-500/40 focus:border-zinc-400 dark:focus:border-zinc-500"
            />
          </div>

          <div className="min-w-[160px]">
            <Select
              value={vendorType}
              onChange={(e) => {
                setVendorType(e.target.value);
                setPage(0);
              }}
            >
              <option value="">All types</option>
              {VENDOR_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </div>

          <div className="min-w-[140px]">
            <Select
              value={criticality}
              onChange={(e) => {
                setCriticality(e.target.value);
                setPage(0);
              }}
            >
              <option value="">All tiers</option>
              {TIERS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </div>

          <Checkbox
            checked={underInvestigation === true}
            onChange={(next) => {
              setUnderInvestigation(next ? true : undefined);
              setPage(0);
            }}
            label="Under investigation"
          />

          {(q || vendorType || criticality || underInvestigation !== undefined) && (
            <button
              onClick={resetFilters}
              className="ml-auto text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 underline"
            >
              Reset
            </button>
          )}
        </div>

        {/* Table */}
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-950 border-b border-zinc-200 dark:border-zinc-800">
                <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
                  <SortableTh field="name" onSort={toggleSort} active={sortField} dir={sortDir}>
                    Vendor
                  </SortableTh>
                  <SortableTh
                    field="vendor_type"
                    onSort={toggleSort}
                    active={sortField}
                    dir={sortDir}
                  >
                    Type
                  </SortableTh>
                  <th className="py-3 px-3 font-medium">Country</th>
                  <SortableTh
                    field="criticality"
                    onSort={toggleSort}
                    active={sortField}
                    dir={sortDir}
                  >
                    Tier
                  </SortableTh>
                  <SortableTh
                    field="annual_spend_usd"
                    onSort={toggleSort}
                    active={sortField}
                    dir={sortDir}
                    align="right"
                  >
                    Annual Spend
                  </SortableTh>
                  <SortableTh
                    field="preliminary_risk_score"
                    onSort={toggleSort}
                    active={sortField}
                    dir={sortDir}
                  >
                    Risk
                  </SortableTh>
                  <th className="py-3 px-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {isLoading && !data ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-zinc-400">
                      <Loader2 className="size-5 animate-spin inline" />
                    </td>
                  </tr>
                ) : data?.items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-zinc-500">
                      No vendors match the current filters.
                    </td>
                  </tr>
                ) : (
                  data?.items.map((v, i) => (
                    <motion.tr
                      key={v.vendor_id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: Math.min(i * 0.015, 0.25), duration: 0.25 }}
                      className="border-b border-zinc-100 dark:border-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800/40 transition-colors"
                    >
                      <td className="py-2.5 px-3">
                        <Link
                          href={`/vendors/${v.vendor_id}`}
                          className="font-medium hover:underline"
                        >
                          {v.name}
                        </Link>
                        <div className="text-[11px] font-mono text-zinc-400">
                          {v.vendor_id}
                          {v.under_investigation && (
                            <span className="ml-2 inline-flex items-center gap-1 text-red-600 dark:text-red-400">
                              <ShieldAlert className="size-3" />
                              under investigation
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-zinc-600 dark:text-zinc-300">
                        {v.vendor_type}
                      </td>
                      <td className="py-2.5 px-3 text-zinc-600 dark:text-zinc-300">
                        {v.country}
                      </td>
                      <td className="py-2.5 px-3 text-zinc-600 dark:text-zinc-300">
                        {v.criticality}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-zinc-600 dark:text-zinc-300">
                        {fmtUSD(v.annual_spend_usd)}
                      </td>
                      <td className="py-2.5 px-3 w-56">
                        <RiskBar score={v.preliminary_risk_score} />
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Link
                          href={`/vendors/${v.vendor_id}`}
                          className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
                        >
                          Open →
                        </Link>
                      </td>
                    </motion.tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-200 dark:border-zinc-800 text-sm">
            <span className="text-zinc-500">
              {data
                ? `Showing ${page * PAGE_SIZE + 1}–${Math.min(
                    (page + 1) * PAGE_SIZE,
                    total,
                  )} of ${total}`
                : "—"}
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="size-3.5" />
                Prev
              </button>
              <span className="text-zinc-500 tabular-nums">
                {page + 1} / {pageCount}
              </span>
              <button
                disabled={page >= pageCount - 1}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
                <ChevronRight className="size-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
      </PageTransition>
    </>
  );
}

function SortableTh({
  field,
  active,
  dir,
  onSort,
  children,
  align = "left",
}: {
  field: SortField;
  active: SortField;
  dir: "asc" | "desc";
  onSort: (f: SortField) => void;
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  const isActive = active === field;
  return (
    <th
      className={cn(
        "py-3 px-3 font-medium select-none cursor-pointer hover:text-zinc-700 dark:hover:text-zinc-200",
        align === "right" ? "text-right" : "text-left",
        isActive && "text-zinc-900 dark:text-zinc-100",
      )}
      onClick={() => onSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {isActive && (
          <span className="text-[10px]">{dir === "desc" ? "▼" : "▲"}</span>
        )}
      </span>
    </th>
  );
}
