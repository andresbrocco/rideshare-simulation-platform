import { useEffect, useRef } from 'react';
import type { ProviderInfo } from '../../types/chat';
import type { ChatMessageData } from './ChatMessage';
import { ChatMessage } from './ChatMessage';
import { CtaButtons } from './CtaButtons';
import { ProviderDropdown } from './ProviderDropdown';

const STARTER_QUESTIONS = [
  'How does deduplication work across the three layers (Stream Processor, Silver, Gold)?',
  'How do the same DBT models run against both DuckDB locally and Glue in production?',
  "What's the difference between the DBT data quality tests and the Great Expectations suites?",
  'What happens to analytics if a Kafka consumer group falls behind?',
  'How does the Bronze DLQ pipeline detect and route malformed events?',
  "How does visitor provisioning work when the platform isn't even running yet?",
] as const;

interface ChatPanelProps {
  messages: ChatMessageData[];
  isLoading: boolean;
  error: string | null;
  inputValue: string;
  onInputChange: (value: string) => void;
  onSend: (message: string) => void;
  onClose: () => void;
  showCta: boolean;
  onCtaDismissed: () => void;
  providers: ProviderInfo[];
  selectedProvider: string;
  onProviderChange: (provider: string) => void;
}

export function ChatPanel({
  messages,
  isLoading,
  error,
  inputValue,
  onInputChange,
  onSend,
  onClose,
  showCta,
  onCtaDismissed,
  providers,
  selectedProvider,
  onProviderChange,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = messagesEndRef.current;
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && inputValue.trim()) {
        onSend(inputValue.trim());
      }
    }
  }

  const showStarterQuestions = messages.length === 0 && !isLoading;

  return (
    <div className="chat-panel">
      <div className="chat-panel-header">
        <span className="chat-panel-title">Ask about this project</span>
        {providers.length > 0 && (
          <ProviderDropdown
            providers={providers}
            selectedProvider={selectedProvider}
            onProviderChange={onProviderChange}
            disabled={isLoading}
          />
        )}
        <button
          type="button"
          className="chat-panel-close"
          aria-label="Close chat"
          onClick={onClose}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            width="18"
            height="18"
            aria-hidden="true"
          >
            <path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        </button>
      </div>

      <div className="chat-panel-messages" role="log" aria-live="polite">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {isLoading && (
          <div className="chat-message chat-message--assistant" data-testid="typing-indicator">
            <div className="chat-message-bubble chat-typing-indicator">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="chat-error" role="alert">
          {error}
        </div>
      )}

      {showStarterQuestions && (
        <div className="chat-starter-questions">
          {STARTER_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              className="chat-starter-btn"
              onClick={() => onSend(question)}
            >
              {question}
            </button>
          ))}
        </div>
      )}

      {showCta ? (
        <CtaButtons onCtaDismissed={onCtaDismissed} />
      ) : (
        <div className="chat-panel-input-area">
          <textarea
            className="chat-input"
            value={inputValue}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question..."
            rows={2}
            disabled={isLoading}
            aria-label="Message input"
          />
          <button
            type="button"
            className="chat-send-btn"
            aria-label="Send"
            disabled={isLoading || !inputValue.trim()}
            onClick={() => {
              if (!isLoading && inputValue.trim()) {
                onSend(inputValue.trim());
              }
            }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              width="18"
              height="18"
              aria-hidden="true"
            >
              <path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
