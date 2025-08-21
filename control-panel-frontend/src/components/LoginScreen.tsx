import { useState } from 'react';

interface LoginScreenProps {
  onLogin: (apiKey: string) => void;
}

export default function LoginScreen({ onLogin }: LoginScreenProps) {
  const [apiKey, setApiKey] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (apiKey.trim()) {
      onLogin(apiKey);
    }
  };

  return (
    <div style={{ maxWidth: '400px', margin: '100px auto', padding: '20px' }}>
      <h2>Login</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '16px' }}>
          <label htmlFor="apiKey" style={{ display: 'block', marginBottom: '8px' }}>
            API Key
          </label>
          <input
            id="apiKey"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter your API key"
            style={{ width: '100%', padding: '8px', fontSize: '16px' }}
          />
        </div>
        <button type="submit" style={{ width: '100%', padding: '10px', fontSize: '16px' }}>
          Login
        </button>
      </form>
    </div>
  );
}
