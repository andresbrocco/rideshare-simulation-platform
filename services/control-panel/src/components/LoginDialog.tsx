import { useState, useEffect, useRef, useCallback } from 'react';
import { storeSession } from '../utils/auth';
import { visitorLogin, LambdaServiceError } from '../services/lambda';

interface LoginDialogProps {
  open: boolean;
  onClose: () => void;
  onLogin: (apiKey: string) => void;
  onGetAccess?: () => void;
}

interface LoginSuccessResponse {
  api_key: string;
  role: string;
  email: string;
}

function isLoginSuccessResponse(value: unknown): value is LoginSuccessResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Record<string, unknown>).api_key === 'string' &&
    typeof (value as Record<string, unknown>).role === 'string' &&
    typeof (value as Record<string, unknown>).email === 'string'
  );
}

function isValidEmail(value: string): boolean {
  return value.includes('@');
}

export default function LoginDialog({ open, onClose, onLogin, onGetAccess }: LoginDialogProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const isEmailValid = isValidEmail(email);
  const canSubmit = isEmailValid && password.length > 0;

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setEmail('');
      setPassword('');
      setError(null);
      requestAnimationFrame(() => {
        emailRef.current?.focus();
      });
    }
  }, [open]);

  // Escape key closes the dialog
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

  // Focus trap — keep Tab inside the dialog
  const handleDialogKeyDown = useCallback((e: React.KeyboardEvent) => {
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
    if (!canSubmit) return;

    setIsLoading(true);
    setError(null);

    try {
      const lambdaUrl = import.meta.env.VITE_LAMBDA_URL;

      if (lambdaUrl) {
        // Lambda authentication (always available, even when simulation is offline)
        const result = await visitorLogin(email, password);
        storeSession(result.api_key, result.role, result.email);
        onLogin(result.api_key);
        onClose();
      } else {
        // Local dev fallback: authenticate against Simulation API directly
        const response = await fetch(`${import.meta.env.VITE_API_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });

        if (response.status === 401) {
          setError('Invalid email or password');
          return;
        }

        if (!response.ok) {
          setError('Unable to connect to authentication service');
          return;
        }

        const data: unknown = await response.json();

        if (!isLoginSuccessResponse(data)) {
          setError('Unable to connect to authentication service');
          return;
        }

        storeSession(data.api_key, data.role, data.email);
        onLogin(data.api_key);
        onClose();
      }
    } catch (err) {
      if (err instanceof LambdaServiceError) {
        if (err.code === 'LAMBDA_ERROR') {
          setError(err.message);
        } else {
          setError('Unable to connect to authentication service');
        }
      } else {
        setError('Unable to connect to authentication service');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setEmail('');
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
        aria-labelledby="login-dialog-title"
        aria-describedby="login-dialog-desc"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleDialogKeyDown}
      >
        <h2 id="login-dialog-title" className="dialog-title">
          Sign In
        </h2>
        <p id="login-dialog-desc" className="dialog-label">
          {onGetAccess ? (
            <>
              Enter your credentials (
              <button type="button" className="dialog-inline-link" onClick={onGetAccess}>
                get them for free here
              </button>
              ).
            </>
          ) : (
            'Enter your credentials to access the control panel.'
          )}
        </p>
        <form onSubmit={handleSubmit}>
          <div className="dialog-form-group">
            <label htmlFor="login-email-input" className="dialog-label">
              Email
            </label>
            <input
              ref={emailRef}
              id="login-email-input"
              type="email"
              className="dialog-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </div>
          <div className="dialog-form-group">
            <label htmlFor="login-password-input" className="dialog-label">
              Password
            </label>
            <input
              id="login-password-input"
              type="password"
              className="dialog-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
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
              disabled={!canSubmit || isLoading}
            >
              {isLoading ? 'Connecting...' : 'Sign In'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
