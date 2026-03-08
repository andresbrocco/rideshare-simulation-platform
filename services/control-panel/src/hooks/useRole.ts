import { getSessionRole } from '../utils/auth';

export type Role = 'admin' | 'viewer';

/**
 * Reads the authenticated user's role from sessionStorage synchronously.
 *
 * Returns 'admin' or 'viewer' when a session exists, or null when the user
 * is not logged in. The hook re-evaluates on every render, so any component
 * that derives disabled state from this will pick up role changes automatically
 * (e.g. after a login/logout cycle triggers a re-render of the parent).
 */
export function useRole(): Role | null {
  const raw = getSessionRole();
  if (raw === 'admin' || raw === 'viewer') {
    return raw;
  }
  return null;
}
