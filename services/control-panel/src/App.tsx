import { useState, useMemo, useCallback } from 'react';
import LoginScreen from './components/LoginScreen';
import Map from './components/Map';
import MapErrorBoundary from './components/MapErrorBoundary';
import ControlPanel from './components/ControlPanel';
import LayerControls from './components/LayerControls';
import InspectorPopup, { type InspectedEntity } from './components/InspectorPopup';
import AgentPlacement from './components/AgentPlacement';
import { OfflineMode } from './components/OfflineMode';
import { useApiHealth } from './hooks/useApiHealth';
import { useSimulationState } from './hooks/useSimulationState';
import { useSimulationLayers } from './hooks/useSimulationLayers';
import { useSimulationControl } from './hooks/useSimulationControl';
import { useWebSocket } from './hooks/useWebSocket';
import { useZones } from './hooks/useZones';
import { Toaster } from './lib/toast.ts';
import { PerformanceProvider } from './contexts/PerformanceContext';
import { usePerformanceContext } from './hooks/usePerformanceContext';
import { UI } from './theme';
import type { WebSocketMessage } from './types/websocket';
import type { ZoneData } from './types/api';
import { DEFAULT_VISIBILITY, type LayerVisibility } from './types/layers';
import type { PlacementMode } from './constants/dnaPresets';
import './App.css';

function DisconnectedBanner() {
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        padding: '8px 16px',
        background: UI.accentRed,
        color: 'white',
        textAlign: 'center',
        zIndex: 2000,
        fontSize: '14px',
      }}
    >
      API connection lost. Reconnecting...
    </div>
  );
}

function AppContent() {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const { available, checking } = useApiHealth(apiUrl);
  const [wasEverAvailable, setWasEverAvailable] = useState(false);

  // Latch: once available, stay available (synchronous state update during render)
  if (available && !wasEverAvailable) {
    setWasEverAvailable(true);
  }

  if (!wasEverAvailable) {
    if (checking) {
      return (
        <div className="loading-container">
          <div className="loading-spinner" />
          <p>Checking API availability...</p>
        </div>
      );
    }
    return <OfflineMode />;
  }

  return (
    <>
      {!available && <DisconnectedBanner />}
      <OnlineApp />
    </>
  );
}

