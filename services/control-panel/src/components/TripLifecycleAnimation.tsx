import { useEffect, useRef, useCallback } from 'react';
import confetti from 'canvas-confetti';
import { DRIVER_COLORS, RIDER_TRIP_STATE_COLORS } from '../layers/agentLayers';
import { resolvePhase, TOTAL_CYCLE_DURATION, type Phase } from './tripLifecyclePhases';
import styles from './TripLifecycleAnimation.module.css';

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function rgbString(color: readonly [number, number, number]): string {
  return `rgb(${color[0]},${color[1]},${color[2]})`;
}

// ============================================================================
// Color constants from agentLayers
// ============================================================================

const COLOR_DRIVER_OFFLINE = DRIVER_COLORS.offline;
const COLOR_DRIVER_ONLINE = DRIVER_COLORS.online;
const COLOR_DRIVER_PICKUP = DRIVER_COLORS.en_route_pickup;
const COLOR_DRIVER_TRIP = DRIVER_COLORS.en_route_destination;

const COLOR_RIDER_OFFLINE = RIDER_TRIP_STATE_COLORS.offline;
const COLOR_RIDER_REQUESTED = RIDER_TRIP_STATE_COLORS.requested;
const COLOR_RIDER_MATCHED = RIDER_TRIP_STATE_COLORS.matched;
const COLOR_RIDER_EN_ROUTE = RIDER_TRIP_STATE_COLORS.driver_en_route;
const COLOR_RIDER_STARTED = RIDER_TRIP_STATE_COLORS.started;
const COLOR_RIDER_COMPLETED = RIDER_TRIP_STATE_COLORS.completed;

// Route colors (from agentLayers layer definitions)
const COLOR_PENDING_ROUTE: [number, number, number] = [253, 186, 116];
const COLOR_PICKUP_ROUTE: [number, number, number] = [252, 211, 77];
const COLOR_TRIP_ROUTE: [number, number, number] = [96, 165, 250];

// ============================================================================
// SVG Road Path (sinuous curve)
// ============================================================================

// Two-cycle sine wave approximated with cubic beziers, centered at y=40
const ROAD_PATH =
  'M 30,40 C 90,10 150,10 210,40 C 270,70 330,70 390,40 C 450,10 510,10 570,40 C 630,70 690,70 750,40 C 810,10 870,10 930,40';

// Positions along the road as fraction of total length
const CAR_START_FRAC = 0.02;
const PERSON_FRAC = 0.45;
const FLAG_FRAC = 0.93;

// ============================================================================
// Component
// ============================================================================

