import type { SimulationStatus } from '../types/api';

interface StatsPanelProps {
  status: SimulationStatus | null;
}

export default function StatsPanel({ status }: StatsPanelProps) {
  if (!status) {
    return <div>Loading...</div>;
  }

  return (
    <div style={{ padding: '20px', background: '#fff', borderRadius: '8px' }}>
      <h3>Simulation Stats</h3>
      <div style={{ marginTop: '16px' }}>
        <StatRow label="State" value={status.state} />
        <StatRow label="Speed" value={`${status.speed_multiplier}x`} />
        <StatRow label="Drivers" value={status.drivers_count} />
        <StatRow label="Riders" value={status.riders_count} />
        <StatRow label="Active Trips" value={status.active_trips_count} />
        <StatRow label="Uptime" value={`${Math.floor(status.uptime_seconds / 60)}m`} />
      </div>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
      <span style={{ fontWeight: 500 }}>{label}:</span>
      <span>{value}</span>
    </div>
  );
}
