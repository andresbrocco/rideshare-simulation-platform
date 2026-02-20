import { useState, useEffect, useRef, useCallback } from 'react';
import { triggerDeploy, checkDeployStatus, LambdaServiceError } from '../services/lambda';
import type { StatusResponse } from '../services/lambda';
import styles from './LaunchDemoPanel.module.css';

interface LaunchDemoPanelProps {
  apiKey: string;
  onApiReady: () => void;
}

type DeployState = 'ready' | 'deploying' | 'error';

/** Maps workflow status to a human-readable progress message */
const STATUS_MESSAGES: Record<string, string> = {
  queued: 'Triggering deployment...',
  in_progress: 'Workflow running...',
  completed: 'Starting services...',
  health_check: 'Almost ready...',
};

const POLLING_CONFIG = {
  STATUS_INTERVAL: 20_000,
  HEALTH_INTERVAL: 10_000,
  /** After this many health attempts (120 * 10s = 20 min), show a warning */
  MAX_HEALTH_BEFORE_WARNING: 120,
  /** After warning, slow down health polling */
  SLOW_HEALTH_INTERVAL: 30_000,
  NETWORK_RETRY_BACKOFF: [5_000, 10_000, 20_000],
};

const GITHUB_ACTIONS_URL = 'https://github.com/andresbrocco/rideshare-simulation-platform/actions';

/**
 * Progress steps shown during deployment.
 * `activeKey` maps each step to the workflow status that activates it.
 */
const PROGRESS_STEPS = [
  { label: 'Triggering deployment...', activeKey: 'queued' },
  { label: 'Workflow running...', activeKey: 'in_progress' },
  { label: 'Starting services...', activeKey: 'completed' },
  { label: 'Almost ready...', activeKey: 'health_check' },
] as const;

