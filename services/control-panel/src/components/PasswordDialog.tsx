import { useState, useEffect, useRef, useCallback } from 'react';
import { validateApiKey, LambdaServiceError } from '../services/lambda';

interface PasswordDialogProps {
  open: boolean;
  onClose: () => void;
  onLogin: (apiKey: string) => void;
}

export default function PasswordDialog({ open, onClose, onLogin }: PasswordDialogProps) {
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (open) {
      setPassword('');
      setError(null);
      // Focus input on next frame after render
      requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
    }
  }, [open]);

  // Escape key handler
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  // Focus trap
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== 'Tab' || !dialogRef.current) return;

    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
      'input, button:not(:disabled), [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const lambdaUrl = import.meta.env.VITE_LAMBDA_URL;

      if (lambdaUrl) {
        // Lambda validation (always available, even when simulation is offline)
        const result = await validateApiKey(password);

        if (result.valid) {
          sessionStorage.setItem('apiKey', password);
          onLogin(password);
          onClose();
        } else {
          setError(result.error || 'Invalid password. Please check and try again.');
        }
      } else {
        // Fallback: simulation API validation (local dev without Lambda)
        const response = await fetch(`${import.meta.env.VITE_API_URL}/auth/validate`, {
          headers: { 'X-API-Key': password },
        });

        if (response.ok) {
          sessionStorage.setItem('apiKey', password);
          onLogin(password);
          onClose();
        } else {
          setError('Invalid password. Please check and try again.');
        }
      }
    } catch (err) {
      if (err instanceof LambdaServiceError) {
        switch (err.code) {
          case 'NETWORK_ERROR':
            setError('Authentication service unavailable. Please try again.');
            break;
          case 'INVALID_RESPONSE':
            setError('Authentication error. Please contact support.');
            break;
          case 'LAMBDA_ERROR':
            setError('Authentication failed. Please try again.');
            break;
        }
      } else {
        setError('Failed to connect to the server. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setPassword('');
    setError(null);
    onClose();
  };

  if (!open) return null;

  return (
    <div className="dialog-overlay" onClick={handleClose}>
      <div
        className="dialog-content"
        ref={dialogRef}
        role="dialog"
        aria-labelledby="password-dialog-title"
        aria-describedby="password-dialog-desc"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <h2 id="password-dialog-title" className="dialog-title">
          Enter Password
        </h2>
        <p id="password-dialog-desc" className="dialog-label">
          Enter the password to access the control panel.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="dialog-form-group">
            <label htmlFor="password-input" className="dialog-label">
              Password
            </label>
            <input
              ref={inputRef}
              id="password-input"
              type="password"
              className="dialog-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              autoComplete="current-password"
            />
          </div>
          {error && <div className="dialog-error">{error}</div>}
          <div className="dialog-buttons">
            <button
              type="button"
              className="dialog-button-secondary"
              onClick={handleClose}
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="dialog-button-primary"
              disabled={!password.trim() || isLoading}
            >
              {isLoading ? 'Connecting...' : 'Connect'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
