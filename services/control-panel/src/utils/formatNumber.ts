export function formatNumber(
  value: number | null | undefined,
  decimals: number,
  fallback = '-'
): string {
  if (value == null || !Number.isFinite(value)) return fallback;
  return value.toFixed(decimals);
}

export function formatPercent(
  value: number | null | undefined,
  decimals: number,
  fallback = '-'
): string {
  if (value == null || !Number.isFinite(value)) return fallback;
  return `${(value * 100).toFixed(decimals)}%`;
}
