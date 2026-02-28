export type AppMode = 'landing' | 'control-panel' | 'dev';

const LANDING_HOSTNAME = 'ridesharing.portfolio.andresbrocco.com';
const CONTROL_PANEL_HOSTNAME = 'control-panel.ridesharing.portfolio.andresbrocco.com';
const COOKIE_DOMAIN = LANDING_HOSTNAME;
const COOKIE_NAME = 'apiKey';
const COOKIE_MAX_AGE = 86400; // 24 hours

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

export function setAuthCookie(apiKey: string): void {
  document.cookie = [
    `${COOKIE_NAME}=${encodeURIComponent(apiKey)}`,
    `Domain=${COOKIE_DOMAIN}`,
    'Path=/',
    'Secure',
    'SameSite=Lax',
    `Max-Age=${COOKIE_MAX_AGE}`,
  ].join('; ');
}

export function getAuthCookie(): string | null {
  const match = document.cookie.split('; ').find((row) => row.startsWith(`${COOKIE_NAME}=`));

  if (!match) return null;

  const value = decodeURIComponent(match.split('=')[1]);
  return value || null;
}

export function clearAuthCookie(): void {
  document.cookie = [
    `${COOKIE_NAME}=`,
    `Domain=${COOKIE_DOMAIN}`,
    'Path=/',
    'Secure',
    'SameSite=Lax',
    'Max-Age=0',
  ].join('; ');
}

export function redirectToControlPanel(): void {
  window.location.href = `https://${CONTROL_PANEL_HOSTNAME}`;
}

export function redirectToLanding(): void {
  // Use replace() to avoid back-button loop
  window.location.replace(`https://${LANDING_HOSTNAME}`);
}
