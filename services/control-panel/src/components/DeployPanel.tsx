import { useState, useEffect, useRef, useCallback } from 'react';
import {
  getSessionStatus,
  getServiceHealth,
  triggerDeploy,
  checkDeployStatus,
  activateSession,
  extendSession,
  shrinkSession,
  LambdaServiceError,
  ALL_SERVICES_DOWN,
} from '../services/lambda';
import type { StatusResponse, ServiceHealthMap } from '../services/lambda';
import styles from './DeployPanel.module.css';

interface DeployPanelProps {
  isLocal: boolean;
  apiKey: string | null;
  onNeedAuth: () => void;
  onServiceHealthChange: (health: ServiceHealthMap) => void;
}

type PanelState = 'idle' | 'deploying' | 'active' | 'tearing-down' | 'expired' | 'error';

const PROGRESS_STEPS = [
  { label: 'Triggering deployment...', activeKey: 'queued' },
  { label: 'Workflow running...', activeKey: 'in_progress' },
  { label: 'Starting services...', activeKey: 'completed' },
  { label: 'Almost ready...', activeKey: 'health_check' },
] as const;

const SESSION_STEP_SECONDS = 15 * 60;
const MAX_REMAINING_SECONDS = 2 * 3600;
const WARNING_THRESHOLD_SECONDS = 5 * 60;

const POLLING_CONFIG = {
  STATUS_INTERVAL: 20_000,
  HEALTH_INTERVAL: 10_000,
  SESSION_POLL_INTERVAL: 30_000,
  TICK_INTERVAL: 1_000,
  MAX_HEALTH_BEFORE_WARNING: 120,
  SLOW_HEALTH_INTERVAL: 30_000,
};

const GITHUB_ACTIONS_URL = 'https://github.com/andresbrocco/rideshare-simulation-platform/actions';

const ALL_SERVICES_UP: ServiceHealthMap = {
  simulation_api: true,
  grafana: true,
  airflow: true,
  trino: true,
  prometheus: true,
  control_panel: true,
};

