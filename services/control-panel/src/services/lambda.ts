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

export async function triggerDeploy(apiKey: string): Promise<DeployResponse> {
  return callLambda({ action: 'deploy', api_key: apiKey }, isDeployResponse, 'Deployment service');
}

export async function checkDeployStatus(apiKey: string): Promise<StatusResponse> {
  return callLambda({ action: 'status', api_key: apiKey }, isStatusResponse, 'Status service');
}
