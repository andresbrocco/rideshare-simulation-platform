import { useState } from 'react';
import { useSimulationControl } from '../hooks/useSimulationControl';
import StatsPanel from './StatsPanel';
import Tooltip from './Tooltip';
import type { SimulationStatus } from '../types/api';
import styles from './ControlPanel.module.css';

interface ControlPanelProps {
  status: SimulationStatus;
  driverCount?: number;
  riderCount?: number;
  tripCount?: number;
  onStatusUpdate?: (status: SimulationStatus) => void;
}

export default function ControlPanel({
  status,
  driverCount: realTimeDriverCount,
  riderCount: realTimeRiderCount,
  tripCount: realTimeTripCount,
  onStatusUpdate,
}: ControlPanelProps) {
  const [driverCount, setDriverCount] = useState(10);
  const [riderCount, setRiderCount] = useState(5);

  const { startSimulation, pauseSimulation, resetSimulation, setSpeed, addDrivers, addRiders } =
    useSimulationControl(onStatusUpdate);

  const isRunning = status.state === 'running';

  const handleSpeedChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const multiplier = parseInt(e.target.value);
    await setSpeed(multiplier);
  };

  const handleAddDrivers = async () => {
    await addDrivers(driverCount);
  };

  const handleAddRiders = async () => {
    await addRiders(riderCount);
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
          <span className={styles.label}>Current Time:</span>
          <span className={styles.value}>{new Date(status.current_time).toLocaleString()}</span>
        </div>
      </div>

      <div className={styles.section}>
        <h3>Controls</h3>
        <div className={styles.buttonGroup}>
          <Tooltip text="Start or resume the simulation">
            <button onClick={startSimulation} disabled={isRunning} className={styles.button}>
              Play
            </button>
          </Tooltip>
          <Tooltip text="Pause simulation (in-flight trips complete first)">
            <button onClick={pauseSimulation} disabled={!isRunning} className={styles.button}>
              Pause
            </button>
          </Tooltip>
          <Tooltip text="Stop and reset to initial state">
            <button onClick={resetSimulation} className={styles.button}>
              Reset
            </button>
          </Tooltip>
        </div>
      </div>

      <div className={styles.section}>
        <label htmlFor="speed-select" className={styles.label}>
          Speed:
        </label>
        <Tooltip text="Control simulation time speed (1x = real-time)">
          <select
            id="speed-select"
            value={status.speed_multiplier}
            onChange={handleSpeedChange}
            className={styles.select}
          >
            <option value="1">1x</option>
            <option value="10">10x</option>
            <option value="100">100x</option>
          </select>
        </Tooltip>
      </div>

      <div className={styles.section}>
        <h3>Add Agents</h3>
        <div className={styles.agentControl}>
          <label htmlFor="driver-count" className={styles.label}>
            Drivers:
          </label>
          <input
            id="driver-count"
            type="number"
            value={driverCount}
            onChange={(e) => setDriverCount(parseInt(e.target.value) || 0)}
            min="1"
            className={styles.input}
          />
          <button onClick={handleAddDrivers} className={styles.button}>
            Add Drivers
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
            onChange={(e) => setRiderCount(parseInt(e.target.value) || 0)}
            min="1"
            className={styles.input}
          />
          <button onClick={handleAddRiders} className={styles.button}>
            Add Riders
          </button>
        </div>
      </div>

      <StatsPanel
        status={status}
        driverCount={realTimeDriverCount}
        riderCount={realTimeRiderCount}
        tripCount={realTimeTripCount}
      />
    </div>
  );
}
