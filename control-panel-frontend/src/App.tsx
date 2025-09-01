import { useState, useMemo } from 'react';
import LoginScreen from './components/LoginScreen';
import Map from './components/Map';
import MapErrorBoundary from './components/MapErrorBoundary';
import ControlPanel from './components/ControlPanel';
import LayerControls from './components/LayerControls';
import InspectorPopup, { type InspectedEntity } from './components/InspectorPopup';
import { useSimulationState } from './hooks/useSimulationState';
import { useSimulationLayers } from './hooks/useSimulationLayers';
import { useWebSocket } from './hooks/useWebSocket';
import { useZones } from './hooks/useZones';
import type { WebSocketMessage } from './types/websocket';
import type { ZoneData } from './types/api';
import { DEFAULT_VISIBILITY, type LayerVisibility } from './types/layers';
import './App.css';

function App() {
  const [apiKey, setApiKey] = useState<string | null>(() => {
    return sessionStorage.getItem('apiKey');
  });

  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>(DEFAULT_VISIBILITY);
  const [inspectedEntity, setInspectedEntity] = useState<InspectedEntity>(null);
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 });

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
    setStatus,
  } = useSimulationState();

  const { zones } = useZones();

  // Transform zone features to ZoneData with default values
  // Real-time surge data would come from WebSocket updates
  const zoneData: ZoneData[] = useMemo(() => {
    return zones.map((feature) => ({
      feature,
      surge: 1.0,
      driver_count: 0,
    }));
  }, [zones]);

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
    layerVisibility,
    zoneData,
  });

  const handleLogin = (key: string) => {
    setApiKey(key);
    sessionStorage.setItem('apiKey', key);
  };

  const handleEntityClick = (entity: InspectedEntity, x: number, y: number) => {
    setInspectedEntity(entity);
    setPopupPosition({ x, y });
  };

  const handleClosePopup = () => {
    setInspectedEntity(null);
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
          <MapErrorBoundary>
            <Map layers={layers} onEntityClick={handleEntityClick} />
          </MapErrorBoundary>
          {status && (
            <ControlPanel
              status={status}
              driverCount={drivers.length}
              riderCount={riders.length}
              tripCount={trips.length}
              onStatusUpdate={setStatus}
            />
          )}
          <LayerControls visibility={layerVisibility} onChange={setLayerVisibility} />
          {inspectedEntity && (
            <InspectorPopup
              entity={inspectedEntity}
              x={popupPosition.x}
              y={popupPosition.y}
              onClose={handleClosePopup}
            />
          )}
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
