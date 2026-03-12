// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ANDRE_EMAIL = 'andresbroco@gmail.com';
const MAILTO_URL = `mailto:${ANDRE_EMAIL}`;

// ---------------------------------------------------------------------------
// CtaButtons component
// ---------------------------------------------------------------------------

interface CtaButtonsProps {
  onCtaDismissed: () => void;
}

export function CtaButtons({ onCtaDismissed }: CtaButtonsProps) {
  return (
    <div className="chat-cta-buttons" data-testid="cta-buttons">
      <a
        href={MAILTO_URL}
        className="chat-cta-btn chat-cta-btn--email"
        onClick={onCtaDismissed}
        data-testid="cta-email-btn"
      >
        Email Andre
      </a>
      <button
        type="button"
        className="chat-cta-btn chat-cta-btn--continue"
        onClick={onCtaDismissed}
        data-testid="cta-continue-btn"
      >
        Continue chatting
      </button>
    </div>
  );
}
