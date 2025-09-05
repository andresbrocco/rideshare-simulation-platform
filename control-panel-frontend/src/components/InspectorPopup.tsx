import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import type { Driver, Rider, ZoneData, DriverState, RiderState } from '../types/api';
import { NextActionsSection } from './NextActionsSection';
import styles from './InspectorPopup.module.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Friendly labels for trip states
function formatTripState(state: string): string {
  const stateLabels: Record<string, string> = {
    requested: 'Waiting for match',
    offer_sent: 'Offer sent to driver',
    offer_expired: 'Offer expired',
    offer_rejected: 'Offer rejected',
    matched: 'Driver assigned',
    driver_en_route: 'Driver en route',
    driver_arrived: 'Driver arrived',
    started: 'In progress',
    completed: 'Completed',
    cancelled: 'Cancelled',
  };
  return stateLabels[state] || state;
}

export type InspectedEntity =
  | { type: 'zone'; data: ZoneData }
  | { type: 'driver'; data: Driver }
  | { type: 'rider'; data: Rider }
  | null;

interface InspectorPopupProps {
  entity: InspectedEntity;
  x: number;
  y: number;
  onClose: () => void;
  onToggleDriverStatus?: (driverId: string, goOnline: boolean) => Promise<void>;
  onRequestRiderTrip?: (riderId: string, riderName: string) => void;
  // Puppet driver actions
  onAcceptOffer?: (driverId: string) => Promise<boolean>;
  onRejectOffer?: (driverId: string) => Promise<boolean>;
  onArriveAtPickup?: (driverId: string) => Promise<boolean>;
  onStartTrip?: (driverId: string) => Promise<boolean>;
  onCompleteTrip?: (driverId: string) => Promise<boolean>;
  onCancelDriverTrip?: (driverId: string) => Promise<boolean>;
  // Puppet rider actions
  onCancelRiderTrip?: (riderId: string) => Promise<boolean>;
}

