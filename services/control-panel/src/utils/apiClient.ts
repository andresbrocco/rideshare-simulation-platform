import { getApiKey, clearSession } from './auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Thin fetch wrapper that:
 * - Injects the X-API-Key header from sessionStorage on every request.
 * - On a 401 response, clears the session and dispatches a custom
 *   'session:expired' event so the app can redirect to the login screen.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const apiKey = getApiKey();

  const headers = new Headers(init.headers);
  if (apiKey) {
    headers.set('X-API-Key', apiKey);
  }

  const response = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (response.status === 401) {
    clearSession();
    window.dispatchEvent(new Event('session:expired'));
  }

  return response;
}
