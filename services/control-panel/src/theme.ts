/**
 * Centralized theme — single source of truth for every color in the frontend.
 *
 * Four regions:
 *   1. Stage colors (trip lifecycle)  — deck.gl layers, legends, controls
 *   2. Unified palette (4 hues + neutral) — PALETTE, NEUTRAL, GREEN, BLUE, AMBER, RED
 *   3. UI palette                     — CSS variables for control panel components
 *   4. Offline palette                — CSS variables for landing/demo page
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
// Region 2 — Unified Palette (4 hues + neutral)
// ============================================================================

/** 13-step neutral scale from near-black (950) to near-white (50) */
export const NEUTRAL: Record<number, string> = {
  950: '#0A0C0B',
  900: '#131716',
  800: '#1C2120',
  700: '#2A2F2E',
  600: '#3B413F',
  500: '#4E5553',
  400: '#6B7371',
  300: '#949B99',
  200: '#C5CAC8',
  150: '#D8DCDB',
  100: '#E8ECEA',
  75: '#EFF2F1',
  50: '#F5F7F6',
};

/** Brand green scale — headings, CTAs, brand accent */
export const GREEN: Record<number, string> = {
  500: '#00FF88',
  400: '#33FFA0',
  300: '#66FFB8',
  200: '#99FFD0',
  100: '#CCFFE8',
};

/** Interactive blue scale — buttons, links, in-transit stage */
export const BLUE: Record<number, string> = {
  600: '#2563EB',
  500: '#3B82F6',
  400: '#60A5FA',
};

/** Warning amber scale — warnings, pickup stage, pending */
export const AMBER: Record<number, string> = {
  500: '#F59E0B',
  400: '#FBBF24',
};

/** Danger red scale — errors, cancelled states, destructive actions */
export const RED: Record<number, string> = {
  600: '#DC2626',
  500: '#EF4444',
  400: '#F87171',
};

/** Success green (distinct from brand green) */
export const SUCCESS: Record<number, string> = {
  600: '#16A34A',
  500: '#22C55E',
};

/** Medallion pipeline colors (semantic, unchanged) */
export const MEDALLION = {
  bronze: '#CD7F32',
  silver: '#9EACB4',
  gold: '#D4AF37',
} as const;

/** Map layer colors */
export const MAP = {
  zoneStroke: '#FFFFFF',
  surgeLabel: '#FFFF00',
} as const;

/** Composite palette export */
export const PALETTE = {
  neutral: NEUTRAL,
  green: GREEN,
  blue: BLUE,
  amber: AMBER,
  red: RED,
  success: SUCCESS,
  medallion: MEDALLION,
  map: MAP,
} as const;

// ============================================================================
// Region 3 — UI Palette
// ============================================================================

export const UI = {
  // Backgrounds (derived from neutral scale)
  bgPrimary: NEUTRAL[800],
  bgSecondary: NEUTRAL[800],
  bgSurface: NEUTRAL[700],
  bgPopup: NEUTRAL[800],

  // Text (derived from neutral scale)
  textPrimary: NEUTRAL[200],
  textSecondary: NEUTRAL[300],
  textMuted: NEUTRAL[400],

  // Borders (derived from neutral scale)
  borderColor: NEUTRAL[600],
  borderSubtle: NEUTRAL[500],

  // Accents (derived from hue scales)
  accentBlue: BLUE[500],
  accentBlueDark: BLUE[600],
  accentBlueLight: BLUE[400],
  accentGreen: '#10B981',
  accentOrange: AMBER[500],
  accentRed: RED[500],
  accentRedDark: RED[600],

  // Status / functional
  successGreen: SUCCESS[500],
  successGreenDark: SUCCESS[600],
  disabledBg: NEUTRAL[400],
} as const;

// ============================================================================
// Region 4 — Offline Palette
// ============================================================================

export const OFFLINE = {
  neon: GREEN[500],
  neonHover: GREEN[400],
  bg: NEUTRAL[950],
  sectionBg: NEUTRAL[900],
  text: NEUTRAL[200],
  textSubtle: NEUTRAL[300],
  textMuted: NEUTRAL[300],
  textDimmer: NEUTRAL[300],
  textDimmest: NEUTRAL[400],
  subtitle: NEUTRAL[300],
  techBadgeText: '#4DAA6E',
  statusRed: RED[500],
  statusRedLight: RED[400],
  // Medallion pipeline colors
  bronze: MEDALLION.bronze,
  silver: MEDALLION.silver,
  gold: MEDALLION.gold,
  ctaBg: NEUTRAL[950],
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

  // Palette-derived variables
  const paletteVars: Record<string, string> = {
    'text-emphasis': NEUTRAL[50],
    'text-emphasis-rgb': rgbToComponents(hexToRgb(NEUTRAL[50])),
    'neutral-950': NEUTRAL[950],
    'neutral-950-rgb': rgbToComponents(hexToRgb(NEUTRAL[950])),
    'brand-green': GREEN[500],
    'brand-green-hover': GREEN[400],
    'brand-green-subtle': GREEN[200],
    'accent-amber': AMBER[500],
    'accent-amber-light': AMBER[400],
  };

  for (const [name, value] of Object.entries(paletteVars)) {
    s.setProperty(`--${name}`, value);
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
