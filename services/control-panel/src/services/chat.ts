import type {
  ChatErrorCode,
  ChatErrorResponse,
  CreateChatSessionResponse,
  ListProvidersResponse,
  ProviderInfo,
  SendChatMessageResponse,
} from '../types/chat';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

function getChatLambdaUrl(): string | undefined {
  return import.meta.env.VITE_CHAT_LAMBDA_URL;
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export type ChatServiceErrorCode = ChatErrorCode | 'NETWORK_ERROR' | 'INVALID_RESPONSE';

export class ChatServiceError extends Error {
  readonly code: ChatServiceErrorCode;

  constructor(message: string, code: ChatServiceErrorCode) {
    super(message);
    this.name = 'ChatServiceError';
    this.code = code;
  }
}

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

function isCreateChatSessionResponse(data: unknown): data is CreateChatSessionResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as CreateChatSessionResponse).session_id === 'string'
  );
}

function isSendChatMessageResponse(data: unknown): data is SendChatMessageResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as SendChatMessageResponse).response === 'string' &&
    typeof (data as SendChatMessageResponse).turn_number === 'number'
  );
}

function isListProvidersResponse(data: unknown): data is ListProvidersResponse {
  if (typeof data !== 'object' || data === null) return false;
  const obj = data as ListProvidersResponse;
  return (
    Array.isArray(obj.providers) &&
    obj.providers.every(
      (p: unknown) =>
        typeof p === 'object' &&
        p !== null &&
        typeof (p as ProviderInfo).name === 'string' &&
        typeof (p as ProviderInfo).default === 'boolean'
    )
  );
}

function isChatErrorResponse(data: unknown): data is ChatErrorResponse {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as ChatErrorResponse).error === 'string' &&
    typeof (data as ChatErrorResponse).message === 'string'
  );
}

// ---------------------------------------------------------------------------
// Internal helper
// ---------------------------------------------------------------------------

async function callChatLambda<T>(
  payload: Record<string, unknown>,
  validateResponse: (data: unknown) => data is T,
  serviceName: string
): Promise<T> {
  const chatUrl = getChatLambdaUrl();

  if (!chatUrl) {
    throw new ChatServiceError('Chat Lambda URL not configured', 'INVALID_RESPONSE');
  }

  let response: Response;
  try {
    response = await fetch(chatUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ChatServiceError(`${serviceName} unavailable`, 'NETWORK_ERROR');
  }

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      throw new ChatServiceError(`Lambda returned ${response.status}`, 'INVALID_RESPONSE');
    }

    if (isChatErrorResponse(errorData)) {
      throw new ChatServiceError(errorData.message, errorData.error);
    }

    throw new ChatServiceError(`Lambda returned ${response.status}`, 'INVALID_RESPONSE');
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new ChatServiceError('Invalid response format from Lambda', 'INVALID_RESPONSE');
  }

  if (!validateResponse(data)) {
    throw new ChatServiceError('Invalid response format from Lambda', 'INVALID_RESPONSE');
  }

  return data;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function createChatSession(visitorEmail?: string): Promise<CreateChatSessionResponse> {
  const payload: Record<string, unknown> = { action: 'create-chat-session' };
  if (visitorEmail) {
    payload.visitor_email = visitorEmail;
  }

  return callChatLambda(payload, isCreateChatSessionResponse, 'Chat session service');
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
  provider?: string
): Promise<SendChatMessageResponse> {
  const payload: Record<string, unknown> = {
    action: 'send-chat-message',
    session_id: sessionId,
    message,
  };
  if (provider) {
    payload.provider = provider;
  }

  return callChatLambda(payload, isSendChatMessageResponse, 'Chat message service');
}

export async function listProviders(): Promise<ListProvidersResponse> {
  return callChatLambda(
    { action: 'list-providers' },
    isListProvidersResponse,
    'List providers service'
  );
}
