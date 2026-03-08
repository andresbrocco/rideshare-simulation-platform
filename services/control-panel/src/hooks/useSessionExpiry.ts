import { useEffect } from 'react';

/**
 * Listens for the 'session:expired' event dispatched by apiClient when a 401
 * is received. Calls the provided callback so the consuming component can
 * clear its local auth state and show the login dialog.
 */
export function useSessionExpiry(onExpired: () => void): void {
  useEffect(() => {
    const handler = () => onExpired();
    window.addEventListener('session:expired', handler);
    return () => window.removeEventListener('session:expired', handler);
  }, [onExpired]);
}
