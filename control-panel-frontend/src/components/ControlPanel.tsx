interface ControlPanelProps {
  onStart: () => void;
  onPause: () => void;
  onStop: () => void;
  isRunning: boolean;
}

export default function ControlPanel({ onStart, onPause, onStop, isRunning }: ControlPanelProps) {
  return (
    <div style={{ padding: '20px', background: '#f5f5f5', borderRadius: '8px' }}>
      <h3>Simulation Controls</h3>
      <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
        <button onClick={onStart} disabled={isRunning} style={{ padding: '10px 20px' }}>
          Start
        </button>
        <button onClick={onPause} disabled={!isRunning} style={{ padding: '10px 20px' }}>
          Pause
        </button>
        <button onClick={onStop} style={{ padding: '10px 20px' }}>
          Stop
        </button>
      </div>
    </div>
  );
}
