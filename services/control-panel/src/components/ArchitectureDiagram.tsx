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
// viewBox: 0 0 800 560
// Left column (real-time): x≈130, right column (analytics): x≈620
// Kafka hub sits in the centre: x≈375, y≈160

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
    cy: 350,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-neon)',
  },
  {
    id: 'ws',
    label: 'WebSocket Server',
    subLabel: 'FastAPI',
    cx: RT_X,
    cy: 435,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-neon)',
  },
  {
    id: 'frontend',
    label: 'React Frontend',
    subLabel: 'deck.gl',
    cx: RT_X,
    cy: 520,
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
    cy: 350,
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
    cy: 435,
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
    cy: 520,
    w: 160,
    h: 46,
    strokeColor: 'var(--offline-gold)',
    strokeOpacity: 0.7,
  },

  // Cross-path feedback loop
  {
    id: 'perfctrl',
    label: 'Perf Controller',
    subLabel: 'PID auto-throttle',
    cx: KF_X,
    cy: 60,
    w: 140,
    h: 40,
    strokeColor: 'var(--offline-text-dimmest)',
    strokeOpacity: 0.6,
  },
];

// ── Edge definitions ──────────────────────────────────────────────────────────

interface EdgeDef {
  id: string;
  d: string; // SVG path d attribute (M…L… commands)
  path: 'realtime' | 'analytics' | 'feedback';
  label?: string;
  labelX?: number;
  labelY?: number;
  dashed?: boolean;
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

function pathD(...coords: [number, number][]): string {
  return coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x},${y}`).join(' ');
}

const EDGES: EdgeDef[] = [
  // Real-time path
  {
    id: 'e-sim-kafka',
    path: 'realtime',
    d: pathD(nodePort('sim', 'bottom'), [RT_X, 120], [KF_X, 120], nodePort('kafka', 'top')),
    label: 'events',
    labelX: (RT_X + KF_X) / 2,
    labelY: 113,
  },
  {
    id: 'e-kafka-stream',
    path: 'realtime',
    d: pathD(nodePort('kafka', 'left'), [RT_X + 80, 160], nodePort('stream', 'top')),
    label: 'consume',
    labelX: 175,
    labelY: 208,
  },
  {
    id: 'e-stream-redis',
    path: 'realtime',
    d: pathD(nodePort('stream', 'bottom'), nodePort('redis', 'top')),
    label: 'fan-out',
    labelX: RT_X + 56,
    labelY: 308,
  },
  {
    id: 'e-redis-ws',
    path: 'realtime',
    d: pathD(nodePort('redis', 'bottom'), nodePort('ws', 'top')),
    label: 'push',
    labelX: RT_X + 56,
    labelY: 395,
  },
  {
    id: 'e-ws-frontend',
    path: 'realtime',
    d: pathD(nodePort('ws', 'bottom'), nodePort('frontend', 'top')),
    label: 'WS',
    labelX: RT_X + 56,
    labelY: 480,
  },

  // Analytics path
  {
    id: 'e-kafka-bronze',
    path: 'analytics',
    d: pathD(nodePort('kafka', 'right'), [AN_X - 80, 160], nodePort('bronze', 'top')),
    label: 'ingest',
    labelX: 540,
    labelY: 208,
  },
  {
    id: 'e-bronze-silver',
    path: 'analytics',
    d: pathD(nodePort('bronze', 'bottom'), nodePort('silver', 'top')),
    label: 'DBT',
    labelX: AN_X + 56,
    labelY: 308,
  },
  {
    id: 'e-silver-gold',
    path: 'analytics',
    d: pathD(nodePort('silver', 'bottom'), nodePort('gold', 'top')),
    label: 'DBT',
    labelX: AN_X + 56,
    labelY: 395,
  },
  {
    id: 'e-gold-trino',
    path: 'analytics',
    d: pathD(nodePort('gold', 'bottom'), nodePort('trino', 'top')),
    label: 'query',
    labelX: AN_X + 56,
    labelY: 480,
  },

  // Perf Controller feedback loop (dashed)
  {
    id: 'e-perfctrl-sim',
    path: 'feedback',
    d: pathD(nodePort('perfctrl', 'left'), nodePort('sim', 'right')),
    label: 'actuate',
    labelX: (RT_X + KF_X) / 2,
    labelY: 53,
    dashed: true,
  },
  {
    id: 'e-prom-perfctrl',
    path: 'feedback',
    d: pathD([AN_X - 80, 520], [AN_X - 80, 0], [KF_X + 70, 0], nodePort('perfctrl', 'top')),
    label: 'headroom',
    labelX: (AN_X - 80 + KF_X + 70) / 2,
    labelY: -6,
    dashed: true,
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
    if (edge.path === 'feedback') continue; // no particles on dashed feedback edges
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

function edgeColor(path: EdgeDef['path']): string {
  if (path === 'realtime') return 'var(--offline-neon)';
  if (path === 'analytics') return 'var(--offline-gold)';
  return 'var(--offline-text-dimmest)';
}

function EdgeLine({ edge }: { edge: EdgeDef }) {
  const color = edgeColor(edge.path);

  return (
    <g>
      <path
        id={edge.id}
        d={edge.d}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeOpacity={0.35}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={edge.dashed ? '6 4' : undefined}
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
      {EDGES.filter((e) => e.path !== 'feedback').map((edge) => {
        const isRT = edge.path === 'realtime';
        const fill = isRT ? 'var(--offline-neon)' : 'var(--offline-gold)';
        // Parse midpoint from path d attribute (average of first and last coordinate)
        const coordPairs = edge.d.match(/[ML]([\d.]+),([\d.]+)/g)?.map((m) => {
          const parts = m.slice(1).split(',').map(Number);
          return [parts[0] ?? 0, parts[1] ?? 0];
        }) ?? [[0, 0]];
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
        viewBox="0 -10 800 580"
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
