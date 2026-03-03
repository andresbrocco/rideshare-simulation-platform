// ArchitectureDiagram — inline SVG showing the platform's dual data-flow paths.
// Real-time path (left): Simulation → Kafka → Stream Processor → Redis → WebSocket → Frontend
// Analytics path (right): Kafka → Bronze → Silver → Gold → Trino + Grafana
// SMIL <animateMotion> particles animate along each edge, gated behind prefers-reduced-motion.

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

// ── Node layout ────────────────────────────────────────────────────────────────
// viewBox: 0 0 800 520
// Left column (real-time): x≈130, right column (analytics): x≈530
// Kafka hub sits in the centre: x≈400, y≈140

interface NodeDef {
  id: string;
  label: string;
  subLabel?: string;
  cx: number; // rect centre x
  cy: number; // rect centre y
  w: number;
  h: number;
  strokeColor: string; // CSS variable
  strokeOpacity?: number;
}

const RT_X = 130; // real-time column centre
const AN_X = 620; // analytics column centre
const KF_X = 375; // kafka hub centre

const NODES: NodeDef[] = [
  // Real-time path (left column)
  {
    id: 'sim',
    label: 'Simulation Engine',
    subLabel: 'SimPy + H3',
    cx: RT_X,
    cy: 60,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-neon)',
  },
  {
    id: 'kafka',
    label: 'Kafka',
    subLabel: 'Event Hub',
    cx: KF_X,
    cy: 160,
    w: 140,
    h: 46,
    strokeColor: 'var(--offline-text)',
  },
  {
    id: 'stream',
    label: 'Stream Processor',
    subLabel: 'Faust',
    cx: RT_X,
    cy: 260,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-neon)',
  },
  {
    id: 'redis',
    label: 'Redis Pub/Sub',
    subLabel: 'State cache',
    cx: RT_X,
    cy: 355,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-neon)',
  },
  {
    id: 'ws',
    label: 'WebSocket Server',
    subLabel: 'FastAPI',
    cx: RT_X,
    cy: 450,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-neon)',
  },
  {
    id: 'frontend',
    label: 'React Frontend',
    subLabel: 'deck.gl',
    cx: RT_X,
    cy: 490,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-neon)',
  },

  // Analytics path (right column)
  {
    id: 'bronze',
    label: 'Bronze Ingestion',
    subLabel: 'Delta Lake raw',
    cx: AN_X,
    cy: 260,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-bronze)',
    strokeOpacity: 0.9,
  },
  {
    id: 'silver',
    label: 'Silver',
    subLabel: 'Validated + deduped',
    cx: AN_X,
    cy: 355,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-silver)',
    strokeOpacity: 0.85,
  },
  {
    id: 'gold',
    label: 'Gold',
    subLabel: 'Star schema',
    cx: AN_X,
    cy: 450,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-gold)',
    strokeOpacity: 0.85,
  },
  {
    id: 'trino',
    label: 'Trino + Grafana',
    subLabel: 'Query + dashboards',
    cx: AN_X,
    cy: 490,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-gold)',
    strokeOpacity: 0.7,
  },
];

// ── Edge definitions ──────────────────────────────────────────────────────────

interface EdgeDef {
  id: string;
  points: string; // polyline points string
  path: 'realtime' | 'analytics';
  label?: string;
  labelX?: number;
  labelY?: number;
}

// Helper: get node rect top/bottom/left/right centres
function nodePort(id: string, port: 'top' | 'bottom' | 'left' | 'right'): [number, number] {
  const n = NODES.find((n) => n.id === id);
  if (!n) return [0, 0];
  switch (port) {
    case 'top':
      return [n.cx, n.cy - n.h / 2];
    case 'bottom':
      return [n.cx, n.cy + n.h / 2];
    case 'left':
      return [n.cx - n.w / 2, n.cy];
    case 'right':
      return [n.cx + n.w / 2, n.cy];
  }
}