function OnlineApp() {
  const [apiKey, setApiKey] = useState<string | null>(() => {
    return sessionStorage.getItem('apiKey');
  });

  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>(DEFAULT_VISIBILITY);
  const [inspectedEntity, setInspectedEntity] = useState<InspectedEntity>(null);
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 });
  const [placementMode, setPlacementMode] = useState<PlacementMode | null>(null);
  const [zoom, setZoom] = useState(11);
  const [destinationSelection, setDestinationSelection] = useState<{
    riderId: string;
    riderName: string;
  } | null>(null);

  const {
    drivers,
    riders,
    trips,
    surge,
    status,
    connected,
    handleMessage,
    handleConnect,
    handleDisconnect,
    setStatus,
  } = useSimulationState();

  const { zones } = useZones();

  const { recordWsMessage } = usePerformanceContext();

  const {
    addPuppetAgent,
    toggleDriverStatus,
    requestRiderTrip,
    // Puppet driver actions
    acceptOffer,
    rejectOffer,
    arriveAtPickup,
    startTrip,
    completeTrip,
    cancelDriverTrip,
    // Puppet rider actions
    cancelRiderTrip,
  } = useSimulationControl(setStatus);

  // Handle placement - create puppet agent at clicked location
  const handlePlacement = useCallback(
    async (lat: number, lng: number) => {
      if (!placementMode) return;

      await addPuppetAgent(placementMode.type, [lat, lng]);
      setPlacementMode(null);
    },
    [placementMode, addPuppetAgent]
  );

  // Handle destination selection for rider trip request
  const handleDestinationSelect = useCallback(
    async (lat: number, lng: number) => {
      if (!destinationSelection) return;

      await requestRiderTrip(destinationSelection.riderId, [lat, lng]);
      setDestinationSelection(null);
    },
    [destinationSelection, requestRiderTrip]
  );

  // Handle request rider trip from popup - enters destination selection mode
  const handleRequestRiderTrip = useCallback((riderId: string, riderName: string) => {
    setDestinationSelection({ riderId, riderName });
  }, []);

  // Cancel destination selection
  const handleCancelDestination = useCallback(() => {
    setDestinationSelection(null);
  }, []);

  // Transform zone features to ZoneData with real-time surge data from WebSocket
  const zoneData: ZoneData[] = useMemo(() => {
    return zones.map((feature) => ({
      feature,
      surge: surge[feature.properties.zone_id] ?? 1.0,
      driver_count: 0,
    }));
  }, [zones, surge]);

  const wsUrl = import.meta.env.VITE_WS_URL;

  useWebSocket({
    url: wsUrl,
    apiKey: apiKey || '',
    onMessage: (data: unknown) => {
      recordWsMessage();
      handleMessage(data as WebSocketMessage);
    },
    onOpen: handleConnect,
    onClose: handleDisconnect,
  });

  const layers = useSimulationLayers({
    drivers,
    riders,
    trips,
    layerVisibility,
    zoneData,
    zoom,
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
      <Toaster position="top-right" />
      {!apiKey ? (
        <>
          <h1>Rideshare Simulation Control Panel</h1>
          <LoginScreen onLogin={handleLogin} />
        </>
      ) : (
        <>
          <MapErrorBoundary>
            <Map
              layers={layers}
              onEntityClick={handleEntityClick}
              placementMode={placementMode}
              onPlacement={handlePlacement}
              destinationMode={!!destinationSelection}
              onDestinationSelect={handleDestinationSelect}
              onZoomChange={setZoom}
            />
          </MapErrorBoundary>
          <AgentPlacement mode={placementMode} onCancel={() => setPlacementMode(null)} />
          {destinationSelection && (
            <div
              style={{
                position: 'fixed',
                top: '20px',
                left: '50%',
                transform: 'translateX(-50%)',
                padding: '12px 24px',
                background: UI.accentBlue,
                color: 'white',
                borderRadius: '8px',
                zIndex: 1001,
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
              }}
            >
              <span>Click on map to select destination for {destinationSelection.riderName}</span>
              <button
                onClick={handleCancelDestination}
                style={{
                  background: 'rgba(255, 255, 255, 0.2)',
                  border: 'none',
                  color: 'white',
                  padding: '6px 12px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                Cancel (ESC)
              </button>
            </div>
          )}
          {status && (
            <ControlPanel
              status={status}
              driverCount={drivers.length}
              riderCount={riders.length}
              tripCount={trips.length}
              onStatusUpdate={setStatus}
              onStartPlacement={setPlacementMode}
            />
          )}
          <LayerControls visibility={layerVisibility} onChange={setLayerVisibility} />
          {inspectedEntity && (
            <InspectorPopup
              entity={inspectedEntity}
              x={popupPosition.x}
              y={popupPosition.y}
              onClose={handleClosePopup}
              onToggleDriverStatus={toggleDriverStatus}
              onRequestRiderTrip={handleRequestRiderTrip}
              // Puppet driver actions
              onAcceptOffer={acceptOffer}
              onRejectOffer={rejectOffer}
              onArriveAtPickup={arriveAtPickup}
              onStartTrip={startTrip}
              onCompleteTrip={completeTrip}
              onCancelDriverTrip={cancelDriverTrip}
              // Puppet rider actions
              onCancelRiderTrip={cancelRiderTrip}
            />
          )}
          {!connected && (
            <div
              style={{
                position: 'fixed',
                top: '20px',
                right: '20px',
                padding: '10px 20px',
                background: UI.accentRed,
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

function App() {
  return (
    <PerformanceProvider>
      <AppContent />
    </PerformanceProvider>
  );
}

export default App;
