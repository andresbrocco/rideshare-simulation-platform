/**
 * Centralized theme — single source of truth for every color in the frontend.
 *
 * Three regions:
 *   1. Stage colors (trip lifecycle)  — deck.gl layers, legends, controls
 *   2. UI palette                     — CSS variables for all UI components
 *   3. Offline palette                — CSS variables for offline demo page
 */

import { hexToRgb, rgbToCss, rgbToComponents, withAlpha } from './utils/colorUtils';
import type { RgbTuple, RgbaQuad } from './utils/colorUtils';

// ============================================================================
// Region 1 — Stage Colors (trip lifecycle)
// ============================================================================

/** Base + variant hex values per trip stage */
export const STAGE_HEX = {
  idle: { base: '#6B7280', light: '#9CA3AF' },
  available: { base: '#34D399' },
  requesting: { base: '#F97316', route: '#FDBA74' },
  pickup: { base: '#F59E0B', light: '#FBBF24', lighter: '#FDE047', route: '#FCD34D' },
  transit: { base: '#3B82F6', route: '#60A5FA' },
  completed: { base: '#4ADE80' },
  cancelled: { base: '#F87171' },
} as const;

/** Derived RGB tuples (for deck.gl getColor) */
export const STAGE_RGB = {
  idle: { base: hexToRgb(STAGE_HEX.idle.base), light: hexToRgb(STAGE_HEX.idle.light) },
  available: { base: hexToRgb(STAGE_HEX.available.base) },
  requesting: {
    base: hexToRgb(STAGE_HEX.requesting.base),
    route: hexToRgb(STAGE_HEX.requesting.route),
  },
  pickup: {
    base: hexToRgb(STAGE_HEX.pickup.base),
    light: hexToRgb(STAGE_HEX.pickup.light),
    lighter: hexToRgb(STAGE_HEX.pickup.lighter),
    route: hexToRgb(STAGE_HEX.pickup.route),
  },
  transit: { base: hexToRgb(STAGE_HEX.transit.base), route: hexToRgb(STAGE_HEX.transit.route) },
  completed: { base: hexToRgb(STAGE_HEX.completed.base) },
  cancelled: { base: hexToRgb(STAGE_HEX.cancelled.base) },
} as const satisfies Record<string, Record<string, RgbTuple>>;

/** Derived CSS rgb() strings (for SVG/HTML style attributes) */
export const STAGE_CSS = {
  idle: { base: rgbToCss(STAGE_RGB.idle.base), light: rgbToCss(STAGE_RGB.idle.light) },
  available: { base: rgbToCss(STAGE_RGB.available.base) },
  requesting: {
    base: rgbToCss(STAGE_RGB.requesting.base),
    route: rgbToCss(STAGE_RGB.requesting.route),
  },
  pickup: {
    base: rgbToCss(STAGE_RGB.pickup.base),
    light: rgbToCss(STAGE_RGB.pickup.light),
    lighter: rgbToCss(STAGE_RGB.pickup.lighter),
    route: rgbToCss(STAGE_RGB.pickup.route),
  },
  transit: { base: rgbToCss(STAGE_RGB.transit.base), route: rgbToCss(STAGE_RGB.transit.route) },
  completed: { base: rgbToCss(STAGE_RGB.completed.base) },
  cancelled: { base: rgbToCss(STAGE_RGB.cancelled.base) },
} as const;

/** Route trail colors at ~30% opacity (for completed route trails) */
export const STAGE_TRAIL: Record<string, RgbaQuad> = {
  pickup: withAlpha(STAGE_RGB.pickup.route, 80),
  transit: withAlpha(STAGE_RGB.transit.route, 80),
};

// ============================================================================
// Region 2 — UI Palette
// ============================================================================

