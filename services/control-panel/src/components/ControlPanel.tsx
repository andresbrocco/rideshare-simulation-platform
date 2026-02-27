import { useState } from 'react';
import { useSimulationControl } from '../hooks/useSimulationControl';
import { useMetrics } from '../hooks/useMetrics';
import { useInfrastructure } from '../hooks/useInfrastructure';
import { usePerformanceMetrics } from '../hooks/usePerformanceMetrics';
import { usePerformanceContext } from '../hooks/usePerformanceContext';
import { usePerformanceController } from '../hooks/usePerformanceController';
import StatsPanel from './StatsPanel';
import InfrastructurePanel from './InfrastructurePanel';
import PerformancePanel from './PerformancePanel';
import Tooltip from './Tooltip';
import ConfirmModal from './ConfirmModal';
import type { SimulationStatus, SpawnMode } from '../types/api';
import type { PlacementMode } from '../constants/dnaPresets';
import { formatDuration } from '../utils/formatDuration';
import styles from './ControlPanel.module.css';

interface ControlPanelProps {
  status: SimulationStatus;
  driverCount?: number;
  riderCount?: number;
  tripCount?: number;
  onStatusUpdate?: (status: SimulationStatus) => void;
  onStartPlacement?: (mode: PlacementMode) => void;
}

