import { useState, useEffect, useRef, useCallback } from 'react';
import { triggerDeploy, getSessionStatus, LambdaServiceError } from '../services/lambda';
import { getSessionEmail } from '../utils/auth';
import styles from './LaunchDemoPanel.module.css';

interface LaunchDemoPanelProps {
  apiKey: string;
  onApiReady: () => void;
}

type DeployState = 'ready' | 'deploying' | 'error';

const GITHUB_ACTIONS_URL = 'https://github.com/andresbrocco/rideshare-simulation-platform/actions';

export default function LaunchDemoPanel({ apiKey, onApiReady }: LaunchDemoPanelProps) {
  const [deployState, setDeployState] = useState<DeployState>('ready');
  const [progressMessage, setProgressMessage] = useState('Triggering deployment...');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [networkError, setNetworkError] = useState(false);
  const [launching, setLaunching] = useState(false);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // ── Cleanup ──────────────────────────────────────────────────────────
  const clearPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearPolling();
    };
  }, [clearPolling]);

  // ── Session status polling ─────────────────────────────────────────────
  const pollSessionStatus = useCallback(async () => {
    try {
      const data = await getSessionStatus();
      if (!mountedRef.current) return;

      setNetworkError(false);

      if (data.active && data.deadline != null) {
        clearPolling();
        onApiReady();
        return;
      }

      if (data.deploying) {
        setProgressMessage('Deploying platform...');
        return;
      }

      if (!data.active && !data.deploying && !data.tearing_down) {
        // Session gone — deploy failed or was cleaned up
        clearPolling();
        setErrorMessage('Deployment did not complete');
        setDeployState('error');
      }
    } catch (err) {
      if (!mountedRef.current) return;
      if (err instanceof LambdaServiceError && err.code === 'NETWORK_ERROR') {
        setNetworkError(true);
      }
    }
  }, [clearPolling, onApiReady]);

  // ── Start polling ─────────────────────────────────────────────────
  const startPolling = useCallback(() => {
    pollSessionStatus();
    pollIntervalRef.current = setInterval(pollSessionStatus, 20_000);
  }, [pollSessionStatus]);

  // Keep ref for mount effect
  const startPollingRef = useRef<() => void>(() => {});
  startPollingRef.current = startPolling;

  // ── Resume deployment state on mount (page refresh) ──────────────────
  useEffect(() => {
    let cancelled = false;

    async function resumeIfDeploying() {
      try {
        const data = await getSessionStatus();
        if (cancelled || !mountedRef.current) return;

        if (data.deploying) {
          setProgressMessage('Deploying platform...');
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
  }, []);

  // ── Launch handler ───────────────────────────────────────────────────
  const handleLaunch = async () => {
    setLaunching(true);
    try {
      const result = await triggerDeploy(apiKey, 'duckdb', getSessionEmail() ?? undefined);
      if (!mountedRef.current) return;

      if (!result.triggered) {
        setErrorMessage(result.error ?? 'Deploy trigger returned false');
        setDeployState('error');
        return;
      }

      setDeployState('deploying');
      setProgressMessage('Triggering deployment...');
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
  };

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
              <span className={styles.warning}>Estimated cost: ~$0.31/hour</span>
              <span className={styles.warning}>Deployment takes 10-15 minutes</span>
            </div>
          </>
        )}

        {/* State B: Deploying */}
        {deployState === 'deploying' && (
          <>
            <div className={styles.deployingStatus}>
              <div className={styles.spinner} />
              <span className={styles.deployingText}>{progressMessage}</span>
            </div>

            <p className={styles.timeEstimate}>This may take 10-15 minutes</p>
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
