import type { NextAction } from '../types/api';
import styles from './NextActionsSection.module.css';

interface NextActionsSectionProps {
  nextAction: NextAction | null;
  isPuppet: boolean;
}

const ACTION_LABELS: Record<string, string> = {
  go_online: 'Go Online',
  go_offline: 'Go Offline',
  accept_reject_offer: 'Respond to Offer',
  request_ride: 'Request Ride',
  patience_timeout: 'Patience Timeout',
};

const ACTION_ICONS: Record<string, string> = {
  go_online: '🟢',
  go_offline: '🔴',
  accept_reject_offer: '📋',
  request_ride: '🚗',
  patience_timeout: '⏰',
};

function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return isoString;
  }
}

export function NextActionsSection({ nextAction, isPuppet }: NextActionsSectionProps) {
  if (isPuppet) {
    return (
      <div className={styles.section}>
        <h4>Next Actions</h4>
        <div className={styles.puppetMessage}>Puppet agent - manually controlled</div>
      </div>
    );
  }

  if (!nextAction) {
    return (
      <div className={styles.section}>
        <h4>Next Actions</h4>
        <div className={styles.noAction}>No scheduled actions</div>
      </div>
    );
  }

  const icon = ACTION_ICONS[nextAction.action_type] || '📌';
  const label = ACTION_LABELS[nextAction.action_type] || nextAction.action_type;
  const timestamp = formatTimestamp(nextAction.scheduled_at_iso);

  return (
    <div className={styles.section}>
      <h4>Next Actions</h4>
      <div className={styles.actionCard}>
        <div className={styles.actionHeader}>
          <span className={styles.actionIcon}>{icon}</span>
          <span className={styles.actionLabel}>{label}</span>
        </div>
        <div className={styles.timestamp}>
          <span className={styles.timestampLabel}>at</span>
          <span className={styles.timestampValue}>{timestamp}</span>
        </div>
        {nextAction.description && (
          <div className={styles.description}>{nextAction.description}</div>
        )}
      </div>
    </div>
  );
}
