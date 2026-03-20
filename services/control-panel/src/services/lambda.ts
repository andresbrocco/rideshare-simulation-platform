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

function isErrorResponse(data: unknown): data is { error: string } {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as { error: string }).error === 'string'
  );
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
      let errorData: unknown;
      try {
        errorData = await response.json();
      } catch {
        throw new LambdaServiceError(`Lambda returned ${response.status}`, 'LAMBDA_ERROR');
      }
      if (isErrorResponse(errorData)) {
        throw new LambdaServiceError(errorData.error, 'LAMBDA_ERROR');
      }
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
  dbtRunner: string = 'duckdb',
  email?: string
): Promise<DeployResponse> {
  const payload: Record<string, string> = {
    action: 'deploy',
    api_key: apiKey,
    dbt_runner: dbtRunner,
  };
  if (email) payload.email = email;
  return callLambda(payload, isDeployResponse, 'Deployment service');
}

export async function checkDeployStatus(apiKey: string): Promise<StatusResponse> {
  return callLambda({ action: 'status', api_key: apiKey }, isStatusResponse, 'Status service');
}

export interface SessionStatusResponse {
  active: boolean;
  deploying?: boolean;
  tearing_down?: boolean;
  tearing_down_at?: number;
  remaining_seconds?: number;
  deployed_at?: number;
  deadline?: number;
  elapsed_seconds?: number;
  cost_so_far?: number;
}

export interface TeardownStepInfo {
  name: string;
  status: 'completed' | 'in_progress' | 'pending';
}

export interface TeardownStatusResponse {
  tearing_down: boolean;
  run_id: number | null;
  workflow_status: string;
  workflow_conclusion: string | null;
  current_step: number;
  total_steps: number;
  steps: TeardownStepInfo[];
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

function isTeardownStatusResponse(data: unknown): data is TeardownStatusResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as TeardownStatusResponse).tearing_down === 'boolean' &&
    typeof (data as TeardownStatusResponse).current_step === 'number' &&
    typeof (data as TeardownStatusResponse).total_steps === 'number' &&
    Array.isArray((data as TeardownStatusResponse).steps)
  );
}

export async function getTeardownStatus(): Promise<TeardownStatusResponse> {
  return callLambda(
    { action: 'teardown-status' },
    isTeardownStatusResponse,
    'Teardown status service'
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

export async function extendSession(
  apiKey: string,
  email?: string
): Promise<SessionAdjustResponse> {
  const payload: Record<string, string> = { action: 'extend-session', api_key: apiKey };
  if (email) payload.email = email;
  return callLambda(payload, isSessionAdjustResponse, 'Session extend service');
}

export async function shrinkSession(
  apiKey: string,
  email?: string
): Promise<SessionAdjustResponse> {
  const payload: Record<string, string> = { action: 'shrink-session', api_key: apiKey };
  if (email) payload.email = email;
  return callLambda(payload, isSessionAdjustResponse, 'Session shrink service');
}

export interface ProvisionVisitorResponse {
  provisioned: boolean;
  email_sent: boolean;
  failures: string[];
  services_provisioned?: string[];
}

function isProvisionVisitorResponse(data: unknown): data is ProvisionVisitorResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as ProvisionVisitorResponse).provisioned === 'boolean' &&
    typeof (data as ProvisionVisitorResponse).email_sent === 'boolean' &&
    Array.isArray((data as ProvisionVisitorResponse).failures)
  );
}

export async function provisionVisitor(email: string): Promise<ProvisionVisitorResponse> {
  const lambdaUrl = getLambdaUrl();

  if (!lambdaUrl) {
    throw new LambdaServiceError('Lambda URL not configured', 'INVALID_RESPONSE');
  }

  let response: Response;
  try {
    response = await fetch(lambdaUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'provision-visitor', email }),
    });
  } catch {
    throw new LambdaServiceError('Visitor provisioning service unavailable', 'NETWORK_ERROR');
  }

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      throw new LambdaServiceError(`Lambda returned ${response.status}`, 'LAMBDA_ERROR');
    }
    if (isErrorResponse(errorData)) {
      throw new LambdaServiceError(errorData.error, 'LAMBDA_ERROR');
    }
    throw new LambdaServiceError(`Lambda returned ${response.status}`, 'LAMBDA_ERROR');
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new LambdaServiceError('Invalid response format from Lambda', 'INVALID_RESPONSE');
  }

  if (!isProvisionVisitorResponse(data)) {
    throw new LambdaServiceError('Invalid response format from Lambda', 'INVALID_RESPONSE');
  }

  return data;
}

export interface VisitorLoginResponse {
  api_key: string;
  role: string;
  email: string;
}

function isVisitorLoginResponse(data: unknown): data is VisitorLoginResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as VisitorLoginResponse).api_key === 'string' &&
    typeof (data as VisitorLoginResponse).role === 'string' &&
    typeof (data as VisitorLoginResponse).email === 'string'
  );
}

export async function visitorLogin(email: string, password: string): Promise<VisitorLoginResponse> {
  const lambdaUrl = getLambdaUrl();

  if (!lambdaUrl) {
    throw new LambdaServiceError('Lambda URL not configured', 'INVALID_RESPONSE');
  }

  let response: Response;
  try {
    response = await fetch(lambdaUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'visitor-login', email, password }),
    });
  } catch {
    throw new LambdaServiceError('Authentication service unavailable', 'NETWORK_ERROR');
  }

  if (response.status === 401) {
    throw new LambdaServiceError('Invalid email or password', 'LAMBDA_ERROR');
  }

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      throw new LambdaServiceError(`Lambda returned ${response.status}`, 'LAMBDA_ERROR');
    }
    if (isErrorResponse(errorData)) {
      throw new LambdaServiceError(errorData.error, 'LAMBDA_ERROR');
    }
    throw new LambdaServiceError(`Lambda returned ${response.status}`, 'LAMBDA_ERROR');
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new LambdaServiceError('Invalid response format from Lambda', 'INVALID_RESPONSE');
  }

  if (!isVisitorLoginResponse(data)) {
    throw new LambdaServiceError('Invalid response format from Lambda', 'INVALID_RESPONSE');
  }

  return data;
}

export interface DeployProgressResponse {
  services: Record<string, boolean>;
  all_ready: boolean;
}

function isDeployProgressResponse(data: unknown): data is DeployProgressResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as DeployProgressResponse).services === 'object' &&
    typeof (data as DeployProgressResponse).all_ready === 'boolean'
  );
}

export async function getDeployProgress(): Promise<DeployProgressResponse> {
  return callLambda({ action: 'get-deploy-progress' }, isDeployProgressResponse, 'Deploy progress');
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