export function TripLifecycleAnimation() {
  // SVG element refs
  const svgRef = useRef<SVGSVGElement>(null);
  const roadPathRef = useRef<SVGPathElement>(null);
  const animatedGroupRef = useRef<SVGGElement>(null);

  // Icon group refs
  const carGroupRef = useRef<SVGGElement>(null);
  const personGroupRef = useRef<SVGGElement>(null);

  const flagGroupRef = useRef<SVGGElement>(null);

  // Filter flood refs for tinting
  const carFloodRef = useRef<SVGFEFloodElement>(null);
  const personFloodRef = useRef<SVGFEFloodElement>(null);

  // Route overlay refs
  const pendingRouteRef = useRef<SVGPathElement>(null);
  const pickupRouteRef = useRef<SVGPathElement>(null);
  const tripRouteRef = useRef<SVGPathElement>(null);

  // Confetti canvas
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Animation state (not React state — direct DOM for 60fps)
  const rafIdRef = useRef(0);
  const confettiFiredRef = useRef(false);
  const reducedMotionRef = useRef(false);

  // Cached path data computed on mount
  const pathDataRef = useRef<{
    totalLength: number;
    carStartLen: number;
    personLen: number;
    flagLen: number;
    pickupPathD: string;
    pickupPathLen: number;
    tripPathD: string;
    tripPathLen: number;
    pendingPathD: string;
    pendingPathLen: number;
  } | null>(null);

  // Sample points along an SVGPathElement to build a polyline path string
  const sampleSubPath = useCallback(
    (pathEl: SVGPathElement, startLen: number, endLen: number, steps: number): string => {
      const parts: string[] = [];
      for (let i = 0; i <= steps; i++) {
        const len = startLen + ((endLen - startLen) * i) / steps;
        const pt = pathEl.getPointAtLength(len);
        parts.push(i === 0 ? `M ${pt.x},${pt.y}` : `L ${pt.x},${pt.y}`);
      }
      return parts.join(' ');
    },
    []
  );

  // Compute sub-path lengths (approximate via sampling)
  const computeSubPathLength = useCallback(
    (pathEl: SVGPathElement, startLen: number, endLen: number, steps: number): number => {
      let length = 0;
      let prevPt = pathEl.getPointAtLength(startLen);
      for (let i = 1; i <= steps; i++) {
        const len = startLen + ((endLen - startLen) * i) / steps;
        const pt = pathEl.getPointAtLength(len);
        length += Math.hypot(pt.x - prevPt.x, pt.y - prevPt.y);
        prevPt = pt;
      }
      return length;
    },
    []
  );

  // Initialize path data on mount
  useEffect(() => {
    const roadEl = roadPathRef.current;
    if (!roadEl) return;

    const totalLength = roadEl.getTotalLength();
    const carStartLen = totalLength * CAR_START_FRAC;
    const personLen = totalLength * PERSON_FRAC;
    const flagLen = totalLength * FLAG_FRAC;

    const SAMPLE_STEPS = 60;

    // Pending route: person → flag (rider's intended trip route, shown during request)
    const pendingPathD = sampleSubPath(roadEl, personLen, flagLen, SAMPLE_STEPS);
    const pendingPathLen = computeSubPathLength(roadEl, personLen, flagLen, SAMPLE_STEPS);

    // Pickup route: car start → person
    const pickupPathD = sampleSubPath(roadEl, carStartLen, personLen, SAMPLE_STEPS);
    const pickupPathLen = computeSubPathLength(roadEl, carStartLen, personLen, SAMPLE_STEPS);

    // Trip route: person → flag
    const tripPathD = sampleSubPath(roadEl, personLen, flagLen, SAMPLE_STEPS);
    const tripPathLen = computeSubPathLength(roadEl, personLen, flagLen, SAMPLE_STEPS);

    pathDataRef.current = {
      totalLength,
      carStartLen,
      personLen,
      flagLen,
      pickupPathD,
      pickupPathLen,
      tripPathD,
      tripPathLen,
      pendingPathD,
      pendingPathLen,
    };

    // Position flag icon at destination
    const flagPt = roadEl.getPointAtLength(flagLen);
    if (flagGroupRef.current) {
      flagGroupRef.current.setAttribute(
        'transform',
        `translate(${flagPt.x - 12}, ${flagPt.y - 12})`
      );
    }

    // Position car and person at initial positions
    const carStartPt = roadEl.getPointAtLength(carStartLen);
    const personPt = roadEl.getPointAtLength(personLen);
    if (carGroupRef.current) {
      carGroupRef.current.setAttribute(
        'transform',
        `translate(${carStartPt.x - 14}, ${carStartPt.y - 14})`
      );
    }
    if (personGroupRef.current) {
      personGroupRef.current.setAttribute(
        'transform',
        `translate(${personPt.x - 12}, ${personPt.y - 12})`
      );
    }

    // Set sub-path d attributes
    if (pendingRouteRef.current) {
      pendingRouteRef.current.setAttribute('d', pendingPathD);
      pendingRouteRef.current.style.strokeDasharray = `${pendingPathLen}`;
      pendingRouteRef.current.style.strokeDashoffset = `${pendingPathLen}`;
    }
    if (pickupRouteRef.current) {
      pickupRouteRef.current.setAttribute('d', pickupPathD);
      pickupRouteRef.current.style.strokeDasharray = `${pickupPathLen}`;
      pickupRouteRef.current.style.strokeDashoffset = `${pickupPathLen}`;
    }
    if (tripRouteRef.current) {
      tripRouteRef.current.setAttribute('d', tripPathD);
      tripRouteRef.current.style.strokeDasharray = `${tripPathLen}`;
      tripRouteRef.current.style.strokeDashoffset = `${tripPathLen}`;
    }
  }, [sampleSubPath, computeSubPathLength]);

  // Animation loop
  useEffect(() => {
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    reducedMotionRef.current = mql.matches;

    if (reducedMotionRef.current) {
      // Static completed state
      renderStaticCompleted();
      return;
    }

    let startTime: number | null = null;

    function animate(timestamp: number) {
      if (startTime === null) startTime = timestamp;
      const elapsed = (timestamp - startTime) / 1000;
      const cycleTime = elapsed % TOTAL_CYCLE_DURATION;

      const { phase, progress } = resolvePhase(cycleTime);
      applyVisualState(phase, progress);

      rafIdRef.current = requestAnimationFrame(animate);
    }

    rafIdRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafIdRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function renderStaticCompleted() {
    const pd = pathDataRef.current;
    if (!pd) return;

    const roadEl = roadPathRef.current;
    if (!roadEl) return;

    // Position car and person at flag
    const flagPt = roadEl.getPointAtLength(pd.flagLen);
    if (carGroupRef.current) {
      carGroupRef.current.setAttribute(
        'transform',
        `translate(${flagPt.x - 14}, ${flagPt.y - 14})`
      );
    }
    if (personGroupRef.current) {
      personGroupRef.current.setAttribute(
        'transform',
        `translate(${flagPt.x - 12 - 20}, ${flagPt.y - 12})`
      );
    }

    // Set colors to completed
    if (carFloodRef.current) {
      carFloodRef.current.setAttribute('flood-color', rgbString(COLOR_DRIVER_TRIP));
    }
    if (personFloodRef.current) {
      personFloodRef.current.setAttribute('flood-color', rgbString(COLOR_RIDER_COMPLETED));
    }

    // Show all routes fully drawn
    if (pickupRouteRef.current) {
      pickupRouteRef.current.style.strokeDashoffset = '0';
      pickupRouteRef.current.style.opacity = '1';
    }
    if (tripRouteRef.current) {
      tripRouteRef.current.style.strokeDashoffset = '0';
      tripRouteRef.current.style.opacity = '1';
    }
    if (pendingRouteRef.current) {
      pendingRouteRef.current.style.opacity = '0';
    }

    if (animatedGroupRef.current) {
      animatedGroupRef.current.style.opacity = '1';
    }
  }

  function applyVisualState(phase: Phase, progress: number) {
    const pd = pathDataRef.current;
    const roadEl = roadPathRef.current;
    if (!pd || !roadEl) return;

    // Default positions
    const carStartPt = roadEl.getPointAtLength(pd.carStartLen);
    const personPt = roadEl.getPointAtLength(pd.personLen);
    const flagPt = roadEl.getPointAtLength(pd.flagLen);

    let carX = carStartPt.x;
    let carY = carStartPt.y;
    let personX = personPt.x;
    let personY = personPt.y;

    let carColor = rgbString(COLOR_DRIVER_OFFLINE);
    let personColor = rgbString(COLOR_RIDER_OFFLINE);

    let pendingOpacity = 0;
    let pendingOffset = pd.pendingPathLen;
    let pickupOpacity = 0;
    let pickupOffset = pd.pickupPathLen;
    let tripOpacity = 0;
    let tripOffset = pd.tripPathLen;

    let groupOpacity = 1;
    let carPulse = false;

    switch (phase) {
      case 'idle':
        carColor = rgbString(COLOR_DRIVER_OFFLINE);
        personColor = rgbString(COLOR_RIDER_OFFLINE);
        break;

      case 'driver_online':
        carColor = rgbString(COLOR_DRIVER_ONLINE);
        personColor = rgbString(COLOR_RIDER_OFFLINE);
        carPulse = true;
        break;

      case 'rider_request':
        carColor = rgbString(COLOR_DRIVER_ONLINE);
        personColor = rgbString(COLOR_RIDER_REQUESTED);
        // Draw pending route (person → flag)
        pendingOpacity = 1;
        pendingOffset = pd.pendingPathLen * (1 - easeInOutCubic(progress));
        break;

      case 'match':
        carColor = rgbString(COLOR_DRIVER_PICKUP);
        personColor = rgbString(COLOR_RIDER_MATCHED);
        // Pending route fully drawn
        pendingOpacity = 1;
        pendingOffset = 0;
        // Pickup route appears
        pickupOpacity = progress;
        pickupOffset = pd.pickupPathLen;
        break;

      case 'pickup_drive': {
        carColor = rgbString(COLOR_DRIVER_PICKUP);
        personColor = rgbString(COLOR_RIDER_EN_ROUTE);
        // Pending route stays
        pendingOpacity = 1;
        pendingOffset = 0;
        // Car moves toward person, trail draws behind
        pickupOpacity = 1;
        const pickupEased = easeInOutCubic(progress);
        pickupOffset = pd.pickupPathLen * (1 - pickupEased);
        const pickupLen = pd.carStartLen + (pd.personLen - pd.carStartLen) * pickupEased;
        const pickupPt = roadEl.getPointAtLength(pickupLen);
        carX = pickupPt.x;
        carY = pickupPt.y;
        break;
      }

      case 'pickup':
        carColor = rgbString(COLOR_DRIVER_TRIP);
        personColor = rgbString(COLOR_RIDER_STARTED);
        // Car at person
        carX = personPt.x;
        carY = personPt.y;
        // Pending fades, pickup stays, trip appears
        pendingOpacity = 1 - progress;
        pendingOffset = 0;
        pickupOpacity = 1;
        pickupOffset = 0;
        tripOpacity = progress;
        tripOffset = pd.tripPathLen;
        break;

      case 'trip_drive': {
        carColor = rgbString(COLOR_DRIVER_TRIP);
        personColor = rgbString(COLOR_RIDER_STARTED);
        // Pending gone
        pendingOpacity = 0;
        // Pickup stays
        pickupOpacity = 1;
        pickupOffset = 0;
        // Both car and person move toward flag
        tripOpacity = 1;
        const tripEased = easeInOutCubic(progress);
        tripOffset = pd.tripPathLen * (1 - tripEased);
        const tripLen = pd.personLen + (pd.flagLen - pd.personLen) * tripEased;
        const tripPt = roadEl.getPointAtLength(tripLen);
        carX = tripPt.x;
        carY = tripPt.y;
        personX = tripPt.x - 20;
        personY = tripPt.y;
        break;
      }

      case 'completed':
        carColor = rgbString(COLOR_DRIVER_TRIP);
        personColor = rgbString(COLOR_RIDER_COMPLETED);
        // Car at flag
        carX = flagPt.x;
        carY = flagPt.y;
        personX = flagPt.x - 20;
        personY = flagPt.y;
        // All routes visible
        pendingOpacity = 0;
        pickupOpacity = 1;
        pickupOffset = 0;
        tripOpacity = 1;
        tripOffset = 0;

        // Fire confetti once per cycle
        if (!confettiFiredRef.current) {
          confettiFiredRef.current = true;
          fireConfetti();
        }
        break;

      case 'hold':
        carColor = rgbString(COLOR_DRIVER_TRIP);
        personColor = rgbString(COLOR_RIDER_COMPLETED);
        carX = flagPt.x;
        carY = flagPt.y;
        personX = flagPt.x - 20;
        personY = flagPt.y;
        pickupOpacity = 1;
        pickupOffset = 0;
        tripOpacity = 1;
        tripOffset = 0;
        break;

      case 'reset':
        carColor = rgbString(COLOR_DRIVER_TRIP);
        personColor = rgbString(COLOR_RIDER_COMPLETED);
        carX = flagPt.x;
        carY = flagPt.y;
        personX = flagPt.x - 20;
        personY = flagPt.y;
        pickupOpacity = 1;
        pickupOffset = 0;
        tripOpacity = 1;
        tripOffset = 0;
        groupOpacity = 1 - easeInOutCubic(progress);
        confettiFiredRef.current = false;
        break;
    }

    // Apply to DOM
    if (carGroupRef.current) {
      carGroupRef.current.setAttribute('transform', `translate(${carX - 14}, ${carY - 14})`);
      if (carPulse) {
        carGroupRef.current.style.animation = 'iconPulse 0.6s ease-in-out infinite';
      } else {
        carGroupRef.current.style.animation = '';
      }
    }
    if (personGroupRef.current) {
      personGroupRef.current.setAttribute(
        'transform',
        `translate(${personX - 12}, ${personY - 12})`
      );
    }

    if (carFloodRef.current) {
      carFloodRef.current.setAttribute('flood-color', carColor);
    }
    if (personFloodRef.current) {
      personFloodRef.current.setAttribute('flood-color', personColor);
    }

    if (pendingRouteRef.current) {
      pendingRouteRef.current.style.opacity = `${pendingOpacity}`;
      pendingRouteRef.current.style.strokeDashoffset = `${pendingOffset}`;
    }
    if (pickupRouteRef.current) {
      pickupRouteRef.current.style.opacity = `${pickupOpacity}`;
      pickupRouteRef.current.style.strokeDashoffset = `${pickupOffset}`;
    }
    if (tripRouteRef.current) {
      tripRouteRef.current.style.opacity = `${tripOpacity}`;
      tripRouteRef.current.style.strokeDashoffset = `${tripOffset}`;
    }

    if (animatedGroupRef.current) {
      animatedGroupRef.current.style.opacity = `${groupOpacity}`;
    }
  }

  function fireConfetti() {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const myConfetti = confetti.create(canvas, { resize: true });
    myConfetti({
      particleCount: 40,
      spread: 60,
      origin: { x: 0.9, y: 0.5 },
      colors: ['#00ff88', '#4ade80', '#34d399'],
      gravity: 0.8,
      ticks: 80,
      scalar: 0.8,
    });
  }

  return (
    <div className={styles.container}>
      <svg
        ref={svgRef}
        className={styles.svg}
        viewBox="0 0 960 80"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Animated trip lifecycle: a driver picks up a rider and drives to the destination"
      >
        <defs>
          {/* Car tint filter */}
          <filter id="car-tint" colorInterpolationFilters="sRGB">
            <feFlood ref={carFloodRef} floodColor="rgb(107,114,128)" result="color" />
            <feComposite in="color" in2="SourceAlpha" operator="in" />
          </filter>
          {/* Person tint filter */}
          <filter id="person-tint" colorInterpolationFilters="sRGB">
            <feFlood ref={personFloodRef} floodColor="rgb(156,163,175)" result="color" />
            <feComposite in="color" in2="SourceAlpha" operator="in" />
          </filter>
        </defs>

        {/* Background road — always visible at very low opacity */}
        <path
          ref={roadPathRef}
          d={ROAD_PATH}
          fill="none"
          stroke="rgba(0,255,136,0.06)"
          strokeWidth="6"
          strokeLinecap="round"
        />

        {/* Route overlays — hidden initially, drawn by animation */}
        <g ref={animatedGroupRef}>
          {/* Pending route (person→flag): light orange */}
          <path
            ref={pendingRouteRef}
            d={ROAD_PATH}
            fill="none"
            stroke={rgbString(COLOR_PENDING_ROUTE)}
            strokeWidth="3"
            strokeLinecap="round"
            opacity="0"
          />
          {/* Pickup route (car→person): gold */}
          <path
            ref={pickupRouteRef}
            d={ROAD_PATH}
            fill="none"
            stroke={rgbString(COLOR_PICKUP_ROUTE)}
            strokeWidth="3"
            strokeLinecap="round"
            opacity="0"
          />
          {/* Trip route (person→flag): light blue */}
          <path
            ref={tripRouteRef}
            d={ROAD_PATH}
            fill="none"
            stroke={rgbString(COLOR_TRIP_ROUTE)}
            strokeWidth="3"
            strokeLinecap="round"
            opacity="0"
          />

          {/* Car icon */}
          <g ref={carGroupRef}>
            <image href="/icons/car.png" width="28" height="28" filter="url(#car-tint)" />
          </g>

          {/* Person icon */}
          <g ref={personGroupRef}>
            <image href="/icons/person.png" width="24" height="24" filter="url(#person-tint)" />
          </g>

          {/* Flag icon — static at destination */}
          <g ref={flagGroupRef}>
            <image href="/icons/flag-checkered.png" width="24" height="24" />
          </g>
        </g>
      </svg>
      <canvas ref={canvasRef} className={styles.confettiCanvas} />
    </div>
  );
}
