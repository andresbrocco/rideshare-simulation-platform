import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getSessionStatus,
  extendSession,
  shrinkSession,
  LambdaServiceError,
} from '../services/lambda';
import type { SessionStatusResponse } from '../services/lambda';
import styles from './SessionTimer.module.css';

const POLL_INTERVAL_MS = 30_000;
const TICK_INTERVAL_MS = 1_000;
const SESSION_STEP_SECONDS = 15 * 60;
const MAX_REMAINING_SECONDS = 2 * 3600;
const WARNING_THRESHOLD_SECONDS = 5 * 60;

interface SessionTimerProps {
  apiKey?: string;
}

export default function SessionTimer({ apiKey }: SessionTimerProps) {
  const [deadline, setDeadline] = useState<number | null>(null);
  const [costSoFar, setCostSoFar] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [active, setActive] = useState(false);
  const [extending, setExtending] = useState(false);
  const [shrinking, setShrinking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [hasSession, setHasSession] = useState(false);
  const deadlineRef = useRef<number | null>(null);

  // Keep ref in sync with state for the tick interval
  useEffect(() => {
    deadlineRef.current = deadline;
  }, [deadline]);

  // Apply server response to local state
  const applyStatus = useCallback((data: SessionStatusResponse) => {
    setActive(data.active);
    if (data.active && data.deadline != null) {
      setDeadline(data.deadline);
      setCostSoFar(data.cost_so_far ?? null);
      setRemainingSeconds(Math.max(0, data.deadline - Math.floor(Date.now() / 1000)));
      setHasSession(true);
    } else if (data.deployed_at != null) {
      // Session expired but we have history
      setDeadline(data.deadline ?? null);
      setCostSoFar(data.cost_so_far ?? null);
      setRemainingSeconds(0);
      setHasSession(true);
    } else {
      setHasSession(false);
    }
  }, []);

  // Poll session status
  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const data = await getSessionStatus();
        if (!cancelled) applyStatus(data);
      } catch {
        // Silently ignore poll errors
      }
    };

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [applyStatus]);

  // Client-side tick for smooth countdown
  useEffect(() => {
    if (!active) return;

    const id = setInterval(() => {
      const dl = deadlineRef.current;
      if (dl == null) return;
      const now = Math.floor(Date.now() / 1000);
      setRemainingSeconds(Math.max(0, dl - now));
    }, TICK_INTERVAL_MS);

    return () => clearInterval(id);
  }, [active]);

  const handleExtend = useCallback(async () => {
    if (!apiKey) return;
    setExtending(true);
    setActionError(null);
    try {
      const data = await extendSession(apiKey);
      setDeadline(data.deadline);
      setRemainingSeconds(data.remaining_seconds);
      setActive(true);
    } catch (e) {
      const msg = e instanceof LambdaServiceError ? e.message : 'Failed to extend';
      setActionError(msg);
    } finally {
      setExtending(false);
    }
  }, [apiKey]);

  const handleShrink = useCallback(async () => {
    if (!apiKey) return;
    setShrinking(true);
    setActionError(null);
    try {
      const data = await shrinkSession(apiKey);
      setDeadline(data.deadline);
      setRemainingSeconds(data.remaining_seconds);
    } catch (e) {
      const msg = e instanceof LambdaServiceError ? e.message : 'Failed to shrink';
      setActionError(msg);
    } finally {
      setShrinking(false);
    }
  }, [apiKey]);

  // Don't render if there's no session at all
  if (!hasSession) return null;

  const isWarning = active && remainingSeconds < WARNING_THRESHOLD_SECONDS;
  const isExpired = !active && hasSession;
  const canExtend =
    !!apiKey && active && remainingSeconds + SESSION_STEP_SECONDS <= MAX_REMAINING_SECONDS;
  const canShrink = !!apiKey && active && remainingSeconds >= SESSION_STEP_SECONDS;

  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  const timeDisplay = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  const containerClass = [
    styles.container,
    isWarning ? styles.containerWarning : '',
    isExpired ? styles.containerExpired : '',
  ]
    .filter(Boolean)
    .join(' ');

  const countdownClass = [
    styles.countdown,
    isWarning ? styles.countdownWarning : '',
    isExpired ? styles.countdownExpired : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={containerClass}>
      <div>
        <div className={countdownClass}>{isExpired ? '00:00' : timeDisplay}</div>
        {costSoFar != null && <div className={styles.cost}>${costSoFar.toFixed(2)} spent</div>}
      </div>
      <div className={styles.divider} />
      <div className={styles.buttons}>
        <button
          className={styles.timerButton}
          onClick={handleShrink}
          disabled={!canShrink || shrinking}
          title="Remove 15 minutes"
        >
          {shrinking ? '...' : '-15m'}
        </button>
        <button
          className={styles.timerButton}
          onClick={handleExtend}
          disabled={!canExtend || extending}
          title="Add 15 minutes"
        >
          {extending ? '...' : '+15m'}
        </button>
      </div>
      {actionError && (
        <span className={styles.error} title={actionError}>
          {actionError}
        </span>
      )}
    </div>
  );
}
