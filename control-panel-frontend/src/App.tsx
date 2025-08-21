import { useState } from 'react';
import './App.css';

function App() {
  const [apiKey] = useState<string | null>(sessionStorage.getItem('api_key'));

  return (
    <div className="App">
      <h1>Rideshare Simulation Control Panel</h1>
      {!apiKey ? <div>Login screen placeholder</div> : <div>Dashboard placeholder</div>}
    </div>
  );
}

export default App;
