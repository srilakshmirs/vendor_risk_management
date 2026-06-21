"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { use, useState } from "react";
import {
  AlertOctagon,
  ArrowLeft,
  Calendar,
  CircleCheck,
  CircleX,
  FileDown,
  Loader2,
  Mail,
  RefreshCw,
  Sparkles,
  Upload,
  FileText,
} from "lucide-react";
import { useSWRConfig } from "swr";

import { ComponentBreakdown } from "../../../components/ComponentBreakdown";
import { PageTransition } from "../../../components/PageTransition";
import { RiskGauge } from "../../../components/RiskGauge";
import { SeverityBadge } from "../../../components/SeverityBadge";
import { Skeleton, SkeletonCard, SkeletonLines } from "../../../components/Skeleton";
import { SupplyChainCard } from "../../../components/SupplyChainCard";
import { TrafficLight } from "../../../components/TrafficLight";
import { Topbar } from "../../../components/Topbar";
import { api } from "../../../lib/api/client";
import { useLatestRisk, useVendor } from "../../../lib/api/hooks";
import { cn } from "../../../lib/cn";
import { fmtDate, fmtUSD } from "../../../lib/format";

export default function VendorDetailPage({
  params,
}: {
  params: Promise<{ vendorId: string }>;
}) {
  const { vendorId } = use(params);
  const { data: vendor, isLoading } = useVendor(vendorId);
  const { data: latestRisk, mutate: refreshLatest } = useLatestRisk(vendorId);
  const { mutate } = useSWRConfig();
  const [recomputing, setRecomputing] = useState(false);
  const [enhancing, setEnhancing] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedContract, setExtractedContract] = useState<any>(null);

  const enhance = async () => {
    setEnhancing(true);
    try {
      await api.enhanceNarrative(vendorId, true);
      await refreshLatest();
    } catch (err) {
      console.error(err);
      alert("LLM enhancement failed. Check the API logs.");
    } finally {
      setEnhancing(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsExtracting(true);
    try {
      const result = await api.extractContract(file, vendorId);
      // The backend returns { fields: {...}, source_filename: "..." }
      setExtractedContract(result.fields || result);
    } catch (err) {
      alert("Failed to extract contract. Check console for details.");
      console.error(err);
    } finally {
      setIsExtracting(false);
    }
    // reset input
    e.target.value = "";
  };

  const recompute = async () => {
    setRecomputing(true);
    try {
      await api.scoreVendor(vendorId, true);
      // Invalidate everything that depends on this vendor + global metrics
      await Promise.all([
        refreshLatest(),
        mutate(["vendor", vendorId]),
        mutate("severity-counts"),
        mutate("eval"),
      ]);
    } finally {
      setRecomputing(false);
    }
  };

  if (isLoading && !vendor) {
    return (
      <>
        <Topbar
          title="Loading vendor…"
          subtitle={vendorId}
        />
        <PageTransition>
          <div className="px-8 py-6 space-y-6">
            {/* Toolbar row */}
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-28" />
              <div className="flex items-center gap-2">
                <Skeleton className="h-9 w-40" />
                <Skeleton className="h-9 w-36" />
              </div>
            </div>
            {/* Hero row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <SkeletonCard>
                <Skeleton className="h-5 w-32 mb-4" />
                <Skeleton className="h-32 w-full rounded-lg" />
                <div className="mt-3 flex items-center justify-between">
                  <Skeleton className="h-5 w-20" />
                  <Skeleton className="h-3 w-16" />
                </div>
              </SkeletonCard>
              <SkeletonCard>
                <Skeleton className="h-5 w-40 mb-4" />
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i}>
                      <div className="flex justify-between mb-1">
                        <Skeleton className="h-3 w-24" />
                        <Skeleton className="h-3 w-12" />
                      </div>
                      <Skeleton className="h-2 w-full rounded-full" />
                    </div>
                  ))}
                </div>
              </SkeletonCard>
              <SkeletonCard>
                <Skeleton className="h-5 w-36 mb-4" />
                <SkeletonLines count={4} />
              </SkeletonCard>
            </div>
            {/* Profile + certs + data access row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <SkeletonCard key={i}>
                  <Skeleton className="h-5 w-28 mb-4" />
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, j) => (
                      <div key={j} className="flex justify-between">
                        <Skeleton className="h-3 w-24" />
                        <Skeleton className="h-3 w-28" />
                      </div>
                    ))}
                  </div>
                </SkeletonCard>
              ))}
            </div>
          </div>
        </PageTransition>
      </>
    );
  }

  if (!vendor) {
    return (
      <>
        <Topbar title="Vendor not found" />
        <div className="px-8 py-10 text-zinc-500">
          No vendor with ID <code>{vendorId}</code>.
          <Link href="/vendors" className="ml-2 underline">
            Back to list
          </Link>
        </div>
      </>
    );
  }

  const dataAccess = vendor.data_access[0];
  const dataClasses = dataAccess?.data_classes
    ? dataAccess.data_classes.split(";").filter(Boolean)
    : [];
  const systems = dataAccess?.systems_accessed
    ? dataAccess.systems_accessed.split(";").filter(Boolean)
    : [];

  return (
    <>
      <Topbar
        title={vendor.name}
        subtitle={`${vendor.vendor_id} · ${vendor.vendor_type} · ${vendor.country} · ${vendor.criticality}`}
      />

      <PageTransition>
      <div className="px-8 py-6 space-y-6">
        {/* Back + actions */}
        <div className="flex items-center justify-between">
          <Link
            href="/vendors"
            className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
          >
            <ArrowLeft className="size-4" />
            All vendors
          </Link>
          <div className="flex items-center gap-2">
            <a
              href={api.auditPackUrl(vendorId)}
              download
              className={cn(
                "inline-flex items-center gap-2 px-3 py-1.5 text-sm rounded-md text-white shadow-sm shadow-red-500/20",
                "bg-linear-to-br from-red-500 to-amber-500 hover:opacity-95",
              )}
            >
              <FileDown className="size-4" />
              Export Audit Pack
            </a>
            <button
              onClick={recompute}
              disabled={recomputing}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-1.5 text-sm rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800",
                recomputing && "opacity-60 cursor-wait",
              )}
            >
              <RefreshCw className={cn("size-4", recomputing && "animate-spin")} />
              Recompute risk
            </button>
          </div>
        </div>

        {/* Hero row: gauge + breakdown + narrative */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6 overflow-hidden">
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-lg font-semibold">Risk Posture</h2>
              {latestRisk && (
                <TrafficLight light={latestRisk.traffic_light} />
              )}
            </div>
            <RiskGauge score={latestRisk?.score ?? vendor.preliminary_risk_score} />
            <div className="mt-2 flex items-center justify-between text-sm">
              {latestRisk ? (
                <SeverityBadge severity={latestRisk.severity} />
              ) : (
                <span className="text-zinc-500">Run scoring to refresh</span>
              )}
              <span className="text-zinc-400 text-[11px] font-mono">
                {latestRisk?.model_version ?? "—"}
              </span>
            </div>
            {latestRisk?.anomaly_type && latestRisk.anomaly_type !== "NONE" && (
              <div className="mt-3 inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 text-[11px] font-mono">
                <AlertOctagon className="size-3" />
                {latestRisk.anomaly_type}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">Component breakdown</h2>
            {latestRisk?.components ? (
              <ComponentBreakdown
                components={latestRisk.components as Record<string, number>}
              />
            ) : (
              <p className="text-sm text-zinc-500">
                No scoring on record yet — click <em>Recompute risk</em>.
              </p>
            )}
          </div>

          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6 flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="size-4 text-amber-500" />
              <h2 className="text-lg font-semibold">Risk Narrative</h2>
              {latestRisk?.narrative_source === "llm" && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider text-white bg-linear-to-br from-red-500 to-amber-500">
                  <Sparkles className="size-2.5" />
                  AI
                </span>
              )}
              {latestRisk?.narrative_source === "deterministic-fallback" && (
                <span className="text-[10px] font-mono text-zinc-400">
                  rules
                </span>
              )}
              <button
                onClick={enhance}
                disabled={enhancing || !latestRisk}
                title="Generate a richer narrative via the LLM"
                className={cn(
                  "ml-auto inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded-md transition-colors",
                  "border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900",
                  "hover:bg-zinc-50 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200",
                  enhancing && "opacity-60 cursor-wait",
                )}
              >
                {enhancing ? (
                  <Loader2 className="size-3 animate-spin" />
                ) : (
                  <Sparkles className="size-3 text-amber-500" />
                )}
                {enhancing ? "Generating…" : "Enhance"}
              </button>
            </div>
            <motion.p
              key={latestRisk?.narrative ?? "empty"}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
              className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-200 flex-1"
            >
              {latestRisk?.narrative ?? "No narrative available yet."}
            </motion.p>
            {latestRisk?.narrative_model && (
              <p className="mt-2 text-[10px] font-mono text-zinc-400">
                via {latestRisk.narrative_provider}
                {latestRisk.narrative_model && ` · ${latestRisk.narrative_model}`}
              </p>
            )}
            {latestRisk?.triggered_rules &&
              latestRisk.triggered_rules.length > 0 && (
                <div className="mt-4 pt-4 border-t border-zinc-200 dark:border-zinc-800">
                  <p className="text-[11px] uppercase tracking-wider text-zinc-500 mb-2">
                    Triggered rules
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {latestRisk.triggered_rules.map((r) => (
                      <span
                        key={r}
                        className="px-2 py-0.5 rounded font-mono text-[11px] bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                      >
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}
          </div>
        </div>

        {/* Contract Extraction Section */}
        <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="size-5 text-indigo-500" />
              <h2 className="text-lg font-semibold">Contract Intelligence</h2>
            </div>
            <label className={cn(
              "inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 cursor-pointer transition-colors",
              isExtracting && "opacity-60 cursor-wait"
            )}>
              {isExtracting ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Extracting...
                </>
              ) : (
                <>
                  <Upload className="size-4" />
                  Upload PDF
                </>
              )}
              <input 
                type="file" 
                accept="application/pdf" 
                className="hidden" 
                onChange={handleUpload}
                disabled={isExtracting}
              />
            </label>
          </div>

          {!extractedContract && !isExtracting && (
            <div className="py-8 text-center border-2 border-dashed border-zinc-200 dark:border-zinc-800 rounded-lg">
              <p className="text-sm text-zinc-500">Upload a vendor contract (PDF) to automatically extract risk obligations.</p>
            </div>
          )}

          {extractedContract && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs uppercase tracking-wider text-zinc-500 mb-1">Data Access Permissions</h3>
                  <ul className="list-disc pl-4 text-sm text-zinc-800 dark:text-zinc-200 space-y-1">
                    {extractedContract.data_access_permissions?.map((p: string, i: number) => (
                      <li key={i}>{p}</li>
                    )) || <span className="text-zinc-400">None detected</span>}
                  </ul>
                </div>
                <div>
                  <h3 className="text-xs uppercase tracking-wider text-zinc-500 mb-1">Compliance Obligations</h3>
                  <ul className="list-disc pl-4 text-sm text-zinc-800 dark:text-zinc-200 space-y-1">
                    {extractedContract.compliance_obligations?.map((o: string, i: number) => (
                      <li key={i}>{o}</li>
                    )) || <span className="text-zinc-400">None detected</span>}
                  </ul>
                </div>
              </div>
              <div className="space-y-4">
                <dl className="space-y-2">
                  <div className="bg-zinc-50 dark:bg-zinc-800/50 p-3 rounded-md">
                    <dt className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">SLA Uptime Guarantee</dt>
                    <dd className="font-medium text-sm">{extractedContract.sla_uptime_percentage || "Not specified"}</dd>
                  </div>
                  <div className="bg-zinc-50 dark:bg-zinc-800/50 p-3 rounded-md">
                    <dt className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">Renewal Date</dt>
                    <dd className="font-medium text-sm">{extractedContract.renewal_date || "Not specified"}</dd>
                  </div>
                  <div className="bg-zinc-50 dark:bg-zinc-800/50 p-3 rounded-md">
                    <dt className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">Termination Conditions</dt>
                    <dd className="text-sm text-zinc-700 dark:text-zinc-300">{extractedContract.termination_conditions || "None found"}</dd>
                  </div>
                </dl>
              </div>
            </div>
          )}
        </div>

        {/* Supply chain (SBOM) */}
        <SupplyChainCard vendorCode={vendorId} />

        {/* Profile + certs + data access */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Profile card */}
          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">Profile</h2>
            <dl className="space-y-2 text-sm">
              <Field label="Annual spend">{fmtUSD(vendor.annual_spend_usd)}</Field>
              <Field label="Financial health">
                {vendor.financial_health_score}/100
              </Field>
              <Field label="Preliminary risk">
                {vendor.preliminary_risk_score}/100
              </Field>
              <Field label="Status">{vendor.status}</Field>
              <Field label="Investigation">
                {vendor.under_investigation ? (
                  <span className="text-red-600 dark:text-red-400 font-medium">
                    Active
                  </span>
                ) : (
                  "None"
                )}
              </Field>
              <Field label="Last assessment" icon={<Calendar className="size-3" />}>
                {fmtDate(vendor.last_assessment_date)}
              </Field>
              <Field label="Primary contact" icon={<Mail className="size-3" />}>
                {vendor.primary_contact_email ?? "—"}
              </Field>
            </dl>
          </div>

          {/* Certifications */}
          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">Certifications</h2>
            <ul className="space-y-2 text-sm">
              {vendor.certifications.map((c) => {
                const isExpired = c.status === "Expired";
                const isCertified = c.status === "Certified";
                return (
                  <li
                    key={c.cert_type}
                    className="flex items-center justify-between gap-2 px-3 py-2 rounded-md border border-zinc-200 dark:border-zinc-800"
                  >
                    <div className="flex items-center gap-2">
                      {isCertified ? (
                        <CircleCheck className="size-4 text-emerald-500" />
                      ) : isExpired ? (
                        <CircleX className="size-4 text-red-500" />
                      ) : (
                        <span className="inline-block size-2 rounded-full bg-zinc-400" />
                      )}
                      <span className="font-medium">{c.cert_type}</span>
                    </div>
                    <div className="text-right">
                      <p
                        className={cn(
                          "text-xs font-medium",
                          isExpired && "text-red-600 dark:text-red-400",
                          isCertified && "text-emerald-600 dark:text-emerald-400",
                          !isExpired && !isCertified && "text-zinc-500",
                        )}
                      >
                        {c.status}
                      </p>
                      <p className="text-[11px] text-zinc-400">
                        {fmtDate(c.expiry_date)}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Data access */}
          <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/60 backdrop-blur-md shadow-sm p-6">
            <h2 className="text-lg font-semibold mb-4">Data access</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                  Access level
                </dt>
                <dd className="font-medium">
                  {dataAccess?.access_level ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                  Data classes
                </dt>
                <dd className="flex flex-wrap gap-1.5">
                  {dataClasses.map((c) => {
                    const sensitive = ["PII", "PCI", "PHI", "Financial"].includes(c);
                    return (
                      <span
                        key={c}
                        className={cn(
                          "px-2 py-0.5 rounded text-[11px] font-mono",
                          sensitive
                            ? "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-900"
                            : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300",
                        )}
                      >
                        {c}
                      </span>
                    );
                  })}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                  Systems accessed
                </dt>
                <dd className="flex flex-wrap gap-1.5">
                  {systems.map((s) => (
                    <span
                      key={s}
                      className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300"
                    >
                      {s}
                    </span>
                  ))}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                  GDPR
                </dt>
                <dd
                  className={cn(
                    "font-medium",
                    dataAccess?.gdpr_compliant
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-red-600 dark:text-red-400",
                  )}
                >
                  {dataAccess?.gdpr_compliant ? "Compliant" : "Not compliant"}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
      </PageTransition>
    </>
  );
}

function Field({
  label,
  children,
  icon,
}: {
  label: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 border-b border-zinc-100 dark:border-zinc-900 last:border-b-0">
      <dt className="text-zinc-500 inline-flex items-center gap-1.5">
        {icon}
        {label}
      </dt>
      <dd className="text-zinc-900 dark:text-zinc-100 font-medium text-right">
        {children}
      </dd>
    </div>
  );
}