export default function LaunchDemoPanel({ apiKey, onApiReady }: LaunchDemoPanelProps) {
  const [deployState, setDeployState] = useState<DeployState>('ready');
  const [workflowStatus, setWorkflowStatus] = useState<string>('queued');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [networkError, setNetworkError] = useState(false);
  const [healthAttempts, setHealthAttempts] = useState(0);
  const [launching, setLaunching] = useState(false);

  const statusIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const healthIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const networkRetryCountRef = useRef(0);
  const mountedRef = useRef(true);
  const startPollingRef = useRef<() => void>(() => {});

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // ── Cleanup ──────────────────────────────────────────────────────────
  const clearPolling = useCallback(() => {
    if (statusIntervalRef.current) {
      clearInterval(statusIntervalRef.current);
      statusIntervalRef.current = null;
    }
    if (healthIntervalRef.current) {
      clearInterval(healthIntervalRef.current);
      healthIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearPolling();
    };
  }, [clearPolling]);

  // ── Health check ─────────────────────────────────────────────────────
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

  // ── Status polling ───────────────────────────────────────────────────
  const pollStatus = useCallback(async () => {
    try {
      const status: StatusResponse = await checkDeployStatus(apiKey);
      if (!mountedRef.current) return;

      networkRetryCountRef.current = 0;
      setNetworkError(false);

      setWorkflowStatus(status.status);

      if (status.conclusion === 'failure' || status.conclusion === 'cancelled') {
        clearPolling();
        setErrorMessage(status.error ?? `Workflow ${status.conclusion}`);
        setDeployState('error');
      }
    } catch (err) {
      if (!mountedRef.current) return;
      if (err instanceof LambdaServiceError && err.code === 'NETWORK_ERROR') {
        setNetworkError(true);
        networkRetryCountRef.current = Math.min(
          networkRetryCountRef.current + 1,
          POLLING_CONFIG.NETWORK_RETRY_BACKOFF.length - 1
        );
      }
    }
  }, [apiKey, clearPolling]);

  // ── Health polling ───────────────────────────────────────────────────
  const pollHealth = useCallback(async () => {
    const healthy = await checkHealth();
    if (!mountedRef.current) return;

    if (healthy) {
      clearPolling();
      onApiReady();
      return;
    }

    setHealthAttempts((prev) => prev + 1);
  }, [checkHealth, clearPolling, onApiReady]);

  // ── Slow down health polling after too many attempts ─────────────────
  useEffect(() => {
    if (
      deployState === 'deploying' &&
      healthAttempts === POLLING_CONFIG.MAX_HEALTH_BEFORE_WARNING &&
      healthIntervalRef.current
    ) {
      clearInterval(healthIntervalRef.current);
      healthIntervalRef.current = setInterval(pollHealth, POLLING_CONFIG.SLOW_HEALTH_INTERVAL);
    }
  }, [healthAttempts, deployState, pollHealth]);

  // ── Start both polling loops ─────────────────────────────────────────
  const startPolling = useCallback(() => {
    // Immediate first checks
    pollStatus();
    pollHealth();

    statusIntervalRef.current = setInterval(pollStatus, POLLING_CONFIG.STATUS_INTERVAL);
    healthIntervalRef.current = setInterval(pollHealth, POLLING_CONFIG.HEALTH_INTERVAL);
  }, [pollStatus, pollHealth]);

  // Keep ref in sync so the mount effect always calls the latest version
  startPollingRef.current = startPolling;

  // ── Resume deployment state on mount (page refresh) ──────────────────
  useEffect(() => {
    let cancelled = false;

    async function resumeIfDeploying() {
      try {
        const status = await checkDeployStatus(apiKey);
        if (cancelled || !mountedRef.current) return;

        if (status.status === 'queued' || status.status === 'in_progress') {
          setWorkflowStatus(status.status);
          setDeployState('deploying');
          startPollingRef.current();
        } else if (status.status === 'completed' && !status.conclusion) {
          // Workflow completed but no conclusion yet — services starting
          setWorkflowStatus('completed');
          setDeployState('deploying');
          startPollingRef.current();
        }
      } catch {
        // Lambda unreachable or no prior deploy — stay in ready state
      }
    }

    resumeIfDeploying();

    return () => {
      cancelled = true;
    };
  }, [apiKey]);

  // ── Launch handler ───────────────────────────────────────────────────
  const handleLaunch = async () => {
    setLaunching(true);
    try {
      const result = await triggerDeploy(apiKey);
      if (!mountedRef.current) return;

      if (!result.triggered) {
        setErrorMessage(result.error ?? 'Deploy trigger returned false');
        setDeployState('error');
        return;
      }

      setDeployState('deploying');
      setWorkflowStatus('queued');
      setHealthAttempts(0);
      startPolling();
    } catch (err) {
      if (!mountedRef.current) return;
      const message = err instanceof Error ? err.message : 'Unknown error';
      setErrorMessage(message);
      setDeployState('error');
    } finally {
      if (mountedRef.current) setLaunching(false);
    }
  };

  // ── Retry handler ────────────────────────────────────────────────────
  const handleRetry = () => {
    setDeployState('ready');
    setErrorMessage('');
    setNetworkError(false);
    networkRetryCountRef.current = 0;
    setHealthAttempts(0);
  };

  // ── Determine which progress step is active ──────────────────────────
  const activeStepIndex = PROGRESS_STEPS.findIndex((step) => step.activeKey === workflowStatus);

  // ── Render ───────────────────────────────────────────────────────────
  return (
    <div className={styles.container}>
      {/* Header — consistent with ControlPanel */}
      <div className={styles.header}>
        <h2>Rideshare Simulation</h2>
        <div
          className={`${styles.statusBadge} ${
            deployState === 'ready'
              ? styles.statusOffline
              : deployState === 'deploying'
                ? styles.statusDeploying
                : styles.statusError
          }`}
        >
          {deployState === 'ready'
            ? 'Offline'
            : deployState === 'deploying'
              ? 'Deploying...'
              : 'Error'}
        </div>
      </div>

      <div className={styles.body}>
        {networkError && deployState === 'deploying' && (
          <div className={styles.networkBanner}>Connection lost, retrying...</div>
        )}

        {/* State A: Ready to Launch */}
        {deployState === 'ready' && (
          <>
            <p className={styles.message}>The simulation platform is not currently running.</p>
            <button className={styles.launchButton} onClick={handleLaunch} disabled={launching}>
              {launching ? 'Triggering...' : 'Launch Demo'}
            </button>
            <div className={styles.warnings}>
              <span className={styles.warning}>Estimated cost: ~$0.65/hour</span>
              <span className={styles.warning}>Deployment takes 10-15 minutes</span>
            </div>
          </>
        )}

        {/* State B: Deploying */}
        {deployState === 'deploying' && (
          <>
            <div className={styles.deployingStatus}>
              <div className={styles.spinner} />
              <span className={styles.deployingText}>
                {STATUS_MESSAGES[workflowStatus] ?? 'Deploying...'}
              </span>
            </div>

            <ul className={styles.progressList}>
              {PROGRESS_STEPS.map((step, i) => {
                let className = styles.progressItem;
                if (i < activeStepIndex) {
                  className += ` ${styles.progressItemDone}`;
                } else if (i === activeStepIndex) {
                  className += ` ${styles.progressItemActive}`;
                }
                return (
                  <li key={step.activeKey} className={className}>
                    {step.label}
                  </li>
                );
              })}
            </ul>

            <p className={styles.timeEstimate}>This may take 10-15 minutes</p>

            {healthAttempts >= POLLING_CONFIG.MAX_HEALTH_BEFORE_WARNING && (
              <p className={styles.timeWarning}>
                Deployment completed but services are taking longer than expected.{' '}
                <a
                  href={GITHUB_ACTIONS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.githubLink}
                  style={{ display: 'inline', marginTop: 0 }}
                >
                  Check GitHub Actions
                </a>
              </p>
            )}
          </>
        )}

        {/* State C: Error */}
        {deployState === 'error' && (
          <>
            <div className={styles.errorIcon}>&#9888;</div>
            <h3 className={styles.errorTitle}>Deployment Failed</h3>
            <div className={styles.errorMessage}>{errorMessage}</div>
            <button className={styles.retryButton} onClick={handleRetry}>
              Retry
            </button>
            <a
              href={GITHUB_ACTIONS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.githubLink}
            >
              View GitHub Actions &rarr;
            </a>
          </>
        )}
      </div>
    </div>
  );
}
