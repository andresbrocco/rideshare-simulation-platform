export function surgeToColor(surge: number): [number, number, number] {
  const clamped = Math.max(1.0, Math.min(2.5, surge));
  const normalized = (clamped - 1.0) / 1.5;

  if (normalized < 0.5) {
    const t = normalized * 2;
    return [Math.round(255 * t), 255, 0];
  } else {
    const t = (normalized - 0.5) * 2;
    return [255, Math.round(255 * (1 - t)), 0];
  }
}

export function getSurgeOpacity(surge: number): number {
  const normalized = (Math.min(surge, 2.5) - 1.0) / 1.5;
  return 0.2 + normalized * 0.4;
}
