/** RGB tuple: [red, green, blue] each 0-255 */
export type RgbTuple = [number, number, number];

/** RGBA quad: [red, green, blue, alpha] each 0-255 */
export type RgbaQuad = [number, number, number, number];

/** Convert "#RRGGBB" hex string to RGB tuple */
export function hexToRgb(hex: string): RgbTuple {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

/** Convert "#RRGGBB" hex string + alpha (0-255) to RGBA quad */
export function hexToRgba(hex: string, alpha: number): RgbaQuad {
  const [r, g, b] = hexToRgb(hex);
  return [r, g, b, alpha];
}

/** Convert RGB tuple to CSS string: "rgb(R, G, B)" */
export function rgbToCss(rgb: RgbTuple): string {
  return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
}

/** Convert RGB tuple to comma-separated components: "R, G, B" (for CSS rgba(var(--x-rgb), alpha)) */
export function rgbToComponents(rgb: RgbTuple): string {
  return `${rgb[0]}, ${rgb[1]}, ${rgb[2]}`;
}

/** Append alpha channel (0-255) to an RGB tuple */
export function withAlpha(rgb: RgbTuple, alpha: number): RgbaQuad {
  return [rgb[0], rgb[1], rgb[2], alpha];
}