export default function InspectorPopup({
  entity,
  x,
  y,
  onClose,
  onToggleDriverStatus,
  onRequestRiderTrip,
  onAcceptOffer,
  onRejectOffer,
  onArriveAtPickup,
  onStartTrip,
  onCompleteTrip,
  onCancelDriverTrip,
  onCancelRiderTrip,
}: InspectorPopupProps) {
  const [detailedDriverState, setDetailedDriverState] = useState<DriverState | null>(null);
  const [detailedRiderState, setDetailedRiderState] = useState<RiderState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Drag state
  const [isDragging, setIsDragging] = useState(false);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const [position, setPosition] = useState({ x, y });

  // Minimize state
  const [isMinimized, setIsMinimized] = useState(false);

  // Track mounted state for async operations
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Fetch detailed state when entity changes, with polling for live updates
  useEffect(() => {
    if (!entity) {
      setDetailedDriverState(null);
      setDetailedRiderState(null);
      setError(null);
      return;
    }

    const controller = new AbortController();
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const fetchDetails = async (isInitialLoad: boolean) => {
      // Only show loading spinner on initial load, not on refreshes
      if (isInitialLoad) {
        setLoading(true);
        setError(null);
      }

      try {
        const apiKey = sessionStorage.getItem('apiKey') || '';

        if (entity.type === 'driver') {
          const response = await fetch(`${API_URL}/agents/drivers/${entity.data.id}`, {
            headers: { 'X-API-Key': apiKey },
            signal: controller.signal,
          });
          if (controller.signal.aborted) return;
          if (response.ok) {
            const state = await response.json();
            if (!controller.signal.aborted) {
              setDetailedDriverState(state);
              setDetailedRiderState(null);
            }
          } else {
            if (!controller.signal.aborted && isInitialLoad) {
              setError('Failed to fetch driver details');
            }
          }
        } else if (entity.type === 'rider') {
          const response = await fetch(`${API_URL}/agents/riders/${entity.data.id}`, {
            headers: { 'X-API-Key': apiKey },
            signal: controller.signal,
          });
          if (controller.signal.aborted) return;
          if (response.ok) {
            const state = await response.json();
            if (!controller.signal.aborted) {
              setDetailedRiderState(state);
              setDetailedDriverState(null);
            }
          } else {
            if (!controller.signal.aborted && isInitialLoad) {
              setError('Failed to fetch rider details');
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return; // Ignore abort errors
        }
        if (!controller.signal.aborted && isInitialLoad) {
          setError('Network error');
        }
      } finally {
        if (!controller.signal.aborted && isInitialLoad) {
          setLoading(false);
        }
      }
    };

    if (entity.type === 'driver' || entity.type === 'rider') {
      fetchDetails(true); // Initial fetch

      // Poll every 3 seconds to refresh statistics (skip if minimized)
      intervalId = setInterval(() => {
        if (!isMinimized) {
          fetchDetails(false);
        }
      }, 3000);
    }

    return () => {
      controller.abort();
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [entity, isMinimized]);

  const { adjustedX, adjustedY } = useMemo(() => {
    const popupWidth = 320;
    const popupHeight = window.innerHeight * 0.8; // Match CSS max-height: 80vh
    const padding = 20;

    let newX = x;
    let newY = y;

    if (x + popupWidth + padding > window.innerWidth) {
      newX = window.innerWidth - popupWidth - padding;
    }
    if (y + popupHeight + padding > window.innerHeight) {
      newY = window.innerHeight - popupHeight - padding;
    }

    return { adjustedX: newX, adjustedY: newY };
  }, [x, y]);

  // Reset position and restore when entity changes (new popup location)
  useEffect(() => {
    setPosition({ x: adjustedX, y: adjustedY });
    setIsMinimized(false); // Auto-restore when clicking a different entity
  }, [adjustedX, adjustedY]);

  // Get entity title for minimized header
  const getEntityTitle = useCallback(() => {
    if (!entity) return '';
    if (entity.type === 'zone') {
      return `Zone: ${entity.data.feature.properties.name}`;
    }
    if (entity.type === 'driver') {
      if (detailedDriverState?.dna) {
        return `${detailedDriverState.dna.first_name} ${detailedDriverState.dna.last_name}`;
      }
      return `Driver: ${entity.data.id.slice(0, 8)}...`;
    }
    if (entity.type === 'rider') {
      if (detailedRiderState?.dna) {
        return `${detailedRiderState.dna.first_name} ${detailedRiderState.dna.last_name}`;
      }
      return `Rider: ${entity.data.id.slice(0, 8)}...`;
    }
    return '';
  }, [entity, detailedDriverState, detailedRiderState]);

  // Refetch detailed state (for after actions)
  const refetchState = useCallback(async () => {
    if (!entity) return;
    const apiKey = sessionStorage.getItem('apiKey') || '';

    try {
      if (entity.type === 'driver') {
        const response = await fetch(`${API_URL}/agents/drivers/${entity.data.id}`, {
          headers: { 'X-API-Key': apiKey },
        });
        if (response.ok && isMountedRef.current) {
          const state = await response.json();
          if (isMountedRef.current) {
            setDetailedDriverState(state);
          }
        }
      } else if (entity.type === 'rider') {
        const response = await fetch(`${API_URL}/agents/riders/${entity.data.id}`, {
          headers: { 'X-API-Key': apiKey },
        });
        if (response.ok && isMountedRef.current) {
          const state = await response.json();
          if (isMountedRef.current) {
            setDetailedRiderState(state);
          }
        }
      }
    } catch {
      // Ignore errors during refetch - state will be stale but not cause issues
    }
  }, [entity]);

  // Handle driver status toggle
  const handleToggleDriverStatus = useCallback(async () => {
    if (!entity || entity.type !== 'driver' || !onToggleDriverStatus || !detailedDriverState)
      return;

    const isOnline = detailedDriverState.status === 'online';
    setActionLoading(true);
    try {
      await onToggleDriverStatus(entity.data.id, !isOnline);
      await refetchState();
    } finally {
      setActionLoading(false);
    }
  }, [entity, onToggleDriverStatus, detailedDriverState, refetchState]);

  // Handle rider trip request
  const handleRequestTrip = useCallback(() => {
    if (!entity || entity.type !== 'rider' || !onRequestRiderTrip) return;
    const riderName = detailedRiderState?.dna
      ? `${detailedRiderState.dna.first_name} ${detailedRiderState.dna.last_name}`
      : `Rider ${entity.data.id.slice(0, 8)}`;
    onRequestRiderTrip(entity.data.id, riderName);
  }, [entity, onRequestRiderTrip, detailedRiderState]);

  // --- Puppet Driver Action Handlers ---

  const handleAcceptOffer = useCallback(async () => {
    if (!entity || entity.type !== 'driver' || !onAcceptOffer) return;
    setActionLoading(true);
    try {
      await onAcceptOffer(entity.data.id);
      await refetchState();
    } finally {
      setActionLoading(false);
    }
  }, [entity, onAcceptOffer, refetchState]);

  const handleRejectOffer = useCallback(async () => {
    if (!entity || entity.type !== 'driver' || !onRejectOffer) return;
    setActionLoading(true);
    try {
      await onRejectOffer(entity.data.id);
      await refetchState();
    } finally {
      setActionLoading(false);
    }
  }, [entity, onRejectOffer, refetchState]);

  const handleArriveAtPickup = useCallback(async () => {
    if (!entity || entity.type !== 'driver' || !onArriveAtPickup) return;
    setActionLoading(true);
    try {
      await onArriveAtPickup(entity.data.id);
      await refetchState();
    } finally {
      setActionLoading(false);
    }
  }, [entity, onArriveAtPickup, refetchState]);

  const handleStartTrip = useCallback(async () => {
    if (!entity || entity.type !== 'driver' || !onStartTrip) return;
    setActionLoading(true);
    try {
      await onStartTrip(entity.data.id);
      await refetchState();
    } finally {
      setActionLoading(false);
    }
  }, [entity, onStartTrip, refetchState]);

  const handleCompleteTrip = useCallback(async () => {
    if (!entity || entity.type !== 'driver' || !onCompleteTrip) return;
    setActionLoading(true);
    try {
      await onCompleteTrip(entity.data.id);
      await refetchState();
    } finally {
      setActionLoading(false);
    }
  }, [entity, onCompleteTrip, refetchState]);

  const handleCancelDriverTrip = useCallback(async () => {
    if (!entity || entity.type !== 'driver' || !onCancelDriverTrip) return;
    setActionLoading(true);
    try {
      await onCancelDriverTrip(entity.data.id);
      await refetchState();
    } finally {
      setActionLoading(false);
    }
  }, [entity, onCancelDriverTrip, refetchState]);

  // --- Puppet Rider Action Handlers ---

  const handleCancelRiderTrip = useCallback(async () => {
    if (!entity || entity.type !== 'rider' || !onCancelRiderTrip) return;
    setActionLoading(true);
    try {
      await onCancelRiderTrip(entity.data.id);
      await refetchState();
    } finally {
      setActionLoading(false);
    }
  }, [entity, onCancelRiderTrip, refetchState]);

  // Drag handlers
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // Only allow drag from the drag handle
      if ((e.target as HTMLElement).closest(`.${styles.dragHandle}`)) {
        e.preventDefault();
        setIsDragging(true);
        dragOffsetRef.current = {
          x: e.clientX - position.x,
          y: e.clientY - position.y,
        };
      }
    },
    [position.x, position.y]
  );

  const handleMouseMove = useCallback((e: MouseEvent) => {
    const popupWidth = 320;
    const popupHeight = 100; // Minimum height to keep on screen
    setPosition({
      x: Math.max(0, Math.min(window.innerWidth - popupWidth, e.clientX - dragOffsetRef.current.x)),
      y: Math.max(
        0,
        Math.min(window.innerHeight - popupHeight, e.clientY - dragOffsetRef.current.y)
      ),
    });
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Add global mouse listeners during drag
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  if (!entity) {
    return null;
  }

  const renderDriverContent = () => {
    if (loading) {
      return <div className={styles.loading}>Loading...</div>;
    }

    if (error || !detailedDriverState) {
      // Fallback to basic info
      const { data } = entity as { type: 'driver'; data: Driver };
      return (
        <>
          <h3>Driver</h3>
          <div className={styles.row}>
            <span className={styles.label}>ID:</span>
            <span className={styles.value}>{data.id.slice(0, 8)}...</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Status:</span>
            <span className={styles.value}>{data.status}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Rating:</span>
            <span className={styles.value}>{data.rating}</span>
          </div>
          {error && <div className={styles.error}>{error}</div>}
        </>
      );
    }

    const { dna, active_trip } = detailedDriverState;

    return (
      <>
        <div className={styles.header}>
          <h3>
            {dna.first_name} {dna.last_name}
          </h3>
        </div>
        {detailedDriverState.is_puppet && <span className={styles.badge}>Puppet Driver</span>}

        <div className={styles.section}>
          <h4>Status</h4>
          <div className={styles.row}>
            <span className={styles.label}>ID:</span>
            <span className={`${styles.value} ${styles.idValue}`}>
              {(entity as { type: 'driver'; data: Driver }).data.id}
            </span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Status:</span>
            <span className={styles.value}>{detailedDriverState.status}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Rating:</span>
            <span className={styles.value}>
              {detailedDriverState.current_rating.toFixed(2)} ({detailedDriverState.rating_count})
            </span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Zone:</span>
            <span className={styles.value}>{detailedDriverState.zone_id || 'Unknown'}</span>
          </div>
        </div>

        {detailedDriverState.pending_offer && (
          <div className={styles.section}>
            <h4>Pending Offer</h4>
            <div className={styles.row}>
              <span className={styles.label}>Trip ID:</span>
              <span className={styles.value}>
                {detailedDriverState.pending_offer.trip_id.slice(0, 8)}...
              </span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Surge:</span>
              <span className={styles.value}>
                {detailedDriverState.pending_offer.surge_multiplier.toFixed(1)}x
              </span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Rider Rating:</span>
              <span className={styles.value}>
                {detailedDriverState.pending_offer.rider_rating.toFixed(1)}
              </span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>ETA:</span>
              <span className={styles.value}>{detailedDriverState.pending_offer.eta_seconds}s</span>
            </div>
          </div>
        )}

        {active_trip && (
          <div className={styles.section}>
            <h4>Active Trip</h4>
            {active_trip.counterpart_name && (
              <div className={styles.row}>
                <span className={styles.label}>
                  {active_trip.state === 'driver_en_route' && 'En route to:'}
                  {active_trip.state === 'driver_arrived' && 'Waiting for:'}
                  {active_trip.state === 'started' && 'Driving:'}
                  {!['driver_en_route', 'driver_arrived', 'started'].includes(active_trip.state) &&
                    'Rider:'}
                </span>
                <span className={styles.value}>{active_trip.counterpart_name}</span>
              </div>
            )}
            <div className={styles.row}>
              <span className={styles.label}>State:</span>
              <span className={styles.value}>{formatTripState(active_trip.state)}</span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Fare:</span>
              <span className={styles.value}>R$ {active_trip.fare.toFixed(2)}</span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Surge:</span>
              <span className={styles.value}>{active_trip.surge_multiplier.toFixed(1)}x</span>
            </div>
          </div>
        )}

        <div className={styles.section}>
          <h4>Behavioral DNA</h4>
          <div className={styles.row}>
            <span className={styles.label}>Acceptance:</span>
            <span className={styles.value}>{(dna.acceptance_rate * 100).toFixed(0)}%</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Service Quality:</span>
            <span className={styles.value}>{(dna.service_quality * 100).toFixed(0)}%</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Response Time:</span>
            <span className={styles.value}>{dna.response_time.toFixed(1)}s</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Min Rider Rating:</span>
            <span className={styles.value}>{dna.min_rider_rating.toFixed(1)}</span>
          </div>
        </div>

        <div className={styles.section}>
          <h4>Vehicle</h4>
          <div className={styles.row}>
            <span className={styles.label}>Vehicle:</span>
            <span className={styles.value}>
              {dna.vehicle_year} {dna.vehicle_make} {dna.vehicle_model}
            </span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Plate:</span>
            <span className={styles.value}>{dna.license_plate}</span>
          </div>
        </div>

        <div className={styles.section}>
          <h4>Session Statistics</h4>
          <div className={styles.statsGrid}>
            <div className={styles.statItem}>
              <span className={styles.statValue}>
                {detailedDriverState.statistics.trips_completed}
              </span>
              <span className={styles.statLabel}>Completed</span>
            </div>
            <div className={styles.statItem}>
              <span className={styles.statValue}>
                {detailedDriverState.statistics.trips_cancelled}
              </span>
              <span className={styles.statLabel}>Cancelled</span>
            </div>
            <div className={styles.statItem}>
              <span className={styles.statValue}>
                {detailedDriverState.statistics.offers_received}
              </span>
              <span className={styles.statLabel}>Offers</span>
            </div>
            <div className={styles.statItem}>
              <span className={styles.statValue}>
                {detailedDriverState.statistics.acceptance_rate.toFixed(0)}%
              </span>
              <span className={styles.statLabel}>Accept Rate</span>
            </div>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Earnings:</span>
            <span className={styles.value}>
              R$ {detailedDriverState.statistics.total_earnings.toFixed(2)}
            </span>
          </div>
          {detailedDriverState.statistics.trips_completed > 0 && (
            <>
              <div className={styles.row}>
                <span className={styles.label}>Avg Fare:</span>
                <span className={styles.value}>
                  R$ {detailedDriverState.statistics.avg_fare.toFixed(2)}
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>Avg Pickup:</span>
                <span className={styles.value}>
                  {detailedDriverState.statistics.avg_pickup_time_seconds.toFixed(0)}s
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>Avg Trip:</span>
                <span className={styles.value}>
                  {detailedDriverState.statistics.avg_trip_duration_minutes.toFixed(1)} min
                </span>
              </div>
            </>
          )}
          {detailedDriverState.statistics.avg_rating_given > 0 && (
            <div className={styles.row}>
              <span className={styles.label}>Avg Rating Given:</span>
              <span className={styles.value}>
                {detailedDriverState.statistics.avg_rating_given.toFixed(1)}
              </span>
            </div>
          )}
        </div>

        {/* Actions section (puppet only) */}
        {detailedDriverState.is_puppet && (
          <div className={styles.section}>
            <h4>Actions</h4>

            {/* Pending offer actions */}
            {detailedDriverState.pending_offer && (
              <div className={styles.buttonGroup}>
                <button
                  className={`${styles.actionButton} ${styles.successButton}`}
                  onClick={handleAcceptOffer}
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Loading...' : 'Accept Offer'}
                </button>
                <button
                  className={`${styles.actionButton} ${styles.dangerButton}`}
                  onClick={handleRejectOffer}
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Loading...' : 'Reject Offer'}
                </button>
              </div>
            )}

            {/* Trip lifecycle actions */}
            {active_trip && (
              <div className={styles.buttonGroup}>
                {(detailedDriverState.status === 'en_route_pickup' ||
                  detailedDriverState.status === 'busy') &&
                  active_trip.state !== 'driver_arrived' && (
                    <button
                      className={styles.actionButton}
                      onClick={handleArriveAtPickup}
                      disabled={actionLoading}
                    >
                      {actionLoading ? 'Loading...' : 'Arrive at Pickup'}
                    </button>
                  )}

                {active_trip.state === 'driver_arrived' && (
                  <button
                    className={`${styles.actionButton} ${styles.successButton}`}
                    onClick={handleStartTrip}
                    disabled={actionLoading}
                  >
                    {actionLoading ? 'Loading...' : 'Start Trip'}
                  </button>
                )}

                {detailedDriverState.status === 'en_route_destination' && (
                  <button
                    className={`${styles.actionButton} ${styles.successButton}`}
                    onClick={handleCompleteTrip}
                    disabled={actionLoading}
                  >
                    {actionLoading ? 'Loading...' : 'Complete Trip'}
                  </button>
                )}

                {(detailedDriverState.status === 'busy' ||
                  detailedDriverState.status === 'en_route_pickup') &&
                  active_trip.state !== 'started' && (
                    <button
                      className={`${styles.actionButton} ${styles.dangerButton}`}
                      onClick={handleCancelDriverTrip}
                      disabled={actionLoading}
                    >
                      {actionLoading ? 'Loading...' : 'Cancel Trip'}
                    </button>
                  )}
              </div>
            )}

            {/* Online/Offline toggle */}
            {onToggleDriverStatus && !active_trip && !detailedDriverState.pending_offer && (
              <button
                className={styles.actionButton}
                onClick={handleToggleDriverStatus}
                disabled={actionLoading}
              >
                {actionLoading
                  ? 'Loading...'
                  : detailedDriverState.status === 'online'
                    ? 'Go Offline'
                    : 'Go Online'}
              </button>
            )}
          </div>
        )}

        {/* Next Actions section (autonomous only) */}
        {!detailedDriverState.is_puppet && (
          <NextActionsSection nextAction={detailedDriverState.next_action} isPuppet={false} />
        )}
      </>
    );
  };

  const renderRiderContent = () => {
    if (loading) {
      return <div className={styles.loading}>Loading...</div>;
    }

    if (error || !detailedRiderState) {
      const { data } = entity as { type: 'rider'; data: Rider };
      const destinationText =
        data.destination_latitude && data.destination_longitude
          ? `${data.destination_latitude.toFixed(4)}, ${data.destination_longitude.toFixed(4)}`
          : 'Not set';

      return (
        <>
          <h3>Rider</h3>
          <div className={styles.row}>
            <span className={styles.label}>ID:</span>
            <span className={styles.value}>{data.id.slice(0, 8)}...</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Status:</span>
            <span className={styles.value}>{data.status}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Destination:</span>
            <span className={styles.value}>{destinationText}</span>
          </div>
          {error && <div className={styles.error}>{error}</div>}
        </>
      );
    }

    const { dna, active_trip } = detailedRiderState;

    return (
      <>
        <div className={styles.header}>
          <h3>
            {dna.first_name} {dna.last_name}
          </h3>
        </div>
        {detailedRiderState.is_puppet && <span className={styles.badge}>Puppet Rider</span>}

        <div className={styles.section}>
          <h4>Status</h4>
          <div className={styles.row}>
            <span className={styles.label}>ID:</span>
            <span className={`${styles.value} ${styles.idValue}`}>
              {(entity as { type: 'rider'; data: Rider }).data.id}
            </span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Status:</span>
            <span className={styles.value}>{detailedRiderState.status}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Rating:</span>
            <span className={styles.value}>
              {detailedRiderState.current_rating.toFixed(2)} ({detailedRiderState.rating_count})
            </span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Zone:</span>
            <span className={styles.value}>{detailedRiderState.zone_id || 'Unknown'}</span>
          </div>
        </div>

        {active_trip && (
          <div className={styles.section}>
            <h4>Active Trip</h4>
            {active_trip.counterpart_name && (
              <div className={styles.row}>
                <span className={styles.label}>Driver:</span>
                <span className={styles.value}>
                  {active_trip.counterpart_name}
                  {active_trip.state === 'matched' && ' assigned'}
                  {active_trip.state === 'driver_en_route' && ' is en route'}
                  {active_trip.state === 'driver_arrived' && ' has arrived'}
                  {active_trip.state === 'started' && ' (in trip)'}
                </span>
              </div>
            )}
            <div className={styles.row}>
              <span className={styles.label}>State:</span>
              <span className={styles.value}>{formatTripState(active_trip.state)}</span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Fare:</span>
              <span className={styles.value}>R$ {active_trip.fare.toFixed(2)}</span>
            </div>
            <div className={styles.row}>
              <span className={styles.label}>Surge:</span>
              <span className={styles.value}>{active_trip.surge_multiplier.toFixed(1)}x</span>
            </div>
          </div>
        )}

        <div className={styles.section}>
          <h4>Behavioral DNA</h4>
          <div className={styles.row}>
            <span className={styles.label}>Behavior Factor:</span>
            <span className={styles.value}>{(dna.behavior_factor * 100).toFixed(0)}%</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Patience:</span>
            <span className={styles.value}>{dna.patience_threshold}s</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Max Surge:</span>
            <span className={styles.value}>{dna.max_surge_multiplier.toFixed(1)}x</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Rides/Week:</span>
            <span className={styles.value}>{dna.avg_rides_per_week}</span>
          </div>
        </div>

        <div className={styles.section}>
          <h4>Payment</h4>
          <div className={styles.row}>
            <span className={styles.label}>Method:</span>
            <span className={styles.value}>{dna.payment_method_type}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Card:</span>
            <span className={styles.value}>{dna.payment_method_masked}</span>
          </div>
        </div>

        <div className={styles.section}>
          <h4>Session Statistics</h4>
          <div className={styles.statsGrid}>
            <div className={styles.statItem}>
              <span className={styles.statValue}>
                {detailedRiderState.statistics.trips_completed}
              </span>
              <span className={styles.statLabel}>Completed</span>
            </div>
            <div className={styles.statItem}>
              <span className={styles.statValue}>
                {detailedRiderState.statistics.trips_cancelled}
              </span>
              <span className={styles.statLabel}>Cancelled</span>
            </div>
            <div className={styles.statItem}>
              <span className={styles.statValue}>
                {detailedRiderState.statistics.trips_requested}
              </span>
              <span className={styles.statLabel}>Requested</span>
            </div>
            <div className={styles.statItem}>
              <span className={styles.statValue}>
                {detailedRiderState.statistics.requests_timed_out}
              </span>
              <span className={styles.statLabel}>Timed Out</span>
            </div>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Total Spent:</span>
            <span className={styles.value}>
              R$ {detailedRiderState.statistics.total_spent.toFixed(2)}
            </span>
          </div>
          {detailedRiderState.statistics.trips_completed > 0 && (
            <>
              <div className={styles.row}>
                <span className={styles.label}>Avg Fare:</span>
                <span className={styles.value}>
                  R$ {detailedRiderState.statistics.avg_fare.toFixed(2)}
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>Avg Wait:</span>
                <span className={styles.value}>
                  {detailedRiderState.statistics.avg_wait_time_seconds.toFixed(0)}s
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>Avg Pickup Wait:</span>
                <span className={styles.value}>
                  {detailedRiderState.statistics.avg_pickup_wait_seconds.toFixed(0)}s
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>Surge Trips:</span>
                <span className={styles.value}>
                  {detailedRiderState.statistics.surge_trips_percentage.toFixed(0)}%
                </span>
              </div>
            </>
          )}
          {detailedRiderState.statistics.avg_rating_given > 0 && (
            <div className={styles.row}>
              <span className={styles.label}>Avg Rating Given:</span>
              <span className={styles.value}>
                {detailedRiderState.statistics.avg_rating_given.toFixed(1)}
              </span>
            </div>
          )}
        </div>

        {/* Actions section (puppet only) */}
        {detailedRiderState.is_puppet && (
          <div className={styles.section}>
            <h4>Actions</h4>

            {/* Request trip (when offline) */}
            {onRequestRiderTrip && detailedRiderState.status === 'offline' && !active_trip && (
              <button className={styles.actionButton} onClick={handleRequestTrip}>
                Request Trip (Select Destination)
              </button>
            )}

            {/* Cancel trip (when waiting or has active trip before started) */}
            {(detailedRiderState.status === 'waiting' ||
              (active_trip && active_trip.state !== 'started')) && (
              <div className={styles.buttonGroup}>
                <div className={styles.statusBadge}>
                  {detailedRiderState.status === 'waiting'
                    ? 'Waiting for driver...'
                    : 'Trip in progress'}
                </div>
                <button
                  className={`${styles.actionButton} ${styles.dangerButton}`}
                  onClick={handleCancelRiderTrip}
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Loading...' : 'Cancel Trip'}
                </button>
              </div>
            )}

            {detailedRiderState.status !== 'offline' &&
              detailedRiderState.status !== 'waiting' &&
              !active_trip && (
                <div className={styles.infoMessage}>Status: {detailedRiderState.status}</div>
              )}
          </div>
        )}

        {/* Next Actions section (autonomous only) */}
        {!detailedRiderState.is_puppet && (
          <NextActionsSection nextAction={detailedRiderState.next_action} isPuppet={false} />
        )}
      </>
    );
  };

  const renderContent = () => {
    if (entity.type === 'zone') {
      const { data } = entity;
      return (
        <>
          <h3>Zone</h3>
          <div className={styles.row}>
            <span className={styles.label}>Name:</span>
            <span className={styles.value}>{data.feature.properties.name}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Surge Multiplier:</span>
            <span className={styles.value}>{data.surge}x</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Drivers:</span>
            <span className={styles.value}>{data.driver_count}</span>
          </div>
        </>
      );
    }

    if (entity.type === 'driver') {
      return renderDriverContent();
    }

    if (entity.type === 'rider') {
      return renderRiderContent();
    }

    return null;
  };

  return (
    <div
      className={`${styles.popup} ${isDragging ? styles.dragging : ''} ${isMinimized ? styles.minimized : ''}`}
      data-testid="inspector-popup"
      style={{
        left: position.x,
        top: position.y,
      }}
    >
      <div className={styles.popupHeader} onMouseDown={handleMouseDown}>
        <div className={styles.dragHandle}>
          <span className={styles.dragIcon}>⋮⋮</span>
        </div>
        <button
          className={styles.minimizeButton}
          onClick={() => setIsMinimized(!isMinimized)}
          aria-label={isMinimized ? 'Restore' : 'Minimize'}
        >
          {isMinimized ? '□' : '−'}
        </button>
        <button className={styles.closeButton} onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      {isMinimized ? (
        <div className={styles.minimizedHeader}>
          <span className={styles.minimizedTitle}>{getEntityTitle()}</span>
        </div>
      ) : (
        <div className={styles.popupContent}>{renderContent()}</div>
      )}
    </div>
  );
}
