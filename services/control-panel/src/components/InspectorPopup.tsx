import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import type { Driver, Rider, ZoneData, DriverState, RiderState } from '../types/api';
import { useAgentState } from '../hooks/useAgentState';
import { useDraggable } from '../hooks/useDraggable';
import { ZoneInspector, DriverInspector, RiderInspector } from './inspector';
import styles from './InspectorPopup.module.css';

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
  onAcceptOffer?: (driverId: string) => Promise<boolean>;
  onRejectOffer?: (driverId: string) => Promise<boolean>;
  onStartTrip?: (driverId: string) => Promise<boolean>;
  onCancelDriverTrip?: (driverId: string) => Promise<boolean>;
  onCancelRiderTrip?: (riderId: string) => Promise<boolean>;
  onHomeLocationChange?: (location: [number, number] | null) => void;
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
  onStartTrip,
  onCancelDriverTrip,
  onCancelRiderTrip,
  onHomeLocationChange,
}: InspectorPopupProps) {
  const [isMinimized, setIsMinimized] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Calculate adjusted position for viewport bounds
  const { adjustedX, adjustedY } = useMemo(() => {
    const popupWidth = 320;
    const popupHeight = window.innerHeight * 0.8;
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

  // Use draggable hook
  const { position, isDragging, handleMouseDown } = useDraggable({
    initialX: adjustedX,
    initialY: adjustedY,
    popupWidth: 320,
    popupHeight: 100,
  });

  // Get entity key for reset dependency
  const entityKey = useMemo(() => {
    if (!entity) return null;
    if (entity.type === 'zone') return entity.data.feature.properties.zone_id;
    return entity.data.id;
  }, [entity]);

  // Reset minimize state when entity changes
  useEffect(() => {
    setIsMinimized(false);
  }, [entityKey]);

  // Determine entity type for API polling
  const entityType = entity?.type === 'driver' || entity?.type === 'rider' ? entity.type : null;
  const entityId = entity?.type === 'driver' || entity?.type === 'rider' ? entity.data.id : null;

  // Use agent state hook for API polling
  const {
    state: agentState,
    loading,
    error,
    refetch,
  } = useAgentState<DriverState | RiderState>({
    entityType,
    entityId,
    isMinimized,
  });

  const driverState = entity?.type === 'driver' ? (agentState as DriverState | null) : null;
  const riderState = entity?.type === 'rider' ? (agentState as RiderState | null) : null;

  // Notify parent of home location changes for map marker
  useEffect(() => {
    if (!onHomeLocationChange) return;

    let homeLocation: [number, number] | null = null;
    if (driverState?.dna?.home_location) {
      const [lat, lon] = driverState.dna.home_location;
      homeLocation = [lon, lat]; // Swap to [lon, lat] for deck.gl
    } else if (riderState?.dna?.home_location) {
      const [lat, lon] = riderState.dna.home_location;
      homeLocation = [lon, lat];
    }

    onHomeLocationChange(homeLocation);
  }, [driverState?.dna?.home_location, riderState?.dna?.home_location, onHomeLocationChange]);

  // Get entity title for minimized header
  const getEntityTitle = useCallback(() => {
    if (!entity) return '';
    if (entity.type === 'zone') {
      return `Zone: ${entity.data.feature.properties.name}`;
    }
    if (entity.type === 'driver') {
      if (driverState?.dna) {
        return `${driverState.dna.first_name} ${driverState.dna.last_name}`;
      }
      return `Driver: ${entity.data.id.slice(0, 8)}...`;
    }
    if (entity.type === 'rider') {
      if (riderState?.dna) {
        return `${riderState.dna.first_name} ${riderState.dna.last_name}`;
      }
      return `Rider: ${entity.data.id.slice(0, 8)}...`;
    }
    return '';
  }, [entity, driverState, riderState]);

  // Action handlers with loading state
  const wrapAction = useCallback(
    (action: () => Promise<unknown>) => async () => {
      setActionLoading(true);
      try {
        await action();
        await refetch();
      } finally {
        if (isMountedRef.current) {
          setActionLoading(false);
        }
      }
    },
    [refetch]
  );

  // Driver action handlers
  const handleAcceptOffer =
    entity?.type === 'driver' && onAcceptOffer
      ? wrapAction(() => onAcceptOffer(entity.data.id))
      : undefined;
  const handleRejectOffer =
    entity?.type === 'driver' && onRejectOffer
      ? wrapAction(() => onRejectOffer(entity.data.id))
      : undefined;
  const handleStartTrip =
    entity?.type === 'driver' && onStartTrip
      ? wrapAction(() => onStartTrip(entity.data.id))
      : undefined;
  const handleCancelDriverTrip =
    entity?.type === 'driver' && onCancelDriverTrip
      ? wrapAction(() => onCancelDriverTrip(entity.data.id))
      : undefined;
  const handleToggleDriverStatus =
    entity?.type === 'driver' && onToggleDriverStatus && driverState
      ? wrapAction(() => onToggleDriverStatus(entity.data.id, driverState.status !== 'available'))
      : undefined;

  // Rider action handlers
  const handleRequestTrip = useCallback(() => {
    if (!entity || entity.type !== 'rider' || !onRequestRiderTrip) return;
    const riderName = riderState?.dna
      ? `${riderState.dna.first_name} ${riderState.dna.last_name}`
      : `Rider ${entity.data.id.slice(0, 8)}`;
    onRequestRiderTrip(entity.data.id, riderName);
  }, [entity, onRequestRiderTrip, riderState]);

  const handleCancelRiderTrip =
    entity?.type === 'rider' && onCancelRiderTrip
      ? wrapAction(() => onCancelRiderTrip(entity.data.id))
      : undefined;

  // Handle drag from header
  const handleHeaderMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if ((e.target as HTMLElement).closest(`.${styles.dragHandle}`)) {
        handleMouseDown(e);
      }
    },
    [handleMouseDown]
  );

  if (!entity) {
    return null;
  }

  const renderContent = () => {
    if (entity.type === 'zone') {
      return <ZoneInspector zone={entity.data} />;
    }

    if (entity.type === 'driver') {
      return (
        <DriverInspector
          driver={entity.data}
          state={driverState}
          loading={loading}
          error={error}
          actionLoading={actionLoading}
          onRefetch={refetch}
          onAcceptOffer={handleAcceptOffer}
          onRejectOffer={handleRejectOffer}
          onStartTrip={handleStartTrip}
          onCancelTrip={handleCancelDriverTrip}
          onToggleStatus={handleToggleDriverStatus}
        />
      );
    }

    if (entity.type === 'rider') {
      return (
        <RiderInspector
          rider={entity.data}
          state={riderState}
          loading={loading}
          error={error}
          actionLoading={actionLoading}
          onRefetch={refetch}
          onRequestTrip={handleRequestTrip}
          onCancelTrip={handleCancelRiderTrip}
        />
      );
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
      <div className={styles.popupHeader} onMouseDown={handleHeaderMouseDown}>
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
