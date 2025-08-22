import { useState } from 'react';

interface LoginScreenProps {
  onLogin: (apiKey: string) => void;
}

export default function LoginScreen({ onLogin }: LoginScreenProps) {
  const [apiKey, setApiKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/health`, {
        headers: { 'X-API-Key': apiKey },
      });

      if (response.ok) {
        sessionStorage.setItem('apiKey', apiKey);
        onLogin(apiKey);
      } else {
        setError('Invalid API key. Please check and try again.');
      }
    } catch {
      setError('Failed to connect to the server. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setApiKey(e.target.value);
    if (error) setError(null);
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
            onChange={handleInputChange}
            placeholder="Enter API Key"
            style={{ width: '100%', padding: '8px', fontSize: '16px' }}
          />
        </div>
        {error && (
          <div style={{ color: 'red', marginBottom: '16px', fontSize: '14px' }}>{error}</div>
        )}
        <button
          type="submit"
          disabled={!apiKey.trim() || isLoading}
          style={{
            width: '100%',
            padding: '10px',
            fontSize: '16px',
            cursor: !apiKey.trim() || isLoading ? 'not-allowed' : 'pointer',
            opacity: !apiKey.trim() || isLoading ? 0.6 : 1,
          }}
        >
          {isLoading ? 'Connecting...' : 'Connect'}
        </button>
      </form>
    </div>
  );
}
