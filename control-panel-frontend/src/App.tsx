import { useState } from 'react';
import LoginScreen from './components/LoginScreen';
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
      <h1>Rideshare Simulation Control Panel</h1>
      {!apiKey ? <LoginScreen onLogin={handleLogin} /> : <div>Dashboard placeholder</div>}
    </div>
  );
}

export default App;
