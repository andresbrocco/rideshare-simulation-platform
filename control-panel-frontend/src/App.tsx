import { useState } from 'react';
import LoginScreen from './components/LoginScreen';
import Map from './components/Map';
import ControlPanel from './components/ControlPanel';
import { useSimulationState } from './hooks/useSimulationState';
import { useSimulationLayers } from './hooks/useSimulationLayers';
import { useWebSocket } from './hooks/useWebSocket';
import type { WebSocketMessage } from './types/websocket';
import './App.css';

function App() {
  const [apiKey, setApiKey] = useState<string | null>(() => {
    return sessionStorage.getItem('apiKey');
  });

  const {
    drivers,
    riders,
    trips,
    status,
    gpsTrails,
    connected,
    handleMessage,
    handleConnect,
    handleDisconnect,
  } = useSimulationState();

  const wsUrl = import.meta.env.VITE_WS_URL;

  useWebSocket({
    url: wsUrl,
    apiKey: apiKey || '',
    onMessage: (data: unknown) => handleMessage(data as WebSocketMessage),
    onOpen: handleConnect,
    onClose: handleDisconnect,
  });

  const layers = useSimulationLayers({
    drivers,
    riders,
    trips,
    trails: gpsTrails,
    currentTime: status?.uptime_seconds || 0,
  });

  const handleLogin = (key: string) => {
    setApiKey(key);
    sessionStorage.setItem('apiKey', key);
  };

  return (
    <div className="App">
      {!apiKey ? (
        <>
          <h1>Rideshare Simulation Control Panel</h1>
          <LoginScreen onLogin={handleLogin} />
        </>
      ) : (
        <>
          <Map layers={layers} />
          {status && <ControlPanel status={status} />}
          {!connected && (
            <div
              style={{
                position: 'fixed',
                top: '20px',
                right: '20px',
                padding: '10px 20px',
                background: '#f44336',
                color: 'white',
                borderRadius: '4px',
                zIndex: 1000,
              }}
            >
              Connection lost. Reconnecting...
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default App;
