interface ChatButtonProps {
  onClick: () => void;
}

export function ChatButton({ onClick }: ChatButtonProps) {
  return (
    <button type="button" className="chat-fab" aria-label="Open chat" onClick={onClick}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        width="24"
        height="24"
        aria-hidden="true"
      >
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
      </svg>
      <span className="chat-fab-sparkle" aria-hidden="true">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">
          <defs>
            <linearGradient id="sparkle-sweep" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#00ff88" stopOpacity="0.6" />
              <stop offset="40%" stopColor="#ffffff" stopOpacity="1" />
              <stop offset="60%" stopColor="#ffffff" stopOpacity="1" />
              <stop offset="100%" stopColor="#00ff88" stopOpacity="0.6" />
              <animateTransform
                attributeName="gradientTransform"
                type="translate"
                from="-1 -1"
                to="1 1"
                dur="2s"
                repeatCount="indefinite"
              />
            </linearGradient>
          </defs>
          <path
            d="M12 0 L14.59 8.41 L24 12 L14.59 15.59 L12 24 L9.41 15.59 L0 12 L9.41 8.41 Z"
            fill="url(#sparkle-sweep)"
          />
        </svg>
      </span>
    </button>
  );
}