export default function ControlPanel({
  status,
  driverCount: realTimeDriverCount,
  riderCount: realTimeRiderCount,
  tripCount: realTimeTripCount,
  onStatusUpdate,
  onStartPlacement,
}: ControlPanelProps) {
  const [driverCount, setDriverCount] = useState(50);
  const [riderCount, setRiderCount] = useState(50);
  const [driverMode, setDriverMode] = useState<SpawnMode>('immediate');
  const [riderMode, setRiderMode] = useState<SpawnMode>('immediate');
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const {
    startSimulation,
    pauseSimulation,
    resumeSimulation,
    resetSimulation,
    setSpeed,
    addDrivers,
    addRiders,
  } = useSimulationControl(onStatusUpdate);

  const { driverMetrics, tripMetrics, overviewMetrics, riderMetrics } = useMetrics();
  const {
    data: infraData,
    loading: infraLoading,
    error: infraError,
    refresh: refreshInfra,
  } = useInfrastructure();
  const {
    metrics: perfMetrics,
    loading: perfLoading,
    error: perfError,
    refresh: refreshPerf,
  } = usePerformanceMetrics();
  const { frontendMetrics } = usePerformanceContext();
  const { status: controllerStatus, setMode: setControllerMode } = usePerformanceController();

  const isRunning = status.state === 'running';
  const isAutoMode = controllerStatus !== null && controllerStatus.mode === 'on';

  const handleSpeedChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const multiplier = parseFloat(e.target.value);
    await setSpeed(multiplier);
  };

  const handleAddDrivers = async () => {
    await addDrivers(driverCount, driverMode);
  };

  const handleAddRiders = async () => {
    await addRiders(riderCount, riderMode);
  };

  const getStatusColor = () => {
    switch (status.state) {
      case 'running':
        return styles.statusRunning;
      case 'paused':
        return styles.statusPaused;
      case 'draining':
        return styles.statusPaused;
      default:
        return styles.statusStopped;
    }
  };

  const getStatusTooltip = () => {
    switch (status.state) {
      case 'running':
        return 'Simulation is actively running';
      case 'paused':
        return 'Simulation is paused';
      case 'draining':
        return 'Completing in-flight trips before pause';
      case 'stopped':
        return 'Simulation is stopped';
      default:
        return 'Simulation status';
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>Simulation Control</h2>
        <Tooltip text={getStatusTooltip()}>
          <div className={`${styles.statusBadge} ${getStatusColor()}`}>{status.state}</div>
        </Tooltip>
      </div>

      <div className={styles.section}>
        <div className={styles.timeDisplay}>
          <div className={styles.timeGroup}>
            <span className={styles.label}>Current Time:</span>
            <span className={styles.value}>{new Date(status.current_time).toLocaleString()}</span>
          </div>
          <div className={styles.timeGroupRight}>
            <span className={styles.label}>Elapsed:</span>
            <span className={styles.value}>{formatDuration(status.uptime_seconds)}</span>
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <h3>Controls</h3>
        <div className={styles.buttonGroup}>
          {status.state === 'paused' ? (
            <Tooltip text="Resume the paused simulation">
              <button onClick={resumeSimulation} className={styles.button}>
                Resume
              </button>
            </Tooltip>
          ) : (
            <Tooltip text="Start the simulation">
              <button onClick={startSimulation} disabled={isRunning} className={styles.button}>
                Play
              </button>
            </Tooltip>
          )}
          <Tooltip text="Pause simulation (in-flight trips complete first)">
            <button onClick={pauseSimulation} disabled={!isRunning} className={styles.button}>
              Pause
            </button>
          </Tooltip>
          <Tooltip text="Stop and reset to initial state">
            <button onClick={() => setShowResetConfirm(true)} className={styles.button}>
              Reset
            </button>
          </Tooltip>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.speedHeader}>
          <label htmlFor="speed-select" className={styles.label}>
            Speed:
          </label>
          {controllerStatus !== null && (
            <Tooltip text={'Control simulation speed to work\nnear the performance limits'}>
              <label className={styles.toggleLabel}>
                <input
                  type="checkbox"
                  className={styles.toggleInput}
                  checked={controllerStatus.mode === 'on'}
                  onChange={(e) => setControllerMode(e.target.checked ? 'on' : 'off')}
                />
                <span className={styles.toggleSwitch} />
                <span className={styles.toggleText}>Auto</span>
              </label>
            </Tooltip>
          )}
        </div>
        {isAutoMode ? (
          <div className={styles.autoSpeedInfo}>
            <span className={styles.autoSpeedValue}>
              {controllerStatus.current_speed.toFixed(1)}x
            </span>
            <span className={styles.autoSpeedManaged}>Managed by performance controller</span>
          </div>
        ) : (
          <Tooltip text="Control simulation time speed (1x = real-time)">
            <select
              id="speed-select"
              value={status.speed_multiplier}
              onChange={handleSpeedChange}
              className={styles.select}
            >
              <option value="0.125">⅛x</option>
              <option value="0.25">¼x</option>
              <option value="0.5">½x</option>
              <option value="1">1x</option>
              <option value="2">2x</option>
              <option value="4">4x</option>
              <option value="8">8x</option>
              <option value="16">16x</option>
              <option value="32">32x</option>
            </select>
          </Tooltip>
        )}
      </div>

      <div className={styles.section}>
        <h3>Add Autonomous Agents</h3>
        <div className={styles.agentControl}>
          <label htmlFor="driver-count" className={styles.label}>
            Drivers:
          </label>
          <input
            id="driver-count"
            type="number"
            value={driverCount}
            onChange={(e) => setDriverCount(Math.min(100, parseInt(e.target.value) || 0))}
            onBlur={() => setDriverCount((v) => Math.max(1, v))}
            min="1"
            max="100"
            className={styles.input}
          />
          <Tooltip text="Immediate: go online immediately. Scheduled: follow shift schedule from DNA.">
            <select
              id="driver-mode"
              value={driverMode}
              onChange={(e) => setDriverMode(e.target.value as SpawnMode)}
              className={styles.select}
            >
              <option value="immediate">Immediate</option>
              <option value="scheduled">Scheduled</option>
            </select>
          </Tooltip>
          <button onClick={handleAddDrivers} className={styles.button}>
            Add
          </button>
        </div>
        <div className={styles.agentControl}>
          <label htmlFor="rider-count" className={styles.label}>
            Riders:
          </label>
          <input
            id="rider-count"
            type="number"
            value={riderCount}
            onChange={(e) => setRiderCount(Math.min(2000, parseInt(e.target.value) || 0))}
            onBlur={() => setRiderCount((v) => Math.max(1, v))}
            min="1"
            max="2000"
            className={styles.input}
          />
          <Tooltip text="Immediate: request trip now. Scheduled: follow ride frequency from DNA.">
            <select
              id="rider-mode"
              value={riderMode}
              onChange={(e) => setRiderMode(e.target.value as SpawnMode)}
              className={styles.select}
            >
              <option value="immediate">Immediate</option>
              <option value="scheduled">Scheduled</option>
            </select>
          </Tooltip>
          <button onClick={handleAddRiders} className={styles.button}>
            Add
          </button>
        </div>
      </div>

      {onStartPlacement && (
        <div className={styles.section}>
          <h3>Add Puppet Agent</h3>
          <div className={styles.puppetButtons}>
            <Tooltip text="Create a puppet driver that you control manually">
              <button
                className={styles.button}
                onClick={() => onStartPlacement({ type: 'driver' })}
              >
                Add Puppet Driver
              </button>
            </Tooltip>
            <Tooltip text="Create a puppet rider that you control manually">
              <button className={styles.button} onClick={() => onStartPlacement({ type: 'rider' })}>
                Add Puppet Rider
              </button>
            </Tooltip>
          </div>
        </div>
      )}

      <StatsPanel
        status={status}
        driverCount={realTimeDriverCount}
        riderCount={realTimeRiderCount}
        tripCount={realTimeTripCount}
        driverMetrics={driverMetrics}
        tripMetrics={tripMetrics}
        overviewMetrics={overviewMetrics}
        riderMetrics={riderMetrics}
      />

      <InfrastructurePanel
        data={infraData}
        loading={infraLoading}
        error={infraError}
        onRefresh={refreshInfra}
        simulationRealTimeRatio={status.real_time_ratio}
        performanceIndex={controllerStatus?.performance_index ?? null}
      />

      <PerformancePanel
        metrics={perfMetrics}
        frontendMetrics={frontendMetrics}
        loading={perfLoading}
        error={perfError}
        onRefresh={refreshPerf}
      />

      <ConfirmModal
        isOpen={showResetConfirm}
        title="Reset Simulation?"
        message="This will clear ALL simulation data including agents, trips, and route cache. This action cannot be undone."
        confirmText="Reset Everything"
        cancelText="Cancel"
        variant="danger"
        onConfirm={() => {
          setShowResetConfirm(false);
          resetSimulation();
        }}
        onCancel={() => setShowResetConfirm(false)}
      />
    </div>
  );
}