export default function DeployPanel({
  isLocal,
  apiKey,
  onNeedAuth,
  onServiceHealthChange,
}: DeployPanelProps) {
  const [panelState, setPanelState] = useState<PanelState>('idle');
  const [workflowStatus, setWorkflowStatus] = useState('queued');
  const [errorMessage, setErrorMessage] = useState('');
  const [networkError, setNetworkError] = useState(false);
  const [healthAttempts, setHealthAttempts] = useState(0);
  const [launching, setLaunching] = useState(false);
  const [dbtRunner, setDbtRunner] = useState<'duckdb' | 'glue'>('duckdb');

  // Timer state
  const [deployedAt, setDeployedAt] = useState<number | null>(null);
  const [deadline, setDeadline] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [costSoFar, setCostSoFar] = useState<number | null>(null);
  const [extending, setExtending] = useState(false);
  const [shrinking, setShrinking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const statusIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const healthIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const deadlineRef = useRef<number | null>(null);
  const deployedAtRef = useRef<number | null>(null);
  const networkRetryCountRef = useRef(0);
  const pendingDeployRef = useRef(false);
  const pendingActionRef = useRef<'extend' | 'shrink' | null>(null);
  const serviceHealthIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const apiUrl = isLocal
    ? import.meta.env.VITE_API_URL || 'http://localhost:8000'
    : 'https://api.ridesharing.portfolio.andresbrocco.com';

  // Keep refs in sync
  useEffect(() => {
    deadlineRef.current = deadline;
  }, [deadline]);

  useEffect(() => {
    deployedAtRef.current = deployedAt;
  }, [deployedAt]);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // ── Cleanup helpers ─────────────────────────────────────────────
  const clearDeployPolling = useCallback(() => {
    if (statusIntervalRef.current) {
      clearInterval(statusIntervalRef.current);
      statusIntervalRef.current = null;
    }
    if (healthIntervalRef.current) {
      clearInterval(healthIntervalRef.current);
      healthIntervalRef.current = null;
    }
    if (serviceHealthIntervalRef.current) {
      clearInterval(serviceHealthIntervalRef.current);
      serviceHealthIntervalRef.current = null;
    }
  }, []);

  const clearSessionPoll = useCallback(() => {
    if (sessionPollRef.current) {
      clearInterval(sessionPollRef.current);
      sessionPollRef.current = null;
    }
  }, []);

  const clearTick = useCallback(() => {
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  // Cleanup all intervals on unmount
  useEffect(() => {
    return () => {
      clearDeployPolling();
      clearSessionPoll();
      clearTick();
    };
  }, [clearDeployPolling, clearSessionPoll, clearTick]);

  // ── Health check ────────────────────────────────────────────────
  const checkHealth = useCallback(async (): Promise<boolean> => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      const response = await fetch(`${apiUrl}/health`, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response.ok;
    } catch {
      return false;
    }
  }, [apiUrl]);

  // ── Per-service health polling ─────────────────────────────────
  const pollServiceHealth = useCallback(async () => {
    if (!mountedRef.current) return;
    try {
      if (isLocal) {
        // In local dev, all services run together via Docker Compose
        const healthy = await checkHealth();
        onServiceHealthChange(healthy ? ALL_SERVICES_UP : ALL_SERVICES_DOWN);
      } else {
        const health = await getServiceHealth();
        if (mountedRef.current) onServiceHealthChange(health);
      }
    } catch {
      // Silently ignore
    }
  }, [isLocal, checkHealth, onServiceHealthChange]);

  // ── Transition to active ────────────────────────────────────────
  const transitionToActive = useCallback(
    (newDeadline: number, newDeployedAt: number | null) => {
      clearDeployPolling();
      setDeadline(newDeadline);
      if (newDeployedAt != null) setDeployedAt(newDeployedAt);
      const now = Math.floor(Date.now() / 1000);
      setRemainingSeconds(Math.max(0, newDeadline - now));
      setPanelState('active');
      pollServiceHealth();
    },
    [clearDeployPolling, pollServiceHealth]
  );

  // ── Deploy status polling ──────────────────────────────────────
  const pollStatus = useCallback(async () => {
    if (!apiKey) return;
    try {
      const status: StatusResponse = await checkDeployStatus(apiKey);
      if (!mountedRef.current) return;

      networkRetryCountRef.current = 0;
      setNetworkError(false);
      setWorkflowStatus(status.status);

      if (status.conclusion === 'failure' || status.conclusion === 'cancelled') {
        clearDeployPolling();
        setErrorMessage(`Workflow ${status.conclusion}`);
        setPanelState('error');
      }
    } catch (err) {
      if (!mountedRef.current) return;
      if (err instanceof LambdaServiceError && err.code === 'NETWORK_ERROR') {
        setNetworkError(true);
        networkRetryCountRef.current = Math.min(networkRetryCountRef.current + 1, 2);
      }
    }
  }, [apiKey, clearDeployPolling]);

  // ── Health polling ─────────────────────────────────────────────
  const pollHealth = useCallback(async () => {
    let allHealthy: boolean;

    if (isLocal) {
      allHealthy = await checkHealth();
    } else {
      try {
        const health = await getServiceHealth();
        if (!mountedRef.current) return;
        onServiceHealthChange(health);
        allHealthy = Object.values(health).every(Boolean);
      } catch {
        allHealthy = false;
      }
    }

    if (!mountedRef.current) return;

    if (allHealthy) {
      // Activate the session timer
      if (apiKey) {
        try {
          const result = await activateSession(apiKey);
          if (!mountedRef.current) return;
          transitionToActive(result.deadline, deployedAtRef.current);
        } catch {
          // Activation failed but services are up — still transition
          transitionToActive(
            Math.floor(Date.now() / 1000) + SESSION_STEP_SECONDS,
            deployedAtRef.current
          );
        }
      } else {
        transitionToActive(
          Math.floor(Date.now() / 1000) + SESSION_STEP_SECONDS,
          deployedAtRef.current
        );
      }
      return;
    }

    setHealthAttempts((prev) => prev + 1);
  }, [apiKey, isLocal, checkHealth, onServiceHealthChange, transitionToActive]);

  // Slow down health polling after too many attempts
  useEffect(() => {
    if (
      panelState === 'deploying' &&
      healthAttempts === POLLING_CONFIG.MAX_HEALTH_BEFORE_WARNING &&
      healthIntervalRef.current
    ) {
      clearInterval(healthIntervalRef.current);
      healthIntervalRef.current = setInterval(pollHealth, POLLING_CONFIG.SLOW_HEALTH_INTERVAL);
    }
  }, [healthAttempts, panelState, pollHealth]);

  // ── Start deploy polling ───────────────────────────────────────
  const startDeployPolling = useCallback(() => {
    pollStatus();
    pollHealth();
    pollServiceHealth();
    statusIntervalRef.current = setInterval(pollStatus, POLLING_CONFIG.STATUS_INTERVAL);
    healthIntervalRef.current = setInterval(pollHealth, POLLING_CONFIG.HEALTH_INTERVAL);
    serviceHealthIntervalRef.current = setInterval(
      pollServiceHealth,
      POLLING_CONFIG.HEALTH_INTERVAL
    );
  }, [pollStatus, pollHealth, pollServiceHealth]);

  // ── Client-side tick ───────────────────────────────────────────
  useEffect(() => {
    clearTick();

    if (panelState === 'deploying' || panelState === 'active' || panelState === 'tearing-down') {
      tickRef.current = setInterval(() => {
        const now = Math.floor(Date.now() / 1000);

        // Elapsed timer
        const da = deployedAtRef.current;
        if (da != null) {
          setElapsedSeconds(now - da);
        }

        // Countdown (active only)
        const dl = deadlineRef.current;
        if (dl != null) {
          const remaining = Math.max(0, dl - now);
          setRemainingSeconds(remaining);
          if (remaining === 0 && panelState === 'active') {
            setPanelState('expired');
          }
        }
      }, POLLING_CONFIG.TICK_INTERVAL);
    }

    return () => clearTick();
  }, [panelState, clearTick]);

  // ── Service health polling (active/expired/tearing-down) ──────
  useEffect(() => {
    if (serviceHealthIntervalRef.current) {
      clearInterval(serviceHealthIntervalRef.current);
      serviceHealthIntervalRef.current = null;
    }

    if (panelState === 'active' || panelState === 'expired' || panelState === 'tearing-down') {
      pollServiceHealth();
      serviceHealthIntervalRef.current = setInterval(
        pollServiceHealth,
        POLLING_CONFIG.HEALTH_INTERVAL
      );
    }

    return () => {
      if (serviceHealthIntervalRef.current) {
        clearInterval(serviceHealthIntervalRef.current);
        serviceHealthIntervalRef.current = null;
      }
    };
  }, [panelState, pollServiceHealth]);

  // ── Session status polling (active state) ──────────────────────
  useEffect(() => {
    clearSessionPoll();

    if (panelState === 'active' || panelState === 'tearing-down') {
      const poll = async () => {
        try {
          const data = await getSessionStatus();
          if (!mountedRef.current) return;

          if (data.tearing_down) {
            if (panelState !== 'tearing-down') {
              setPanelState('tearing-down');
            }
            if (data.cost_so_far != null) {
              setCostSoFar(data.cost_so_far);
            }
            return;
          }

          if (panelState === 'tearing-down') {
            // Teardown complete — session gone
            if (!data.active && !data.tearing_down && !data.deploying) {
              setPanelState('idle');
            }
            return;
          }

          // Normal active state polling
          if (data.deadline != null) {
            setDeadline(data.deadline);
          }
          if (data.cost_so_far != null) {
            setCostSoFar(data.cost_so_far);
          }
          if (!data.active && !data.deploying) {
            setPanelState('expired');
          }
        } catch {
          if (panelState === 'tearing-down') {
            // Lambda unreachable (infra destroyed) — teardown complete
            setPanelState('idle');
          }
        }
      };

      sessionPollRef.current = setInterval(poll, POLLING_CONFIG.SESSION_POLL_INTERVAL);
    }

    return () => clearSessionPoll();
  }, [panelState, clearSessionPoll, onServiceHealthChange]);

  // ── Resume state on mount ──────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function resume() {
      try {
        const sessionData = await getSessionStatus();
        if (cancelled || !mountedRef.current) return;

        if (sessionData.tearing_down) {
          setDeployedAt(sessionData.deployed_at ?? null);
          setCostSoFar(sessionData.cost_so_far ?? null);
          if (sessionData.deployed_at != null) {
            setElapsedSeconds(Math.floor(Date.now() / 1000) - sessionData.deployed_at);
          }
          setPanelState('tearing-down');
          return;
        }

        if (sessionData.deploying) {
          // Deploying — session exists but no deadline
          setDeployedAt(sessionData.deployed_at ?? null);
          setCostSoFar(sessionData.cost_so_far ?? null);
          if (sessionData.deployed_at != null) {
            setElapsedSeconds(Math.floor(Date.now() / 1000) - sessionData.deployed_at);
          }
          setPanelState('deploying');
          // Start polling for deploy status + health
          startDeployPolling();
          return;
        }

        if (sessionData.active && sessionData.deadline != null) {
          // Active session
          setDeployedAt(sessionData.deployed_at ?? null);
          setDeadline(sessionData.deadline);
          setCostSoFar(sessionData.cost_so_far ?? null);
          const now = Math.floor(Date.now() / 1000);
          setRemainingSeconds(Math.max(0, sessionData.deadline - now));
          if (sessionData.deployed_at != null) {
            setElapsedSeconds(now - sessionData.deployed_at);
          }
          setPanelState('active');
          return;
        }

        // Stale expired session or no session — show idle (fresh deploy button).
        // Only the real-time tick (line 258) transitions to 'expired' for
        // users who actively watched their own session count down to zero.
        setPanelState('idle');
      } catch {
        // Lambda unreachable — stay idle
      }
    }

    resume();
    return () => {
      cancelled = true;
    };
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Deploy handler ─────────────────────────────────────────────
  const handleDeploy = async () => {
    if (!apiKey) {
      pendingDeployRef.current = true;
      onNeedAuth();
      return;
    }

    setLaunching(true);
    try {
      const result = await triggerDeploy(apiKey, dbtRunner);
      if (!mountedRef.current) return;

      if (!result.triggered) {
        setErrorMessage(result.error ?? 'Deploy trigger returned false');
        setPanelState('error');
        return;
      }

      const now = Math.floor(Date.now() / 1000);
      setDeployedAt(now);
      setElapsedSeconds(0);
      setPanelState('deploying');
      setWorkflowStatus('queued');
      setHealthAttempts(0);
      startDeployPolling();
    } catch (err) {
      if (!mountedRef.current) return;
      const message = err instanceof Error ? err.message : 'Unknown error';
      setErrorMessage(message);
      setPanelState('error');
    } finally {
      if (mountedRef.current) setLaunching(false);
    }
  };

  // ── Auto-deploy after auth ────────────────────────────────────
  useEffect(() => {
    if (apiKey && pendingDeployRef.current && panelState === 'idle') {
      pendingDeployRef.current = false;
      handleDeploy();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  // ── Extend/Shrink handlers ─────────────────────────────────────
  const handleExtend = useCallback(async () => {
    if (!apiKey) {
      pendingActionRef.current = 'extend';
      onNeedAuth();
      return;
    }
    setExtending(true);
    setActionError(null);
    try {
      const data = await extendSession(apiKey);
      setDeadline(data.deadline);
      setRemainingSeconds(data.remaining_seconds);
    } catch (e) {
      setActionError(e instanceof LambdaServiceError ? e.message : 'Failed to extend');
    } finally {
      setExtending(false);
    }
  }, [apiKey, onNeedAuth]);

  const handleShrink = useCallback(async () => {
    if (!apiKey) {
      pendingActionRef.current = 'shrink';
      onNeedAuth();
      return;
    }
    setShrinking(true);
    setActionError(null);
    try {
      const data = await shrinkSession(apiKey);
      setDeadline(data.deadline);
      setRemainingSeconds(data.remaining_seconds);
    } catch (e) {
      setActionError(e instanceof LambdaServiceError ? e.message : 'Failed to shrink');
    } finally {
      setShrinking(false);
    }
  }, [apiKey, onNeedAuth]);

  // ── Auto-extend/shrink after auth ──────────────────────────────
  useEffect(() => {
    if (apiKey && pendingActionRef.current && panelState === 'active') {
      const action = pendingActionRef.current;
      pendingActionRef.current = null;
      if (action === 'extend') {
        handleExtend();
      } else {
        handleShrink();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey]);

  // ── Retry handler ──────────────────────────────────────────────
  const handleRetry = () => {
    setPanelState('idle');
    setErrorMessage('');
    setNetworkError(false);
    networkRetryCountRef.current = 0;
    setHealthAttempts(0);
  };

  // ── Derived values ─────────────────────────────────────────────
  const activeStepIndex = PROGRESS_STEPS.findIndex((s) => s.activeKey === workflowStatus);
  const isWarning = panelState === 'active' && remainingSeconds < WARNING_THRESHOLD_SECONDS;
  const canExtend =
    panelState === 'active' && remainingSeconds + SESSION_STEP_SECONDS <= MAX_REMAINING_SECONDS;
  const canShrink = panelState === 'active' && remainingSeconds >= SESSION_STEP_SECONDS;

  const formatTime = (totalSeconds: number) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const formatElapsed = (totalSeconds: number) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}m ${String(s).padStart(2, '0')}s`;
  };

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className={styles.container}>
      {/* Idle */}
      {panelState === 'idle' && (
        <>
          <div className={styles.runnerRow}>
            <label htmlFor="dbt-runner-select" className={styles.runnerLabel}>
              DBT Runner
            </label>
            <select
              id="dbt-runner-select"
              className={styles.runnerSelect}
              value={dbtRunner}
              onChange={(e) => setDbtRunner(e.target.value as 'duckdb' | 'glue')}
              disabled={launching}
            >
              <option value="duckdb">DuckDB</option>
              <option value="glue">AWS Glue</option>
            </select>
          </div>
          <button className={styles.deployButton} onClick={handleDeploy} disabled={launching}>
            {launching ? 'Triggering...' : 'Deploy Platform'}
          </button>
          <div className={styles.warnings}>
            <span className={styles.warning}>~$0.31/hour</span>
            <span className={styles.warning}>10-15 min deploy time</span>
          </div>
        </>
      )}

      {/* Deploying */}
      {panelState === 'deploying' && (
        <>
          {networkError && <div className={styles.networkBanner}>Connection lost, retrying...</div>}

          <div className={styles.deployingHeader}>
            <div className={styles.spinner} />
            <span className={styles.deployingText}>Deploying...</span>
          </div>

          <ul className={styles.progressList}>
            {PROGRESS_STEPS.map((step, i) => {
              let cls = styles.progressItem;
              if (i < activeStepIndex) cls += ` ${styles.progressItemDone}`;
              else if (i === activeStepIndex) cls += ` ${styles.progressItemActive}`;
              return (
                <li key={step.activeKey} className={cls}>
                  {step.label}
                </li>
              );
            })}
          </ul>

          <div className={styles.elapsedRow}>
            <span>Elapsed:</span>
            <span className={styles.elapsedTime}>{formatElapsed(elapsedSeconds)}</span>
          </div>

          {healthAttempts >= POLLING_CONFIG.MAX_HEALTH_BEFORE_WARNING && (
            <p className={styles.timeWarning}>
              Services taking longer than expected.{' '}
              <a
                href={GITHUB_ACTIONS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.githubLink}
              >
                Check GitHub Actions
              </a>
            </p>
          )}
        </>
      )}

      {/* Tearing down */}
      {panelState === 'tearing-down' && (
        <>
          <div className={styles.deployingHeader}>
            <div className={`${styles.spinner} ${styles.spinnerTeardown}`} />
            <span className={styles.teardownText}>Tearing down...</span>
          </div>
          <div className={styles.teardownInfo}>
            Saving checkpoint and destroying infrastructure.
          </div>
          <div className={styles.elapsedRow}>
            <span>Elapsed:</span>
            <span className={styles.elapsedTime}>{formatElapsed(elapsedSeconds)}</span>
          </div>
          {costSoFar != null && <span className={styles.cost}>${costSoFar.toFixed(2)} spent</span>}
        </>
      )}

      {/* Active */}
      {panelState === 'active' && (
        <>
          <div className={styles.activeRow}>
            <div className={`${styles.countdown}${isWarning ? ` ${styles.countdownWarning}` : ''}`}>
              {formatTime(remainingSeconds)}
            </div>
            <div className={styles.divider} />
            <div className={styles.timerInfo}>
              <div className={styles.elapsedRow}>
                <span>Elapsed:</span>
                <span className={styles.elapsedTime}>{formatElapsed(elapsedSeconds)}</span>
              </div>
              {costSoFar != null && (
                <span className={styles.cost}>${costSoFar.toFixed(2)} spent</span>
              )}
            </div>
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
          </div>
          {actionError && <div className={styles.actionError}>{actionError}</div>}
        </>
      )}

      {/* Expired */}
      {panelState === 'expired' && (
        <div className={styles.expiredContainer}>
          <p className={styles.expiredText}>Session expired</p>
          <button className={styles.redeployButton} onClick={handleRetry}>
            Re-deploy
          </button>
        </div>
      )}

      {/* Error */}
      {panelState === 'error' && (
        <div className={styles.errorContainer}>
          <div className={styles.errorIcon}>&#9888;</div>
          <h3 className={styles.errorTitle}>Deployment Failed</h3>
          <div className={styles.errorMessage}>{errorMessage}</div>
          <button className={styles.retryButton} onClick={handleRetry}>
            Retry
          </button>
          <div style={{ marginTop: 8 }}>
            <a
              href={GITHUB_ACTIONS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.githubLink}
            >
              View GitHub Actions
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
