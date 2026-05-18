import { useState, useEffect, useRef, useCallback } from 'react';
import {
  getSessionStatus,
  getServiceHealth,
  getDeployStatus,
  getTeardownStatus,
  triggerDeploy,
  extendSession,
  shrinkSession,
  getDataState,
  resetData,
  LambdaServiceError,
  ALL_SERVICES_DOWN,
} from '../services/lambda';
import type { ServiceHealthMap, DataStateResponse } from '../services/lambda';
import { useRole } from '../hooks/useRole';
import ConfirmModal from './ConfirmModal';
import {
  useDeployNotification,
  playSuccessChime,
  playErrorTone,
} from '../hooks/useDeployNotification';
import { showToast } from '../lib/toast';
import { getSessionEmail } from '../utils/auth';
import styles from './DeployPanel.module.css';

interface DeployPanelProps {
  isLocal: boolean;
  apiKey: string | null;
  onNeedAuth: () => void;
  onServiceHealthChange: (health: ServiceHealthMap) => void;
  onSessionUpdate?: (data: { panelState: string; remainingSeconds: number }) => void;
}

type PanelState = 'idle' | 'deploying' | 'active' | 'tearing-down' | 'expired' | 'error';

const DEPLOY_STEPS = [
  { label: 'Provisioning infrastructure...', activeKey: 'provisioning' },
  { label: 'Applying Terraform...', activeKey: 'terraform' },
  { label: 'Preparing deployment...', activeKey: 'preparing' },
  { label: 'Starting services...', activeKey: 'services' },
  { label: 'Configuring platform...', activeKey: 'configuring' },
  { label: 'Setting up networking...', activeKey: 'networking' },
  { label: 'Finalizing...', activeKey: 'finalizing' },
] as const;

const ESTIMATED_DEPLOY_SECONDS = 1800; // 30 min (full convergence)

const TEARDOWN_STEPS = [
  { label: 'Saving simulation checkpoint...', activeKey: 'saving_checkpoint' },
  { label: 'Cleaning up DNS records...', activeKey: 'cleaning_dns' },
  { label: 'Destroying infrastructure...', activeKey: 'destroying_infra' },
  { label: 'Verifying cleanup...', activeKey: 'verifying' },
  { label: 'Finalizing...', activeKey: 'finalizing' },
] as const;

const ESTIMATED_TEARDOWN_SECONDS = 540; // 9 min

const SESSION_STEP_SECONDS = 30 * 60;
const MAX_REMAINING_SECONDS = 2 * 3600;
const WARNING_THRESHOLD_SECONDS = 5 * 60;

const POLLING_CONFIG = {
  STATUS_INTERVAL: 20_000,
  HEALTH_INTERVAL: 10_000,
  SESSION_POLL_INTERVAL: 30_000,
  TICK_INTERVAL: 1_000,
};

const GITHUB_ACTIONS_URL = 'https://github.com/andresbrocco/rideshare-simulation-platform/actions';

const ALL_SERVICES_UP: ServiceHealthMap = {
  simulation_api: true,
  grafana: true,
  airflow: true,
  dbt_docs: true,
  trino: true,
  prometheus: true,
  control_panel: true,
};

