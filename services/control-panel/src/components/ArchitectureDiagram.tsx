// ArchitectureDiagram — inline SVG showing the platform's three data-flow paths.
// Observability path (left): Services →← OTel Collector → Prometheus → Perf Controller → Simulation
// Real-time path (centre): Simulation → Kafka → Stream Processor → Redis → WebSocket → Frontend
// Analytics path (right): Kafka → Bronze → Silver → Gold → Trino + Grafana
// SMIL <animateMotion> particles animate along each edge, gated behind prefers-reduced-motion.

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

// ── Node layout ────────────────────────────────────────────────────────────────
// Left column (observability): x≈130
// Centre column (real-time): x≈400, Kafka hub at y≈160
// Right column (analytics): x≈670

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

const OB_X = 130; // observability column (left)
const RT_X = 400; // real-time column (centre)
const AN_X = 670; // analytics column (right)

const NODES: NodeDef[] = [
  // Real-time path (centre column)
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
    cx: RT_X,
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

  // Cross-path feedback loop (observability column)
  {
    id: 'perfctrl',
    label: 'Perf Controller',
    subLabel: 'PID auto-throttle',
    cx: OB_X,
    cy: 60,
    w: 140,
    h: 40,
    strokeColor: 'var(--offline-feedback)',
    strokeOpacity: 0.7,
  },

  // Observability path (left column)
  {
    id: 'otel',
    label: 'OTel Collector',
    subLabel: 'Metrics · Logs · Traces',
    cx: OB_X,
    cy: 160,
    w: 140,
    h: 40,
    strokeColor: 'var(--offline-feedback)',
    strokeOpacity: 0.5,
  },
  {
    id: 'prom',
    label: 'Prometheus',
    subLabel: 'Recording rules',
    cx: OB_X,
    cy: 260,
    w: 140,
    h: 40,
    strokeColor: 'var(--offline-feedback)',
    strokeOpacity: 0.5,
  },
];

// ── Edge definitions ──────────────────────────────────────────────────────────

