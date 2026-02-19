import { useState } from 'react';
import { UI } from '../theme';

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
      const response = await fetch(`${import.meta.env.VITE_API_URL}/auth/validate`, {
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
    <div
      style={{
        maxWidth: '400px',
        margin: '100px auto',
        padding: '24px',
        background: 'var(--bg-secondary)',
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
      }}
    >
      <h2 style={{ color: 'var(--text-primary)', marginBottom: '24px' }}>Login</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '16px' }}>
          <label
            htmlFor="apiKey"
            style={{
              display: 'block',
              marginBottom: '8px',
              color: 'var(--text-secondary)',
              fontSize: '14px',
            }}
          >
            API Key
          </label>
          <input
            id="apiKey"
            type="password"
            value={apiKey}
            onChange={handleInputChange}
            placeholder="Enter API Key"
            style={{
              width: '100%',
              padding: '10px',
              fontSize: '16px',
              background: 'var(--bg-surface)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '4px',
            }}
          />
        </div>
        {error && (
          <div
            style={{
              color: 'var(--accent-red)',
              marginBottom: '16px',
              fontSize: '14px',
              padding: '8px',
              background: `${UI.accentRed}1a`,
              borderRadius: '4px',
            }}
          >
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={!apiKey.trim() || isLoading}
          style={{
            width: '100%',
            padding: '12px',
            fontSize: '16px',
            cursor: !apiKey.trim() || isLoading ? 'not-allowed' : 'pointer',
            background: !apiKey.trim() || isLoading ? UI.disabledBg : UI.accentBlue,
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontWeight: '500',
          }}
        >
          {isLoading ? 'Connecting...' : 'Connect'}
        </button>
      </form>
    </div>
  );
}