export default function DeployPanel({
  isLocal,
  apiKey,
  onNeedAuth,
  onServiceHealthChange,
  onSessionUpdate,
}: DeployPanelProps) {
  const {
    enabled: notifyEnabled,
    toggle: toggleNotify,
    permission: notifyPermission,
    notifySuccess,
    notifyError,
    markDeployStarted,
    checkPendingNotification,
  } = useDeployNotification();

  const [panelState, setPanelState] = useState<PanelState>('idle');
  const [deployStepIndex, setDeployStepIndex] = useState(-1);
  const [errorMessage, setErrorMessage] = useState('');
  const [networkError, setNetworkError] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [dbtRunner, setDbtRunner] = useState<'duckdb' | 'glue'>('duckdb');

  // Data state
  const role = useRole();
  const [dataState, setDataState] = useState<DataStateResponse | null>(null);
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetting, setResetting] = useState(false);

  // Timer state
  const [deployedAt, setDeployedAt] = useState<number | null>(null);
  const [deadline, setDeadline] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [costSoFar, setCostSoFar] = useState<number | null>(null);
  const [extending, setExtending] = useState(false);
  const [shrinking, setShrinking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [teardownStepIndex, setTeardownStepIndex] = useState(-1);
  const [teardownStartedAt, setTeardownStartedAt] = useState<number | null>(null);

  const mountedRef = useRef(true);
  const deployStatusIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const deadlineRef = useRef<number | null>(null);
  const deployedAtRef = useRef<number | null>(null);
  const pendingDeployRef = useRef(false);
  const pendingActionRef = useRef<'extend' | 'shrink' | null>(null);
  const serviceHealthIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const teardownPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const pendingNotificationRef = useRef<
    { type: 'success' } | { type: 'error'; message: string } | null
  >(null);

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

  // Bubble session state to parent
  useEffect(() => {
    onSessionUpdate?.({ panelState, remainingSeconds });
  }, [panelState, remainingSeconds, onSessionUpdate]);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      audioCtxRef.current?.close();
      audioCtxRef.current = null;
    };
  }, []);

  // ── Cleanup helpers ─────────────────────────────────────────────
  const clearDeployPolling = useCallback(() => {
    if (deployStatusIntervalRef.current) {
      clearInterval(deployStatusIntervalRef.current);
      deployStatusIntervalRef.current = null;
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
  const pollDeployStatus = useCallback(async () => {
    try {
      const data = await getDeployStatus();
      if (!mountedRef.current) return;

      setNetworkError(false);
      setDeployStepIndex(data.current_step);

      if (data.workflow_conclusion === 'failure' || data.workflow_conclusion === 'cancelled') {
        clearDeployPolling();
        setErrorMessage(`Workflow ${data.workflow_conclusion}`);
        setPanelState('error');
        return;
      }

      if (!data.deploying && data.workflow_conclusion === 'success') {
        // Deploy workflow finished — poll session-status for deadline
        try {
          const sessionData = await getSessionStatus();
          if (!mountedRef.current) return;
          if (sessionData.active && sessionData.deadline != null) {
            transitionToActive(
              sessionData.deadline,
              sessionData.deployed_at ?? deployedAtRef.current
            );
            return;
          }
        } catch {
          // Fall through — will retry next poll
        }
      }
    } catch (err) {
      if (!mountedRef.current) return;
      if (err instanceof LambdaServiceError && err.code === 'NETWORK_ERROR') {
        setNetworkError(true);
      }
    }
  }, [clearDeployPolling, transitionToActive]);

  // ── Start deploy polling ───────────────────────────────────────
  const startDeployPolling = useCallback(() => {
    pollDeployStatus();
    deployStatusIntervalRef.current = setInterval(pollDeployStatus, POLLING_CONFIG.STATUS_INTERVAL);
  }, [pollDeployStatus]);

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

    if (panelState === 'active' || panelState === 'deploying' || panelState === 'tearing-down') {
      const poll = async () => {
        try {
          const data = await getSessionStatus();
          if (!mountedRef.current) return;

          if (data.tearing_down) {
            if (panelState !== 'tearing-down') {
              setTeardownStartedAt(data.tearing_down_at ?? null);
              setPanelState('tearing-down');
            }
            if (data.cost_so_far != null) {
              setCostSoFar(data.cost_so_far);
            }
            return;
          }

          // Deploying: detect stale session cleared or activated externally
          if (panelState === 'deploying') {
            if (data.tearing_down) {
              clearDeployPolling();
              setTeardownStartedAt(data.tearing_down_at ?? null);
              setPanelState('tearing-down');
              return;
            }
            if (data.active && data.deadline != null) {
              // Another tab activated the session
              transitionToActive(data.deadline, data.deployed_at ?? deployedAtRef.current);
              return;
            }
            if (!data.active && !data.deploying) {
              // Backend cleaned up stale session (timeout or workflow failure)
              clearDeployPolling();
              setPanelState('idle');
              return;
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

      poll();
      sessionPollRef.current = setInterval(poll, POLLING_CONFIG.SESSION_POLL_INTERVAL);
    }

    return () => clearSessionPoll();
  }, [panelState, clearSessionPoll, clearDeployPolling, transitionToActive, onServiceHealthChange]);

  // ── Teardown progress polling ──────────────────────────────────
  useEffect(() => {
    if (teardownPollRef.current) {
      clearInterval(teardownPollRef.current);
      teardownPollRef.current = null;
    }

    if (panelState !== 'tearing-down') {
      setTeardownStepIndex(-1);
      return;
    }

    const pollTeardown = async () => {
      try {
        const data = await getTeardownStatus();
        if (!mountedRef.current) return;
        if (data.tearing_down) {
          setTeardownStepIndex(data.current_step);
        }
      } catch {
        // Silently ignore — progress bar stays at last known state
      }
    };

    pollTeardown();
    teardownPollRef.current = setInterval(pollTeardown, POLLING_CONFIG.STATUS_INTERVAL);

    return () => {
      if (teardownPollRef.current) {
        clearInterval(teardownPollRef.current);
        teardownPollRef.current = null;
      }
    };
  }, [panelState]);

  // ── Deploy-complete notification ───────────────────────────────
  const prevPanelStateRef = useRef<PanelState>('idle');

  useEffect(() => {
    const prev = prevPanelStateRef.current;
    prevPanelStateRef.current = panelState;

    if (prev === 'deploying' && panelState === 'active') {
      notifySuccess();
      if (document.hidden) {
        pendingNotificationRef.current = { type: 'success' };
      } else {
        showToast.success('Deploy complete — all services are ready');
        playSuccessChime(audioCtxRef.current);
      }
    }
    if (prev === 'deploying' && panelState === 'error') {
      notifyError(errorMessage);
      if (document.hidden) {
        pendingNotificationRef.current = {
          type: 'error',
          message: errorMessage || 'Deployment failed',
        };
      } else {
        showToast.error(errorMessage || 'Deployment failed');
        playErrorTone(audioCtxRef.current);
      }
    }
  }, [panelState, notifySuccess, notifyError, errorMessage]);

  // ── Drain pending notification when tab becomes visible ────────
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) return;
      const pending = pendingNotificationRef.current;
      if (!pending) return;
      pendingNotificationRef.current = null;
      if (pending.type === 'success') {
        showToast.success('Deploy complete — all services are ready');
        playSuccessChime(audioCtxRef.current);
      } else {
        showToast.error(pending.message);
        playErrorTone(audioCtxRef.current);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // ── Resume state on mount ──────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function resume() {
      try {
        const sessionData = await getSessionStatus();
        if (cancelled || !mountedRef.current) return;

        if (sessionData.tearing_down) {
          sessionStorage.removeItem('deploy-was-in-progress');
          setDeployedAt(sessionData.deployed_at ?? null);
          setCostSoFar(sessionData.cost_so_far ?? null);
          setTeardownStartedAt(sessionData.tearing_down_at ?? null);
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
          markDeployStarted();
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
          const hadPendingDeploy = checkPendingNotification('success');
          if (hadPendingDeploy) {
            showToast.success('Deploy complete — all services are ready');
            playSuccessChime(audioCtxRef.current);
          }
          return;
        }

        // Stale expired session or no session — show idle (fresh deploy button).
        // Only the real-time tick (line 258) transitions to 'expired' for
        // users who actively watched their own session count down to zero.
        checkPendingNotification('error', 'Deployment did not complete');
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

    if (!audioCtxRef.current && typeof AudioContext !== 'undefined') {
      audioCtxRef.current = new AudioContext();
    }

    setLaunching(true);
    try {
      const result = await triggerDeploy(apiKey, dbtRunner, getSessionEmail() ?? undefined);
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
      markDeployStarted();
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
      const data = await extendSession(apiKey, getSessionEmail() ?? undefined);
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
      const data = await shrinkSession(apiKey, getSessionEmail() ?? undefined);
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
  };

  // ── Data state polling ─────────────────────────────────────────
  useEffect(() => {
    if (panelState !== 'idle') return;

    let cancelled = false;
    const fetchDataState = async () => {
      try {
        const state = await getDataState();
        if (!cancelled) setDataState(state);
      } catch {
        // Non-fatal — indicator stays hidden
      }
    };

    fetchDataState();

    // Poll when resetting
    if (dataState?.status === 'resetting') {
      const interval = setInterval(fetchDataState, 10_000);
      return () => {
        cancelled = true;
        clearInterval(interval);
      };
    }

    return () => {
      cancelled = true;
    };
  }, [panelState, dataState?.status]);

  const handleReset = useCallback(async () => {
    setShowResetModal(false);
    if (!apiKey) {
      onNeedAuth();
      return;
    }
    setResetting(true);
    try {
      await resetData(apiKey);
      setDataState({ status: 'resetting' });
      showToast.success('Data reset triggered — this takes a few minutes');
    } catch (err) {
      const message = err instanceof LambdaServiceError ? err.message : 'Failed to reset data';
      showToast.error(message);
    } finally {
      setResetting(false);
    }
  }, [apiKey, onNeedAuth]);

  // ── Derived values ─────────────────────────────────────────────
  const etaRemaining = Math.max(0, ESTIMATED_DEPLOY_SECONDS - elapsedSeconds);
  const teardownElapsed =
    teardownStartedAt != null ? Math.floor(Date.now() / 1000) - teardownStartedAt : elapsedSeconds;
  const teardownEtaRemaining = Math.max(0, ESTIMATED_TEARDOWN_SECONDS - teardownElapsed);
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
          {dataState && (
            <div className={styles.dataStateRow}>
              <span className={styles.dataStateLabel}>Lakehouse data:</span>
              <span
                className={`${styles.dataStateBadge} ${
                  dataState.status === 'populated'
                    ? styles.dataState_populated
                    : dataState.status === 'clean'
                      ? styles.dataState_clean
                      : dataState.status === 'resetting'
                        ? styles.dataState_resetting
                        : dataState.status === 'error'
                          ? styles.dataState_error
                          : styles.dataState_unknown
                }`}
              >
                {dataState.status === 'resetting' && <span className={styles.dataStateSpinner} />}
                {dataState.status === 'populated' && 'Populated'}
                {dataState.status === 'clean' && 'Clean'}
                {dataState.status === 'resetting' && 'Resetting...'}
                {dataState.status === 'error' && 'Reset error'}
                {dataState.status === 'unknown' && 'Unknown'}
              </span>
              {role === 'admin' && dataState.status === 'populated' && (
                <button
                  className={styles.resetButton}
                  onClick={() => setShowResetModal(true)}
                  disabled={resetting}
                >
                  {resetting ? 'Resetting...' : 'Reset'}
                </button>
              )}
            </div>
          )}
          <button
            className={styles.deployButton}
            onClick={handleDeploy}
            disabled={launching || dataState?.status === 'resetting'}
          >
            {launching ? 'Triggering...' : 'Deploy Platform'}
          </button>
          <div className={styles.warnings}>
            <span className={styles.warning}>~$0.31/hour</span>
            <span className={styles.warning}>~30 min deploy time</span>
          </div>
          <ConfirmModal
            isOpen={showResetModal}
            title="Reset Lakehouse Data"
            message="This will wipe all Bronze, Silver, and Gold tables from S3. The reset takes a few minutes. Are you sure?"
            confirmText="Reset Data"
            cancelText="Cancel"
            variant="danger"
            onConfirm={handleReset}
            onCancel={() => setShowResetModal(false)}
          />
        </>
      )}

      {/* Deploying */}
      {panelState === 'deploying' && (
        <>
          {networkError && <div className={styles.networkBanner}>Connection lost, retrying...</div>}

          <div className={styles.etaRow}>
            <div className={styles.deployingHeader}>
              <span className={styles.deployingText}>Deploying...</span>
            </div>
            <span className={styles.etaCountdown}>
              {etaRemaining > 0 ? `~${formatTime(etaRemaining)} ETA` : 'Finishing up...'}
            </span>
          </div>

          <div className={styles.progressBar}>
            {DEPLOY_STEPS.map((step, i) => (
              <div key={step.activeKey} className={styles.segmentWrap} data-tooltip={step.label}>
                <div
                  className={[
                    styles.segment,
                    i < deployStepIndex ? styles.segmentDone : '',
                    i === deployStepIndex ? styles.segmentActive : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                />
              </div>
            ))}
          </div>

          <ul className={styles.progressList}>
            {DEPLOY_STEPS.map((step, i) => {
              let cls = styles.progressItem;
              if (i < deployStepIndex) cls += ` ${styles.progressItemDone}`;
              else if (i === deployStepIndex) cls += ` ${styles.progressItemActive}`;
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

          <label className={styles.notifyLabel}>
            <input
              type="checkbox"
              className={styles.notifyCheckbox}
              checked={notifyEnabled}
              onChange={() => {
                if (!audioCtxRef.current && typeof AudioContext !== 'undefined') {
                  audioCtxRef.current = new AudioContext();
                }
                toggleNotify();
              }}
            />
            <span className={styles.notifySwitch} />
            <span className={styles.notifyText}>Notify me when done</span>
            {notifyPermission === 'denied' && (
              <span className={styles.notifyHint}>
                {notifyEnabled ? 'sound only — notifications blocked' : 'notifications blocked'}
              </span>
            )}
          </label>
        </>
      )}

      {/* Tearing down */}
      {panelState === 'tearing-down' && (
        <>
          <div className={styles.etaRow}>
            <div className={styles.deployingHeader}>
              <span className={styles.teardownText}>Tearing down...</span>
            </div>
            <span className={styles.etaCountdownTeardown}>
              {teardownEtaRemaining > 0
                ? `~${formatTime(teardownEtaRemaining)} ETA`
                : 'Finishing up...'}
            </span>
          </div>

          <div className={styles.progressBar}>
            {TEARDOWN_STEPS.map((step, i) => (
              <div key={step.activeKey} className={styles.segmentWrap} data-tooltip={step.label}>
                <div
                  className={[
                    styles.segment,
                    i < teardownStepIndex ? styles.segmentDone : '',
                    i === teardownStepIndex ? styles.segmentActiveTeardown : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                />
              </div>
            ))}
          </div>

          <ul className={styles.progressList}>
            {TEARDOWN_STEPS.map((step, i) => {
              let cls = styles.progressItem;
              if (i < teardownStepIndex) cls += ` ${styles.progressItemDone}`;
              else if (i === teardownStepIndex) cls += ` ${styles.progressItemActiveTeardown}`;
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
