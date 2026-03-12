export interface ChatMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isCtaMessage?: boolean;
}

interface ChatMessageProps {
  message: ChatMessageData;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  return (
    <div className={`chat-message chat-message--${isUser ? 'user' : 'assistant'}`}>
      <div className="chat-message-bubble">{message.content}</div>
    </div>
  );
}
