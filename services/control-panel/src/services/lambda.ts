function getLambdaUrl(): string | undefined {
  return import.meta.env.VITE_LAMBDA_URL;
}

export interface ValidateResponse {
  valid: boolean;
  error?: string;
}

export interface DeployResponse {
  triggered: boolean;
  error?: string;
  workflow_run_id?: string;
}

export interface StatusResponse {
  status: 'queued' | 'in_progress' | 'completed';
  conclusion?: 'success' | 'failure' | 'cancelled' | 'skipped';
  error?: string;
}

export type LambdaErrorCode = 'NETWORK_ERROR' | 'INVALID_RESPONSE' | 'LAMBDA_ERROR';

export class LambdaServiceError extends Error {
  readonly code: LambdaErrorCode;

  constructor(message: string, code: LambdaErrorCode) {
    super(message);
    this.name = 'LambdaServiceError';
    this.code = code;
  }
}

async function callLambda<T>(
  payload: Record<string, string>,
  validateResponse: (data: unknown) => data is T,
  serviceName: string
): Promise<T> {
  const lambdaUrl = getLambdaUrl();

  if (!lambdaUrl) {
    throw new LambdaServiceError('Lambda URL not configured', 'INVALID_RESPONSE');
  }

  try {
    const response = await fetch(lambdaUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new LambdaServiceError(`Lambda returned ${response.status}`, 'LAMBDA_ERROR');
    }

    const data: unknown = await response.json();

    if (!validateResponse(data)) {
      throw new LambdaServiceError('Invalid response format from Lambda', 'INVALID_RESPONSE');
    }

    return data;
  } catch (error) {
    if (error instanceof LambdaServiceError) {
      throw error;
    }

    throw new LambdaServiceError(`${serviceName} unavailable`, 'NETWORK_ERROR');
  }
}

function isValidateResponse(data: unknown): data is ValidateResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as ValidateResponse).valid === 'boolean'
  );
}

function isDeployResponse(data: unknown): data is DeployResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as DeployResponse).triggered === 'boolean'
  );
}

function isStatusResponse(data: unknown): data is StatusResponse {
  return (
    typeof data === 'object' && data !== null && typeof (data as StatusResponse).status === 'string'
  );
}

export async function validateApiKey(apiKey: string): Promise<ValidateResponse> {
  return callLambda(
    { action: 'validate', api_key: apiKey },
    isValidateResponse,
    'Authentication service'
  );
}

export async function triggerDeploy(
  apiKey: string,
  dbtRunner: string = 'duckdb'
): Promise<DeployResponse> {
  return callLambda(
    { action: 'deploy', api_key: apiKey, dbt_runner: dbtRunner },
    isDeployResponse,
    'Deployment service'
  );
}

export async function checkDeployStatus(apiKey: string): Promise<StatusResponse> {
  return callLambda({ action: 'status', api_key: apiKey }, isStatusResponse, 'Status service');
}

export interface SessionStatusResponse {
  active: boolean;
  deploying?: boolean;
  remaining_seconds?: number;
  deployed_at?: number;
  deadline?: number;
  elapsed_seconds?: number;
  cost_so_far?: number;
}

export interface SessionAdjustResponse {
  success: boolean;
  remaining_seconds: number;
  deadline: number;
  error?: string;
}

function isSessionStatusResponse(data: unknown): data is SessionStatusResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as SessionStatusResponse).active === 'boolean'
  );
}

function isSessionAdjustResponse(data: unknown): data is SessionAdjustResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as SessionAdjustResponse).success === 'boolean' &&
    typeof (data as SessionAdjustResponse).remaining_seconds === 'number' &&
    typeof (data as SessionAdjustResponse).deadline === 'number'
  );
}

export async function getSessionStatus(): Promise<SessionStatusResponse> {
  return callLambda(
    { action: 'session-status' },
    isSessionStatusResponse,
    'Session status service'
  );
}

export async function activateSession(apiKey: string): Promise<SessionAdjustResponse> {
  return callLambda(
    { action: 'activate-session', api_key: apiKey },
    isSessionAdjustResponse,
    'Session activate service'
  );
}

export async function extendSession(apiKey: string): Promise<SessionAdjustResponse> {
  return callLambda(
    { action: 'extend-session', api_key: apiKey },
    isSessionAdjustResponse,
    'Session extend service'
  );
}

export async function shrinkSession(apiKey: string): Promise<SessionAdjustResponse> {
  return callLambda(
    { action: 'shrink-session', api_key: apiKey },
    isSessionAdjustResponse,
    'Session shrink service'
  );
}

export type ServiceId =
  | 'simulation_api'
  | 'grafana'
  | 'airflow'
  | 'trino'
  | 'prometheus'
  | 'control_panel';

export type ServiceHealthMap = Record<ServiceId, boolean>;

export const ALL_SERVICES_DOWN: ServiceHealthMap = {
  simulation_api: false,
  grafana: false,
  airflow: false,
  trino: false,
  prometheus: false,
  control_panel: false,
};

interface ServiceHealthResponse {
  services: Record<string, boolean>;
}

function isServiceHealthResponse(data: unknown): data is ServiceHealthResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as ServiceHealthResponse).services === 'object' &&
    (data as ServiceHealthResponse).services !== null
  );
}

export async function getServiceHealth(): Promise<ServiceHealthMap> {
  const response = await callLambda(
    { action: 'service-health' },
    isServiceHealthResponse,
    'Service health'
  );
  const sim = !!response.services['simulation_api'];
  return {
    simulation_api: sim,
    grafana: !!response.services['grafana'],
    airflow: !!response.services['airflow'],
    trino: !!response.services['trino'],
    prometheus: !!response.services['prometheus'],
    control_panel: sim,
  };
}
