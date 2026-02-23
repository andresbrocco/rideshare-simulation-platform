import type { ActionHistoryEntry } from '../types/api';
import styles from './PreviousActionsSection.module.css';

interface PreviousActionsSectionProps {
  actionHistory: ActionHistoryEntry[];
  isPuppet: boolean;
}

const ACTION_LABELS: Record<string, string> = {
  go_online: 'Went Online',
  go_offline: 'Went Offline',
  accept_trip: 'Accepted Offer',
  reject_offer: 'Rejected Offer',
  offer_expired: 'Offer Expired',
  start_pickup: 'Started Pickup',
  start_trip: 'Started Trip',
  complete_trip: 'Completed Trip',
  start_repositioning: 'Driving Closer to Home',
  end_repositioning: 'Arrived Near Home',
  repositioning_failed: 'Repositioning Failed',
  request_trip: 'Requested Ride',
  driver_assigned: 'Driver Assigned',
  cancel_trip: 'Trip Cancelled',
};

const ACTION_ICONS: Record<string, string> = {
  go_online: '🟢',
  go_offline: '🔴',
  accept_trip: '✅',
  reject_offer: '❌',
  offer_expired: '⏰',
  start_pickup: '📍',
  start_trip: '🚗',
  complete_trip: '🏁',
  start_repositioning: '🏠',
  end_repositioning: '🏠',
  repositioning_failed: '⚠️',
  request_trip: '🙋',
  driver_assigned: '🤝',
  cancel_trip: '🚫',
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

export function PreviousActionsSection({ actionHistory, isPuppet }: PreviousActionsSectionProps) {
  if (isPuppet) {
    return null;
  }

  return (
    <div className={styles.section}>
      <h4>Previous Actions</h4>
      {actionHistory.length === 0 ? (
        <div className={styles.noHistory}>No actions recorded yet</div>
      ) : (
        <ul className={styles.list}>
          {actionHistory.map((entry, index) => {
            const icon = ACTION_ICONS[entry.action_type] || '📌';
            const label = ACTION_LABELS[entry.action_type] || entry.action_type;
            const timestamp = formatTimestamp(entry.occurred_at_iso);

            return (
              <li key={index} className={styles.item}>
                <span className={styles.itemAction}>
                  <span className={styles.itemIcon}>{icon}</span>
                  <span className={styles.itemLabel}>{label}</span>
                </span>
                <span className={styles.itemTimestamp}>{timestamp}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