export const UI = {
  // Backgrounds
  bgPrimary: '#1a1a2e',
  bgSecondary: '#16213e',
  bgSurface: '#1f2937',
  bgPopup: '#1e1e1e',

  // Text
  textPrimary: '#e4e4e7',
  textSecondary: '#a1a1aa',
  textMuted: '#888888',

  // Borders
  borderColor: '#374151',
  borderSubtle: '#444444',

  // Accents
  accentBlue: '#3B82F6',
  accentBlueDark: '#2563EB',
  accentBlueLight: '#60A5FA',
  accentGreen: '#10B981',
  accentOrange: '#F59E0B',
  accentRed: '#EF4444',
  accentRedDark: '#DC2626',

  // Status / functional
  successGreen: '#22C55E',
  successGreenDark: '#16A34A',
  disabledBg: '#6B7280',
} as const;

// ============================================================================
// Region 3 — Offline Palette
// ============================================================================

export const OFFLINE = {
  neon: '#00FF88',
  neonHover: '#00E678',
  bg: '#080C09',
  sectionBg: '#0D1A10',
  text: '#C8E6C9',
  textSubtle: '#6B9A7A',
  textMuted: '#7AAB8A',
  textDimmer: '#6B8F7A',
  textDimmest: '#5C8A6E',
  subtitle: '#6B9A7A',
  techBadgeText: '#4DAA6E',
  statusRed: '#EF4444',
  statusRedLight: '#F87171',
  // Medallion pipeline colors
  bronze: '#CD7F32',
  silver: '#9EACB4',
  gold: '#D4AF37',
  ctaBg: '#040C07',
} as const;

// ============================================================================
// CSS Variable Injection
// ============================================================================

/**
 * Inject all theme CSS variables onto :root.
 * Call once in main.tsx before createRoot.
 *
 * Sets both `--var` (hex/color) and `--var-rgb` (comma-separated components)
 * so CSS modules can do `rgba(var(--accent-blue-rgb), 0.1)`.
 */
export function injectCssVars(): void {
  const s = document.documentElement.style;

  // UI palette
  const uiVars: Record<string, string> = {
    'bg-primary': UI.bgPrimary,
    'bg-secondary': UI.bgSecondary,
    'bg-surface': UI.bgSurface,
    'bg-popup': UI.bgPopup,
    'text-primary': UI.textPrimary,
    'text-secondary': UI.textSecondary,
    'text-muted': UI.textMuted,
    'border-color': UI.borderColor,
    'border-subtle': UI.borderSubtle,
    'accent-blue': UI.accentBlue,
    'accent-blue-dark': UI.accentBlueDark,
    'accent-blue-light': UI.accentBlueLight,
    'accent-green': UI.accentGreen,
    'accent-orange': UI.accentOrange,
    'accent-red': UI.accentRed,
    'accent-red-dark': UI.accentRedDark,
    'success-green': UI.successGreen,
    'success-green-dark': UI.successGreenDark,
    'disabled-bg': UI.disabledBg,
  };

  for (const [name, hex] of Object.entries(uiVars)) {
    s.setProperty(`--${name}`, hex);
    s.setProperty(`--${name}-rgb`, rgbToComponents(hexToRgb(hex)));
  }

  // Offline palette
  const offlineVars: Record<string, string> = {
    'offline-neon': OFFLINE.neon,
    'offline-neon-hover': OFFLINE.neonHover,
    'offline-bg': OFFLINE.bg,
    'offline-section-bg': OFFLINE.sectionBg,
    'offline-text': OFFLINE.text,
    'offline-text-subtle': OFFLINE.textSubtle,
    'offline-text-muted': OFFLINE.textMuted,
    'offline-text-dimmer': OFFLINE.textDimmer,
    'offline-text-dimmest': OFFLINE.textDimmest,
    'offline-subtitle': OFFLINE.subtitle,
    'offline-tech-badge-text': OFFLINE.techBadgeText,
    'offline-status-red': OFFLINE.statusRed,
    'offline-status-red-light': OFFLINE.statusRedLight,
    'offline-bronze': OFFLINE.bronze,
    'offline-silver': OFFLINE.silver,
    'offline-gold': OFFLINE.gold,
    'offline-cta-bg': OFFLINE.ctaBg,
  };

  for (const [name, hex] of Object.entries(offlineVars)) {
    s.setProperty(`--${name}`, hex);
    s.setProperty(`--${name}-rgb`, rgbToComponents(hexToRgb(hex)));
  }
}
