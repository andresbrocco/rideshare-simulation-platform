import { createContext } from 'react';
import type { FrontendMetrics } from '../types/api';

export interface PerformanceContextType {
  frontendMetrics: FrontendMetrics;
  recordWsMessage: () => void;
}

export const PerformanceContext = createContext<PerformanceContextType | null>(null);
