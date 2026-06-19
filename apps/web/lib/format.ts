export const fmtUSD = (n: number): string =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);

export const fmtPct = (n: number, digits = 1): string =>
  `${(n * 100).toFixed(digits)}%`;

export const fmtDate = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
};

export const fmtNum = (n: number): string =>
  new Intl.NumberFormat("en-US").format(n);
