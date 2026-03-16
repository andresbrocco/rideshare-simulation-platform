import { useState, useCallback } from 'react';

type NotifyPermission = 'default' | 'granted' | 'denied' | 'unsupported';

interface UseDeployNotificationReturn {
  enabled: boolean;
  toggle: () => void;
  permission: NotifyPermission;
  notifySuccess: () => void;
  notifyError: (message: string) => void;
  markDeployStarted: () => void;
  checkPendingNotification: (outcome: 'success' | 'error', errorMessage?: string) => void;
}

const STORAGE_KEY = 'deploy-notify-enabled';
const DEPLOYING_FLAG_KEY = 'deploy-was-in-progress';

function getInitialPermission(): NotifyPermission {
  if (typeof Notification === 'undefined') return 'unsupported';
  return Notification.permission as NotifyPermission;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

export function playSuccessChime(ctx: AudioContext | null): void {
  if (!ctx || prefersReducedMotion()) return;
  if (ctx.state === 'suspended') ctx.resume();

  const now = ctx.currentTime;

  // Note 1: C5 (523.25 Hz)
  const osc1 = ctx.createOscillator();
  const gain1 = ctx.createGain();
  osc1.type = 'sine';
  osc1.frequency.value = 523.25;
  gain1.gain.setValueAtTime(0, now);
  gain1.gain.linearRampToValueAtTime(0.3, now + 0.03);
  gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
  osc1.connect(gain1);
  gain1.connect(ctx.destination);
  osc1.start(now);
  osc1.stop(now + 0.15);

  // Note 2: E5 (659.25 Hz) — starts slightly before note 1 ends
  const osc2 = ctx.createOscillator();
  const gain2 = ctx.createGain();
  osc2.type = 'sine';
  osc2.frequency.value = 659.25;
  gain2.gain.setValueAtTime(0, now + 0.12);
  gain2.gain.linearRampToValueAtTime(0.3, now + 0.15);
  gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.32);
  osc2.connect(gain2);
  gain2.connect(ctx.destination);
  osc2.start(now + 0.12);
  osc2.stop(now + 0.32);
}

export function playErrorTone(ctx: AudioContext | null): void {
  if (!ctx || prefersReducedMotion()) return;
  if (ctx.state === 'suspended') ctx.resume();

  const now = ctx.currentTime;

  // Note 1: E4 (329.63 Hz)
  const osc1 = ctx.createOscillator();
  const gain1 = ctx.createGain();
  osc1.type = 'sine';
  osc1.frequency.value = 329.63;
  gain1.gain.setValueAtTime(0, now);
  gain1.gain.linearRampToValueAtTime(0.25, now + 0.03);
  gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
  osc1.connect(gain1);
  gain1.connect(ctx.destination);
  osc1.start(now);
  osc1.stop(now + 0.2);

  // Note 2: C4 (261.63 Hz) — descending
  const osc2 = ctx.createOscillator();
  const gain2 = ctx.createGain();
  osc2.type = 'sine';
  osc2.frequency.value = 261.63;
  gain2.gain.setValueAtTime(0, now + 0.15);
  gain2.gain.linearRampToValueAtTime(0.25, now + 0.18);
  gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
  osc2.connect(gain2);
  gain2.connect(ctx.destination);
  osc2.start(now + 0.15);
  osc2.stop(now + 0.35);
}

export function wasPendingDeploy(): boolean {
  if (typeof sessionStorage === 'undefined') return false;
  return sessionStorage.getItem(DEPLOYING_FLAG_KEY) === 'true';
}

export function useDeployNotification(): UseDeployNotificationReturn {
  const [permission, setPermission] = useState<NotifyPermission>(getInitialPermission);
  const [enabled, setEnabled] = useState<boolean>(() => {
    if (typeof sessionStorage === 'undefined') return false;
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored !== 'true') return false;
    // Only restore if permission was already granted (or sound-only)
    return getInitialPermission() !== 'unsupported';
  });

  const toggle = useCallback(async () => {
    if (enabled) {
      setEnabled(false);
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(DEPLOYING_FLAG_KEY);
      return;
    }

    // Request notification permission if not yet decided
    let currentPermission = getInitialPermission();
    if (currentPermission === 'default') {
      const result = await Notification.requestPermission();
      currentPermission = result as NotifyPermission;
      setPermission(currentPermission);
    }

    setEnabled(true);
    sessionStorage.setItem(STORAGE_KEY, 'true');
  }, [enabled]);

  const notifySuccess = useCallback(() => {
    if (!enabled) return;

    if (permission === 'granted') {
      new Notification('Deploy Complete', {
        body: 'All services are ready. Your platform is live.',
        icon: '/favicon.svg',
        tag: 'deploy-complete',
      });
    }

    setEnabled(false);
    sessionStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(DEPLOYING_FLAG_KEY);
  }, [enabled, permission]);

  const notifyError = useCallback(
    (message: string) => {
      if (!enabled) return;

      if (permission === 'granted') {
        new Notification('Deployment Failed', {
          body: message,
          icon: '/favicon.svg',
          tag: 'deploy-failed',
        });
      }

      setEnabled(false);
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(DEPLOYING_FLAG_KEY);
    },
    [enabled, permission]
  );

  const markDeployStarted = useCallback(() => {
    sessionStorage.setItem(DEPLOYING_FLAG_KEY, 'true');
  }, []);

  const checkPendingNotification = useCallback(
    (outcome: 'success' | 'error', errorMessage?: string) => {
      const wasDeploying = sessionStorage.getItem(DEPLOYING_FLAG_KEY) === 'true';
      if (!wasDeploying) return;
      sessionStorage.removeItem(DEPLOYING_FLAG_KEY);
      if (!enabled) return;
      if (outcome === 'success') {
        notifySuccess();
      } else {
        notifyError(errorMessage ?? 'Deployment failed');
      }
    },
    [enabled, notifySuccess, notifyError]
  );

  return {
    enabled,
    toggle,
    permission,
    notifySuccess,
    notifyError,
    markDeployStarted,
    checkPendingNotification,
  };
}
