// ============================================================================
// Phase definitions and pure functions for the trip lifecycle animation
// ============================================================================

export type Phase =
  | 'idle'
  | 'driver_online'
  | 'rider_request'
  | 'match'
  | 'pickup_drive'
  | 'pickup'
  | 'trip_drive'
  | 'completed'
  | 'hold'
  | 'reset';

interface PhaseConfig {
  phase: Phase;
  duration: number;
}

export const PHASES: PhaseConfig[] = [
  { phase: 'idle', duration: 1.0 },
  { phase: 'driver_online', duration: 1.0 },
  { phase: 'rider_request', duration: 1.5 },
  { phase: 'match', duration: 0.5 },
  { phase: 'pickup_drive', duration: 2.0 },
  { phase: 'pickup', duration: 0.5 },
  { phase: 'trip_drive', duration: 2.5 },
  { phase: 'completed', duration: 1.5 },
  { phase: 'hold', duration: 2.0 },
  { phase: 'reset', duration: 0.5 },
];

export const TOTAL_CYCLE_DURATION = PHASES.reduce((sum, p) => sum + p.duration, 0);

export interface PhaseState {
  phase: Phase;
  progress: number;
}

export function resolvePhase(cycleTime: number): PhaseState {
  const t = ((cycleTime % TOTAL_CYCLE_DURATION) + TOTAL_CYCLE_DURATION) % TOTAL_CYCLE_DURATION;
  let elapsed = 0;
  for (const config of PHASES) {
    if (t < elapsed + config.duration) {
      return { phase: config.phase, progress: (t - elapsed) / config.duration };
    }
    elapsed += config.duration;
  }
  return { phase: 'reset', progress: 1 };
}
