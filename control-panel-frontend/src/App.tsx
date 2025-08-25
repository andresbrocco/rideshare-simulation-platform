import { useState } from 'react';
import LoginScreen from './components/LoginScreen';
import Map from './components/Map';
import { useSimulationState } from './hooks/useSimulationState';
import { useSimulationLayers } from './hooks/useSimulationLayers';
import './App.css';

function App() {
  const [apiKey, setApiKey] = useState<string | null>(() => {
    return sessionStorage.getItem('apiKey');
  });

  const { drivers, riders, trips } = useSimulationState();

  const layers = useSimulationLayers({
    drivers,
    riders,
    trips,
    trails: [],
    currentTime: 0,
  });

  const handleLogin = (key: string) => {
    setApiKey(key);
  };

  return (
    <div className="App">
      {!apiKey ? (
        <>
          <h1>Rideshare Simulation Control Panel</h1>
          <LoginScreen onLogin={handleLogin} />
        </>
      ) : (
        <Map layers={layers} />
      )}
    </div>
  );
}

export default App;