function pts(...coords: [number, number][]): string {
  return coords.map(([x, y]) => `${x},${y}`).join(' ');
}

const EDGES: EdgeDef[] = [
  // Real-time path
  {
    id: 'e-sim-kafka',
    path: 'realtime',
    points: pts(nodePort('sim', 'right'), nodePort('kafka', 'left')),
    label: 'events',
    labelX: 255,
    labelY: 108,
  },
  {
    id: 'e-kafka-stream',
    path: 'realtime',
    points: pts(nodePort('kafka', 'left'), [RT_X + 80, 160], nodePort('stream', 'top')),
    label: 'consume',
    labelX: 175,
    labelY: 208,
  },
  {
    id: 'e-stream-redis',
    path: 'realtime',
    points: pts(nodePort('stream', 'bottom'), nodePort('redis', 'top')),
    label: 'fan-out',
    labelX: RT_X + 56,
    labelY: 310,
  },
  {
    id: 'e-redis-ws',
    path: 'realtime',
    points: pts(nodePort('redis', 'bottom'), nodePort('ws', 'top')),
    label: 'push',
    labelX: RT_X + 56,
    labelY: 405,
  },
  {
    id: 'e-ws-frontend',
    path: 'realtime',
    points: pts(nodePort('ws', 'bottom'), nodePort('frontend', 'top')),
    label: 'WS',
    labelX: RT_X + 56,
    labelY: 472,
  },

  // Analytics path
  {
    id: 'e-kafka-bronze',
    path: 'analytics',
    points: pts(nodePort('kafka', 'right'), [AN_X - 80, 160], nodePort('bronze', 'top')),
    label: 'ingest',
    labelX: 540,
    labelY: 208,
  },
  {
    id: 'e-bronze-silver',
    path: 'analytics',
    points: pts(nodePort('bronze', 'bottom'), nodePort('silver', 'top')),
    label: 'DBT',
    labelX: AN_X + 56,
    labelY: 310,
  },
  {
    id: 'e-silver-gold',
    path: 'analytics',
    points: pts(nodePort('silver', 'bottom'), nodePort('gold', 'top')),
    label: 'DBT',
    labelX: AN_X + 56,
    labelY: 405,
  },
  {
    id: 'e-gold-trino',
    path: 'analytics',
    points: pts(nodePort('gold', 'bottom'), nodePort('trino', 'top')),
    label: 'query',
    labelX: AN_X + 56,
    labelY: 472,
  },
];

// ── Particles ─────────────────────────────────────────────────────────────────

interface ParticleDef {
  edgeId: string;
  begin: string; // SMIL begin value (e.g. "0s", "0.8s")
  dur: string; // animation duration
  fill: string; // CSS variable
}

function buildParticles(): ParticleDef[] {
  const particles: ParticleDef[] = [];

  for (const edge of EDGES) {
    const isRT = edge.path === 'realtime';
    const dur = isRT ? '2.5s' : '4s';
    const fill = isRT ? 'var(--offline-neon)' : 'var(--offline-gold)';
    const count = isRT ? 3 : 2;
    const stagger = isRT ? 0.8 : 2;

    for (let i = 0; i < count; i++) {
      particles.push({
        edgeId: edge.id,
        begin: `${(i * stagger).toFixed(1)}s`,
        dur,
        fill,
      });
    }
  }

  return particles;
}

const PARTICLES = buildParticles();

// ── Sub-components ─────────────────────────────────────────────────────────────

function NodeRect({ node }: { node: NodeDef }) {
  const { cx, cy, w, h, label, subLabel, strokeColor, strokeOpacity = 1 } = node;
  const x = cx - w / 2;
  const y = cy - h / 2;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={12}
        fill="var(--offline-section-bg)"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeOpacity={strokeOpacity}
      />
      <text
        x={cx}
        y={subLabel ? cy - 5 : cy + 4}
        textAnchor="middle"
        fontSize="11"
        fill="var(--offline-text)"
        fontWeight="500"
      >
        {label}
      </text>
      {subLabel && (
        <text
          x={cx}
          y={cy + 10}
          textAnchor="middle"
          fontSize="10"
          fill="var(--offline-text-dimmest)"
        >
          {subLabel}
        </text>
      )}
    </g>
  );
}

