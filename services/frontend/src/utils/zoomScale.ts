// Reference zoom level (default São Paulo view)
const REFERENCE_ZOOM = 11;

/**
 * Calculate scale multiplier based on zoom level.
 *
 * @param zoom - Current map zoom level (continuous, e.g., 11.5)
 * @param layerZoomScaleFactor - Rate of scaling per zoom level:
 *   - 1.0 = no scaling (constant size regardless of zoom)
 *   - 1.1 = 10% larger per zoom level in, 10% smaller per zoom level out
 *   - 2.0 = double per zoom level in, half per zoom level out
 * @returns Scale multiplier to apply to base sizes/widths
 *
 * Examples with layerZoomScaleFactor = 1.15, reference zoom = 11:
 *   zoom 12 → 1.15^1 = 1.15 (15% larger)
 *   zoom 14 → 1.15^3 = 1.52 (52% larger)
 *   zoom 10 → 1.15^-1 = 0.87 (13% smaller)
 *   zoom 8  → 1.15^-3 = 0.66 (34% smaller)
 */
export function calculateZoomScale(zoom: number, layerZoomScaleFactor: number = 1.15): number {
  return Math.pow(layerZoomScaleFactor, zoom - REFERENCE_ZOOM);
}
