import { useContext } from 'react';
import { PerformanceContext } from '../contexts/performanceContextDef';
import type { PerformanceContextType } from '../contexts/performanceContextDef';

export function usePerformanceContext(): PerformanceContextType {
  const context = useContext(PerformanceContext);
  if (!context) {
    throw new Error('usePerformanceContext must be used within a PerformanceProvider');
  }
  return context;
}