function EdgeLine({ edge }: { edge: EdgeDef }) {
  const color = edge.path === 'realtime' ? 'var(--offline-neon)' : 'var(--offline-gold)';

  return (
    <g>
      <polyline
        id={edge.id}
        points={edge.points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeOpacity={0.35}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {edge.label && edge.labelX !== undefined && edge.labelY !== undefined && (
        <text
          x={edge.labelX}
          y={edge.labelY}
          fontSize="9"
          fill={color}
          fillOpacity={0.6}
          letterSpacing="0.1em"
          textAnchor="middle"
        >
          {edge.label.toUpperCase()}
        </text>
      )}
    </g>
  );
}

function Particles() {
  return (
    <>
      {PARTICLES.map((p, i) => (
        <ellipse key={`${p.edgeId}-p${i}`} rx={4} ry={2.5} fill={p.fill} fillOpacity={0.7}>
          <animateMotion dur={p.dur} begin={p.begin} repeatCount="indefinite" rotate="auto">
            <mpath href={`#${p.edgeId}`} />
          </animateMotion>
        </ellipse>
      ))}
    </>
  );
}

function StaticParticles() {
  // When prefers-reduced-motion is set, render small static dots at edge midpoints
  return (
    <>
      {EDGES.map((edge) => {
        const isRT = edge.path === 'realtime';
        const fill = isRT ? 'var(--offline-neon)' : 'var(--offline-gold)';
        // Parse midpoint from points string (average of first and last coordinate)
        const coordPairs = edge.points.split(' ').map((p) => p.split(',').map(Number));
        const first = coordPairs[0] ?? [0, 0];
        const last = coordPairs[coordPairs.length - 1] ?? [0, 0];
        const mx = ((first[0] ?? 0) + (last[0] ?? 0)) / 2;
        const my = ((first[1] ?? 0) + (last[1] ?? 0)) / 2;

        return (
          <ellipse
            key={`static-${edge.id}`}
            cx={mx}
            cy={my}
            rx={4}
            ry={2.5}
            fill={fill}
            fillOpacity={0.5}
          />
        );
      })}
    </>
  );
}

// ── Path labels ───────────────────────────────────────────────────────────────

function PathLabels() {
  return (
    <>
      <text
        x={RT_X}
        y={22}
        textAnchor="middle"
        fontSize="10"
        fill="var(--offline-neon)"
        fillOpacity={0.7}
        letterSpacing="0.1em"
      >
        REAL-TIME PATH
      </text>
      <text
        x={AN_X}
        y={22}
        textAnchor="middle"
        fontSize="10"
        fill="var(--offline-gold)"
        fillOpacity={0.7}
        letterSpacing="0.1em"
      >
        ANALYTICS PATH
      </text>
    </>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function ArchitectureDiagram() {
  const reducedMotion = prefersReducedMotion();

  return (
    <section id="architecture">
      <h2>System Architecture</h2>
      <svg
        viewBox="0 0 800 520"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="System architecture diagram showing real-time and analytics data-flow paths"
        style={{ width: '100%', maxWidth: '800px', display: 'block', margin: '0 auto' }}
      >
        {/* Column labels */}
        <PathLabels />

        {/* Edges drawn first so nodes sit on top */}
        {EDGES.map((edge) => (
          <EdgeLine key={edge.id} edge={edge} />
        ))}

        {/* Nodes */}
        {NODES.map((node) => (
          <NodeRect key={node.id} node={node} />
        ))}

        {/* Particles — SMIL animations or static midpoints */}
        {reducedMotion ? <StaticParticles /> : <Particles />}
      </svg>
    </section>
  );
}
