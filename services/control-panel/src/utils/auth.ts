export type AppMode = 'landing' | 'control-panel' | 'dev';

const LANDING_HOSTNAME = 'ridesharing.portfolio.andresbrocco.com';
const CONTROL_PANEL_HOSTNAME = 'control-panel.ridesharing.portfolio.andresbrocco.com';

// Session storage keys for the authenticated session
const SESSION_KEY_API_KEY = 'apiKey';
const SESSION_KEY_ROLE = 'role';
const SESSION_KEY_EMAIL = 'email';

export function getAppMode(): AppMode {
  const hostname = window.location.hostname;

  if (hostname === CONTROL_PANEL_HOSTNAME) {
    return 'control-panel';
  }
  if (hostname === LANDING_HOSTNAME) {
    return 'landing';
  }
  return 'dev';
}

// --- Session storage helpers ---

/** Returns the API key stored in the current session, or null if not authenticated. */
export function getApiKey(): string | null {
  return sessionStorage.getItem(SESSION_KEY_API_KEY) || null;
}

/** Returns the role of the authenticated user ('admin', 'operator', etc.), or null. */
export function getSessionRole(): string | null {
  return sessionStorage.getItem(SESSION_KEY_ROLE) || null;
}

/** Returns the email of the authenticated user, or null. */
export function getSessionEmail(): string | null {
  return sessionStorage.getItem(SESSION_KEY_EMAIL) || null;
}

/**
 * Stores api_key, role, and email in sessionStorage after a successful login.
 * Called by LoginDialog on a 200 response from POST /auth/login.
 */
export function storeSession(apiKey: string, role: string, email: string): void {
  sessionStorage.setItem(SESSION_KEY_API_KEY, apiKey);
  sessionStorage.setItem(SESSION_KEY_ROLE, role);
  sessionStorage.setItem(SESSION_KEY_EMAIL, email);
}

/** Removes all session fields from sessionStorage. */
export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY_API_KEY);
  sessionStorage.removeItem(SESSION_KEY_ROLE);
  sessionStorage.removeItem(SESSION_KEY_EMAIL);
}
