/** Request/response types for the ai-chat Lambda function. */

// ---------------------------------------------------------------------------
// Requests
// ---------------------------------------------------------------------------

export interface CreateChatSessionRequest {
  action: 'create-chat-session';
  visitor_email?: string;
}

export interface SendChatMessageRequest {
  action: 'send-chat-message';
  session_id: string;
  message: string;
}

// ---------------------------------------------------------------------------
// Responses
// ---------------------------------------------------------------------------

export interface CreateChatSessionResponse {
  session_id: string;
}

export interface SendChatMessageResponse {
  response: string;
  turn_number: number;
}

// ---------------------------------------------------------------------------
// Error responses
// ---------------------------------------------------------------------------

export type ChatErrorCode =
  | 'EMPTY_MESSAGE'
  | 'MESSAGE_TOO_LONG'
  | 'TURN_LIMIT_EXCEEDED'
  | 'INVALID_SESSION'
  | 'BUDGET_EXCEEDED'
  | 'LLM_ERROR'
  | 'UNKNOWN_ACTION'
  | 'INTERNAL_ERROR';

export interface ChatErrorResponse {
  error: ChatErrorCode;
  message: string;
}
