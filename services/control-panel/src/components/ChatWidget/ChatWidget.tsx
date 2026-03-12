import { useState } from 'react';
import { createChatSession, sendChatMessage, ChatServiceError } from '../../services/chat';
import type { ChatServiceErrorCode } from '../../services/chat';
import { ChatButton } from './ChatButton';
import { ChatPanel } from './ChatPanel';
import type { ChatMessageData } from './ChatMessage';
import './ChatWidget.css';

// ---------------------------------------------------------------------------
// Error message mapping
// ---------------------------------------------------------------------------

const ERROR_MESSAGES: Record<string, string> = {
  BUDGET_EXCEEDED: 'The chat has reached its daily limit. Please try again tomorrow.',
  LLM_ERROR: 'Something went wrong. Please try again.',
  NETWORK_ERROR: 'Unable to connect. Please check your connection.',
  INTERNAL_ERROR: 'An unexpected error occurred. Please try again.',
};

function getErrorMessage(err: ChatServiceError): string {
  return ERROR_MESSAGES[err.code] ?? err.message ?? 'An unexpected error occurred.';
}

// ---------------------------------------------------------------------------
// CTA configuration
// ---------------------------------------------------------------------------

const CTA_TURN = 5;
const CTA_MESSAGE_CONTENT =
  "I see you're enjoying this. Do you want to book a video call with my creator, Andre Sbrocco? Drop him an e-mail!";

// ---------------------------------------------------------------------------
// ChatWidget component
// ---------------------------------------------------------------------------

interface ChatWidgetProps {
  visitorEmail: string | null;
}

export function ChatWidget({ visitorEmail }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [ctaShown, setCtaShown] = useState(false);
  const [showCta, setShowCta] = useState(false);

  function generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  async function handleSend(text: string) {
    if (!text.trim() || isLoading) return;

    const userMessage: ChatMessageData = {
      id: generateId(),
      role: 'user',
      content: text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      let activeSessionId = sessionId;

      // Lazy session creation on first message
      if (activeSessionId === null) {
        const sessionResponse = await createChatSession(visitorEmail ?? undefined);
        activeSessionId = sessionResponse.session_id;
        setSessionId(activeSessionId);
      }

      let messageResponse;
      try {
        messageResponse = await sendChatMessage(activeSessionId, text);
      } catch (sendErr) {
        if (
          sendErr instanceof ChatServiceError &&
          (sendErr.code as ChatServiceErrorCode) === 'INVALID_SESSION'
        ) {
          // Auto-retry: create a fresh session and retry
          const retrySession = await createChatSession(visitorEmail ?? undefined);
          activeSessionId = retrySession.session_id;
          setSessionId(activeSessionId);
          // If retry also throws, propagate to outer catch
          messageResponse = await sendChatMessage(activeSessionId, text);
        } else {
          throw sendErr;
        }
      }

      const assistantMessage: ChatMessageData = {
        id: generateId(),
        role: 'assistant',
        content: messageResponse.response,
      };

      if (messageResponse.turn_number === CTA_TURN && !ctaShown) {
        const ctaMessage: ChatMessageData = {
          id: generateId(),
          role: 'assistant',
          content: CTA_MESSAGE_CONTENT,
          isCtaMessage: true,
        };
        setMessages((prev) => [...prev, assistantMessage, ctaMessage]);
        setCtaShown(true);
        setShowCta(true);
      } else {
        setMessages((prev) => [...prev, assistantMessage]);
      }
    } catch (err) {
      if (err instanceof ChatServiceError) {
        setError(getErrorMessage(err));
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className={`chat-widget chat-widget--${isOpen ? 'open' : 'closed'}`}>
      {isOpen ? (
        <ChatPanel
          messages={messages}
          isLoading={isLoading}
          error={error}
          inputValue={inputValue}
          onInputChange={setInputValue}
          onSend={handleSend}
          onClose={() => setIsOpen(false)}
          showCta={showCta}
          onCtaDismissed={() => setShowCta(false)}
        />
      ) : (
        <ChatButton onClick={() => setIsOpen(true)} />
      )}
    </div>
  );
}
