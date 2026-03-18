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
const SESSION_STEP_SECONDS = 30 * 60;
const MAX_REMAINING_SECONDS = 2 * 3600;
const WARNING_THRESHOLD_SECONDS = 5 * 60;
const COST_PER_HOUR = 0.31;

interface SessionTimerProps {
  apiKey?: string;
}

export default function SessionTimer({ apiKey }: SessionTimerProps) {
  const [deadline, setDeadline] = useState<number | null>(null);
  const [costSoFar, setCostSoFar] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [active, setActive] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [deployedAt, setDeployedAt] = useState<number | null>(null);
  const [extending, setExtending] = useState(false);
  const [shrinking, setShrinking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [hasSession, setHasSession] = useState(false);
  const deadlineRef = useRef<number | null>(null);
  const deployedAtRef = useRef<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Keep ref in sync with state for the tick interval
  useEffect(() => {
    deadlineRef.current = deadline;
  }, [deadline]);

  // Keep refs in sync
  useEffect(() => {
    deployedAtRef.current = deployedAt;
  }, [deployedAt]);

  // Apply server response to local state
  const applyStatus = useCallback((data: SessionStatusResponse) => {
    setActive(data.active);

    // Deploying state: session exists but no deadline yet
    if (data.deploying) {
      setDeploying(true);
      setDeployedAt(data.deployed_at ?? null);
      setCostSoFar(data.cost_so_far ?? null);
      setRemainingSeconds(0);
      setHasSession(true);
      if (data.deployed_at != null) {
        setElapsedSeconds(Math.floor(Date.now() / 1000) - data.deployed_at);
      }
      return;
    }

    setDeploying(false);

    if (data.active && data.deadline != null) {
      setDeadline(data.deadline);
      setDeployedAt(data.deployed_at ?? null);
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

  // Client-side tick for smooth countdown and elapsed time
  useEffect(() => {
    if (!active && !deploying) return;

    const id = setInterval(() => {
      const now = Math.floor(Date.now() / 1000);

      // Update elapsed time
      const da = deployedAtRef.current;
      if (da != null) {
        setElapsedSeconds(now - da);
      }

      // Update countdown (only when active, not deploying)
      if (active) {
        const dl = deadlineRef.current;
        if (dl != null) {
          setRemainingSeconds(Math.max(0, dl - now));
        }
      }
    }, TICK_INTERVAL_MS);

    return () => clearInterval(id);
  }, [active, deploying]);

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
  const isExpired = !active && !deploying && hasSession;
  const canExtend =
    !!apiKey && active && remainingSeconds + SESSION_STEP_SECONDS <= MAX_REMAINING_SECONDS;
  const canShrink = !!apiKey && active && remainingSeconds >= SESSION_STEP_SECONDS;

  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  const timeDisplay = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  const elapsedMin = Math.floor(elapsedSeconds / 60);
  const elapsedSec = elapsedSeconds % 60;
  const elapsedDisplay = `${elapsedMin}m ${String(elapsedSec).padStart(2, '0')}s`;

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

  const estimatedCost = (elapsedSeconds / 3600) * COST_PER_HOUR;

  // Deploying state: show elapsed time and estimated cost instead of countdown
  if (deploying) {
    return (
      <div className={styles.container}>
        <div>
          <div className={styles.countdown}>Deploying...</div>
          <div className={styles.cost}>
            {elapsedDisplay} elapsed &middot; ~${estimatedCost.toFixed(2)} spent
          </div>
        </div>
      </div>
    );
  }

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
          title="Remove 30 minutes"
        >
          {shrinking ? '...' : '-30m'}
        </button>
        <button
          className={styles.timerButton}
          onClick={handleExtend}
          disabled={!canExtend || extending}
          title="Add 30 minutes"
        >
          {extending ? '...' : '+30m'}
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
