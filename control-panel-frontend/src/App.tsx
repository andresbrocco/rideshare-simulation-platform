import { useState } from 'react';
import LoginScreen from './components/LoginScreen';
import Map from './components/Map';
import './App.css';

function App() {
  const [apiKey, setApiKey] = useState<string | null>(() => {
    return sessionStorage.getItem('apiKey');
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
        <Map layers={[]} />
      )}
    </div>
  );
}

export default App;