interface EdgeDef {
  id: string;
  d: string; // SVG path d attribute (M…L… commands)
  path: 'realtime' | 'analytics' | 'feedback' | 'scrape';
  label?: string;
  labelX?: number;
  labelY?: number;
  labelRotate?: number;
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
  // Real-time path (straight vertical in centre column)
  {
    id: 'e-sim-kafka',
    path: 'realtime',
    d: pathD(nodePort('sim', 'bottom'), nodePort('kafka', 'top')),
    label: 'events',
    labelX: RT_X + 56,
    labelY: 113,
  },
  {
    id: 'e-kafka-stream',
    path: 'realtime',
    d: pathD(nodePort('kafka', 'bottom'), nodePort('stream', 'top')),
    label: 'consume',
    labelX: RT_X + 56,
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

  // Analytics path (branches right from Kafka)
  {
    id: 'e-kafka-bronze',
    path: 'analytics',
    d: pathD(nodePort('kafka', 'right'), [AN_X - 80, 160], nodePort('bronze', 'top')),
    label: 'ingest',
    labelX: AN_X - 40,
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
    d: pathD(nodePort('perfctrl', 'right'), nodePort('sim', 'left')),
    label: 'actuate',
    labelX: (OB_X + RT_X) / 2,
    labelY: 53,
    dashed: true,
  },
  {
    id: 'e-prom-perfctrl',
    path: 'feedback',
    d: pathD(nodePort('prom', 'left'), [20, 260], [20, 60], nodePort('perfctrl', 'left')),
    label: 'infrastructure headroom',
    labelX: 10,
    labelY: 160,
    labelRotate: -90,
    dashed: true,
  },

  // Observability: OTel Collector → Prometheus (solid, left column)
  {
    id: 'e-otel-prom',
    path: 'feedback',
    d: pathD(nodePort('otel', 'bottom'), nodePort('prom', 'top')),
    label: 'remote write',
    labelX: OB_X + 56,
    labelY: 213,
  },

  // Scrape / OTLP push lines (faint background)
  {
    id: 'e-sim-otel',
    path: 'scrape',
    d: pathD(nodePort('sim', 'left'), nodePort('otel', 'right')),
  },
  {
    id: 'e-stream-otel',
    path: 'scrape',
    d: pathD(nodePort('stream', 'left'), nodePort('otel', 'right')),
  },
  // Prometheus scrape lines (faint)
  {
    id: 'e-prom-kafka-scrape',
    path: 'scrape',
    d: pathD(nodePort('prom', 'right'), nodePort('kafka', 'left')),
  },
  {
    id: 'e-prom-redis-scrape',
    path: 'scrape',
    d: pathD(nodePort('prom', 'right'), nodePort('redis', 'left')),
  },
];

// ── Particles ─────────────────────────────────────────────────────────────────

interface ParticleDef {
  edgeId: string;
  begin: string; // SMIL begin value (e.g. "0s", "0.8s")
  dur: string; // animation duration
  fill: string; // CSS variable
  opacity: number;
  boomerang?: boolean;
}

function buildParticles(): ParticleDef[] {
  const particles: ParticleDef[] = [];

  for (const edge of EDGES) {
    if (edge.path === 'feedback') continue; // no particles on dashed feedback edges
    const isScrape = edge.path === 'scrape';
    const isRT = edge.path === 'realtime';
    const dur = isScrape ? '3s' : isRT ? '2.5s' : '4s';
    const fill = isScrape
      ? 'var(--offline-feedback)'
      : isRT
        ? 'var(--offline-neon)'
        : 'var(--offline-gold)';
    const count = isScrape ? 1 : isRT ? 3 : 2;
    const stagger = isScrape ? 0 : isRT ? 0.8 : 2;
    const opacity = isScrape ? 0.3 : 0.7;

    for (let i = 0; i < count; i++) {
      particles.push({
        edgeId: edge.id,
        begin: `${(i * stagger).toFixed(1)}s`,
        dur,
        fill,
        opacity,
        boomerang: isScrape && edge.id.includes('scrape'),
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
  if (path === 'scrape') return 'var(--offline-feedback)';
  return 'var(--offline-feedback)';
}

function EdgeLine({ edge }: { edge: EdgeDef }) {
  const color = edgeColor(edge.path);
  const isScrape = edge.path === 'scrape';

  return (
    <g>
      <path
        id={edge.id}
        d={edge.d}
        fill="none"
        stroke={color}
        strokeWidth={isScrape ? 1 : 1.5}
        strokeOpacity={isScrape ? 0.12 : 0.35}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={isScrape ? '3 3' : edge.dashed ? '6 4' : undefined}
      />
      {edge.label && edge.labelX !== undefined && edge.labelY !== undefined && (
        <text
          x={edge.labelX}
          y={edge.labelY}
          fontSize="9"
          fill={color}
          fillOpacity={isScrape ? 0.3 : 0.6}
          letterSpacing="0.1em"
          textAnchor="middle"
          transform={
            edge.labelRotate
              ? `rotate(${edge.labelRotate} ${edge.labelX} ${edge.labelY})`
              : undefined
          }
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
        <ellipse key={`${p.edgeId}-p${i}`} rx={4} ry={2.5} fill={p.fill} fillOpacity={p.opacity}>
          <animateMotion
            dur={p.dur}
            begin={p.begin}
            repeatCount="indefinite"
            rotate="auto"
            keyPoints={p.boomerang ? '0;1;0' : undefined}
            keyTimes={p.boomerang ? '0;0.5;1' : undefined}
            calcMode={p.boomerang ? 'linear' : undefined}
          >
            <mpath href={`#${p.edgeId}`} />
          </animateMotion>
          {p.boomerang && (
            <animate
              attributeName="fill-opacity"
              values={`0.1;0.1;${p.opacity};${p.opacity}`}
              keyTimes="0;0.49;0.51;1"
              dur={p.dur}
              begin={p.begin}
              repeatCount="indefinite"
            />
          )}
        </ellipse>
      ))}
    </>
  );
}

function FeedbackParticles() {
  const feedbackEdges = EDGES.filter((e) => e.path === 'feedback');
  const particles: { edgeId: string; begin: string; dur: string }[] = [];

  for (const edge of feedbackEdges) {
    // 2 slower particles per feedback edge, staggered
    for (let i = 0; i < 2; i++) {
      particles.push({
        edgeId: edge.id,
        begin: `${(i * 3).toFixed(1)}s`,
        dur: '6s',
      });
    }
  }

  return (
    <>
      {particles.map((p, i) => (
        <polygon
          key={`fb-${p.edgeId}-${i}`}
          points="-4,0 0,-3 4,0 0,3"
          fill="var(--offline-feedback)"
          fillOpacity={0.8}
        >
          <animateMotion dur={p.dur} begin={p.begin} repeatCount="indefinite" rotate="auto">
            <mpath href={`#${p.edgeId}`} />
          </animateMotion>
          <animate
            attributeName="fill-opacity"
            values="0.3;0.9;0.3"
            dur="1.5s"
            begin={p.begin}
            repeatCount="indefinite"
          />
        </polygon>
      ))}
    </>
  );
}

function StaticParticles() {
  // When prefers-reduced-motion is set, render small static dots at edge midpoints
  return (
    <>
      {EDGES.filter((e) => e.path !== 'scrape').map((edge) => {
        const fill =
          edge.path === 'realtime'
            ? 'var(--offline-neon)'
            : edge.path === 'analytics'
              ? 'var(--offline-gold)'
              : 'var(--offline-feedback)';
        const isFeedback = edge.path === 'feedback';
        // Parse midpoint from path d attribute (average of first and last coordinate)
        const coordPairs = edge.d.match(/[ML]([\d.]+),([\d.]+)/g)?.map((m) => {
          const parts = m.slice(1).split(',').map(Number);
          return [parts[0] ?? 0, parts[1] ?? 0];
        }) ?? [[0, 0]];
        const first = coordPairs[0] ?? [0, 0];
        const last = coordPairs[coordPairs.length - 1] ?? [0, 0];
        const mx = ((first[0] ?? 0) + (last[0] ?? 0)) / 2;
        const my = ((first[1] ?? 0) + (last[1] ?? 0)) / 2;

        return isFeedback ? (
          <polygon
            key={`static-${edge.id}`}
            points={`${mx - 4},${my} ${mx},${my - 3} ${mx + 4},${my} ${mx},${my + 3}`}
            fill={fill}
            fillOpacity={0.5}
          />
        ) : (
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
        fontWeight="700"
        fill="var(--offline-neon)"
        fillOpacity={0.7}
        letterSpacing="0.1em"
      >
        REAL-TIME PATH
      </text>
      <text
        x={AN_X}
        y={160}
        textAnchor="middle"
        fontSize="10"
        fontWeight="700"
        fill="var(--offline-gold)"
        fillOpacity={0.7}
        letterSpacing="0.1em"
      >
        ANALYTICS PATH
      </text>
      <text
        x={OB_X}
        y={130}
        textAnchor="middle"
        fontSize="10"
        fontWeight="700"
        fill="var(--offline-feedback)"
        fillOpacity={0.5}
        letterSpacing="0.1em"
      >
        OBSERVABILITY
      </text>
      <text
        x={OB_X + 80}
        y={164}
        textAnchor="start"
        fontSize="9"
        fill="var(--offline-feedback)"
        fillOpacity={0.3}
        letterSpacing="0.1em"
      >
        OTLP
      </text>
      <text
        x={OB_X + 80}
        y={264}
        textAnchor="start"
        fontSize="9"
        fill="var(--offline-feedback)"
        fillOpacity={0.3}
        letterSpacing="0.1em"
      >
        SCRAPE
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

        {/* Background scrape/monitoring lines (behind everything) */}
        {EDGES.filter((e) => e.path === 'scrape').map((edge) => (
          <EdgeLine key={edge.id} edge={edge} />
        ))}

        {/* Main edges */}
        {EDGES.filter((e) => e.path !== 'scrape').map((edge) => (
          <EdgeLine key={edge.id} edge={edge} />
        ))}

        {/* Particles — behind nodes for smoother flow through blocks */}
        {reducedMotion ? (
          <StaticParticles />
        ) : (
          <>
            <Particles />
            <FeedbackParticles />
          </>
        )}

        {/* Nodes */}
        {NODES.map((node) => (
          <NodeRect key={node.id} node={node} />
        ))}
      </svg>
    </section>
  );
}
