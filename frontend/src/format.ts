export const pretty = (n: number | null | undefined) =>
  n == null || !Number.isFinite(n)
    ? "—"
    : Intl.NumberFormat("en", { notation: n > 9999 ? "compact" : "standard", maximumFractionDigits: 1 }).format(n);

export const duration = (seconds: number) => {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
};

export const clock = (date: Date, withSeconds = false) =>
  date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", ...(withSeconds && { second: "2-digit" }) });

export const percent = (fraction: number) => `${(fraction * 100).toFixed(1)}%`;
