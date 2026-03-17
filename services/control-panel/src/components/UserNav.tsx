import { useState, useCallback, useEffect, useRef } from 'react';
import styles from './UserNav.module.css';

interface UserNavProps {
  email: string | null;
  role: 'admin' | 'viewer' | null;
  onSignOut: () => void;
  landingUrl?: string;
}

function ScrollingEmail({ email }: { email: string }) {
  const outerRef = useRef<HTMLSpanElement>(null);
  const innerRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const outer = outerRef.current;
    const inner = innerRef.current;
    if (!outer || !inner) return;
    const overflow = inner.scrollWidth - outer.clientWidth;
    inner.style.setProperty('--email-scroll-distance', overflow > 0 ? `-${overflow}px` : '0px');
    inner.style.animationPlayState = overflow > 0 ? 'running' : 'paused';
  }, [email]);

  return (
    <span className={styles.email} title={email} ref={outerRef}>
      <span className={styles.emailInner} ref={innerRef}>
        {email}
      </span>
    </span>
  );
}

export function UserNav({ email, role, onSignOut, landingUrl }: UserNavProps) {
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);
  const avatarRef = useRef<HTMLButtonElement>(null);

  const toggleProfile = useCallback(() => {
    setProfileOpen((prev) => !prev);
  }, []);

  useEffect(() => {
    if (!profileOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setProfileOpen(false);
        avatarRef.current?.focus();
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [profileOpen]);

  // Not authenticated — render nothing
  if (!email && !role) return null;

  const landingIcon = landingUrl ? (
    <a
      href={landingUrl}
      className={styles.landingLink}
      title="Back to landing"
      aria-label="Back to landing page"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M8 1.5L1.5 7H4v6.5h3V10h2v3.5h3V7h2.5L8 1.5Z"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />
      </svg>
    </a>
  ) : null;

  const authContent = (
    <>
      {email && <ScrollingEmail email={email} />}
      {role && <span className={styles.roleBadge}>{role}</span>}
      <button type="button" className={styles.signOutBtn} onClick={onSignOut}>
        Sign Out
      </button>
    </>
  );

  return (
    <div className={styles.container}>
      {landingIcon}

      {/* Desktop: horizontal row */}
      <div className={styles.desktopContent}>{authContent}</div>

      {/* Mobile: avatar + dropdown */}
      <div className={styles.mobileContent} ref={profileRef}>
        <button
          type="button"
          className={styles.avatar}
          onClick={toggleProfile}
          ref={avatarRef}
          aria-expanded={profileOpen}
          aria-haspopup="true"
          aria-label="Account menu"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <circle cx="10" cy="7" r="3.5" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M3 17.5c0-3.5 3.1-6 7-6s7 2.5 7 6"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          <span className={styles.avatarDot} />
        </button>
        {profileOpen && (
          <div className={styles.dropdown} role="menu">
            {authContent}
          </div>
        )}
      </div>
    </div>
  );
}
