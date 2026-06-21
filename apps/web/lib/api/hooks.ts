"use client";

import useSWR, { type SWRConfiguration } from "swr";
import { api } from "./client";
import type { AlertListParams, VendorListParams } from "./types";

const fetcherBase = <T,>(thunk: () => Promise<T>) => () => thunk();

export function useHealth(config?: SWRConfiguration) {
  return useSWR("health", fetcherBase(api.health), {
    refreshInterval: 30_000,
    ...config,
  });
}

export function useLLMInfo(config?: SWRConfiguration) {
  return useSWR("llm-info", fetcherBase(api.llmInfo), {
    revalidateOnFocus: false,
    ...config,
  });
}

export function useVendors(params: VendorListParams = {}, config?: SWRConfiguration) {
  const key = ["vendors", JSON.stringify(params)] as const;
  return useSWR(key, () => api.listVendors(params), {
    keepPreviousData: true,
    ...config,
  });
}

export function useVendor(vendorId: string | null, config?: SWRConfiguration) {
  return useSWR(
    vendorId ? ["vendor", vendorId] : null,
    () => api.getVendor(vendorId as string),
    config,
  );
}

export function useLatestRisk(vendorId: string | null, config?: SWRConfiguration) {
  return useSWR(
    vendorId ? ["latest-risk", vendorId] : null,
    () => api.latestRisk(vendorId as string),
    config,
  );
}

export function useEval(config?: SWRConfiguration) {
  return useSWR("eval", fetcherBase(api.eval), {
    refreshInterval: 60_000,
    revalidateOnFocus: false,
    ...config,
  });
}

export function useAlerts(params: AlertListParams = {}, config?: SWRConfiguration) {
  const key = ["alerts", JSON.stringify(params)] as const;
  return useSWR(key, () => api.listAlerts(params), {
    keepPreviousData: true,
    refreshInterval: 30_000,
    ...config,
  });
}

export function useAlertCounts(config?: SWRConfiguration) {
  return useSWR("alert-counts", fetcherBase(api.alertCounts), {
    refreshInterval: 20_000,
    ...config,
  });
}

export function useVendorSboms(vendorCode: string | null, config?: SWRConfiguration) {
  return useSWR(
    vendorCode ? ["sboms", vendorCode] : null,
    () => api.getSboms(vendorCode as string),
    config,
  );
}
