import type { FunctionComponent, SVGProps } from 'react';
import { useEffect, useState } from 'react';
import {
  SiPython,
  SiFastapi,
  SiPydantic,
  SiH3,
  SiApachekafka,
  SiRedis,
  SiMinio,
  SiTrino,
  SiApachehive,
  SiDuckdb,
  SiPostgresql,
  SiApacheairflow,
  SiReact,
  SiTypescript,
  SiMaplibre,
  SiPrometheus,
  SiGrafana,
  SiOpentelemetry,
  SiDocker,
  SiKubernetes,
  SiTerraform,
  SiGithubactions,
} from '@icons-pack/react-simple-icons';
import {
  SiPythonHex,
  SiFastapiHex,
  SiPydanticHex,
  SiH3Hex,
  SiApachekafkaHex,
  SiRedisHex,
  SiMinioHex,
  SiTrinoHex,
  SiApachehiveHex,
  SiDuckdbHex,
  SiPostgresqlHex,
  SiApacheairflowHex,
  SiReactHex,
  SiTypescriptHex,
  SiMaplibreHex,
  SiPrometheusHex,
  SiGrafanaHex,
  SiOpentelemetryHex,
  SiDockerHex,
  SiKubernetesHex,
  SiTerraformHex,
  SiGithubactionsHex,
} from '@icons-pack/react-simple-icons';
import DeltaLakeIcon from '../../public/icons/tech/delta-lake.svg?react';
import DbtIcon from '../../public/icons/tech/dbt.svg?react';
import GreatExpectationsIcon from '../../public/icons/tech/great-expectations.svg?react';
import SimpyIcon from '../../public/icons/tech/simpy.svg?react';
import LokiIcon from '../../public/icons/tech/loki.svg?react';
import TempoIcon from '../../public/icons/tech/tempo.svg?react';
import DeckGlIcon from '../../public/icons/tech/deck-gl.svg?react';
import OsrmIcon from '../../public/icons/tech/osrm.svg?react';
import ArgocdIcon from '../../public/icons/tech/argocd.svg?react';
import AwsIcon from '../../public/icons/tech/aws.svg?react';
import PerfControllerIcon from '../../public/icons/tech/performance-controller.svg?react';
import { useActiveSection } from '../hooks/useActiveSection';
import { useCountUp } from '../hooks/useCountUp';
import { useInView } from '../hooks/useInView';
import Zoom from 'react-medium-image-zoom';
import { ArchitectureDiagram } from './ArchitectureDiagram';
import { TripLifecycleAnimation } from './TripLifecycleAnimation';
import DeployPanel from './DeployPanel';

const LINKEDIN_URL = 'https://www.linkedin.com/in/andresbrocco/';

type IconComponent = FunctionComponent<SVGProps<SVGSVGElement>>;

interface TechBadge {
  label: string;
  icon: IconComponent;
  iconColor: string;
  tooltip: string;
}

interface TechGroup {
  title: string;
  badges: TechBadge[];
}

const SELF_HOSTED_COLOR = '#4daa6e';

const TECH_GROUPS: TechGroup[] = [
  {
    title: 'Simulation',
    badges: [
      {
        label: 'Python 3.13',
        icon: SiPython,
        iconColor: SiPythonHex,
        tooltip: 'Simulation engine, pipelines, and tooling runtime',
      },
      {
        label: 'SimPy',
        icon: SimpyIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Discrete-event simulation with generator-based coroutines',
      },
      {
        label: 'FastAPI',
        icon: SiFastapi,
        iconColor: SiFastapiHex,
        tooltip: 'REST API and WebSocket server for simulation control',
      },
      {
        label: 'Pydantic',
        icon: SiPydantic,
        iconColor: SiPydanticHex,
        tooltip: 'Data validation, settings, and immutable DNA models',
      },
      {
        label: 'H3',
        icon: SiH3,
        iconColor: SiH3Hex,
        tooltip: 'Uber H3 hexagonal geospatial indexing for O(1) driver lookups',
      },
      {
        label: 'OSRM',
        icon: OsrmIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Real Sao Paulo road network routing via OpenStreetMap',
      },
    ],
  },
  {
    title: 'Streaming',
    badges: [
      {
        label: 'Apache Kafka',
        icon: SiApachekafka,
        iconColor: SiApachekafkaHex,
        tooltip: 'Event backbone with 8 topics and SASL/PLAIN auth',
      },
      {
        label: 'Schema Registry',
        icon: SiApachekafka,
        iconColor: SiApachekafkaHex,
        tooltip: 'JSON Schema Draft 7 validation for all event contracts',
      },
      {
        label: 'Redis',
        icon: SiRedis,
        iconColor: SiRedisHex,
        tooltip: 'Real-time state snapshots and pub/sub fan-out',
      },
    ],
  },
  {
    title: 'Storage',
    badges: [
      {
        label: 'Delta Lake',
        icon: DeltaLakeIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'ACID lakehouse tables via delta-rs (no JVM, 94% less memory)',
      },
      {
        label: 'MinIO / S3',
        icon: SiMinio,
        iconColor: SiMinioHex,
        tooltip: 'Object storage for Bronze, Silver, and Gold layers',
      },
      {
        label: 'Apache Trino',
        icon: SiTrino,
        iconColor: SiTrinoHex,
        tooltip: 'Interactive SQL engine over Delta Lake with partition pruning',
      },
      {
        label: 'Hive Metastore',
        icon: SiApachehive,
        iconColor: SiApachehiveHex,
        tooltip: 'Table metadata catalog for Trino discovery',
      },
      {
        label: 'DuckDB',
        icon: SiDuckdb,
        iconColor: SiDuckdbHex,
        tooltip: 'In-process analytics engine for DBT and Airflow DLQ queries',
      },
      {
        label: 'PostgreSQL',
        icon: SiPostgresql,
        iconColor: SiPostgresqlHex,
        tooltip: 'Metadata storage for Airflow and Hive Metastore',
      },
    ],
  },
  {
    title: 'Transformation',
    badges: [
      {
        label: 'dbt',
        icon: DbtIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Bronze-to-Silver-to-Gold SQL transformations with ~40 tests',
      },
      {
        label: 'Apache Airflow',
        icon: SiApacheairflow,
        iconColor: SiApacheairflowHex,
        tooltip: '4 DAGs orchestrating pipelines (hourly to daily)',
      },
      {
        label: 'Great Expectations',
        icon: GreatExpectationsIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Data quality validation checkpoints on Silver and Gold',
      },
    ],
  },
  {
    title: 'Frontend',
    badges: [
      {
        label: 'React',
        icon: SiReact,
        iconColor: SiReactHex,
        tooltip: 'UI framework (v19) for control panel and landing page',
      },
      {
        label: 'TypeScript',
        icon: SiTypescript,
        iconColor: SiTypescriptHex,
        tooltip: 'Type-safe frontend with OpenAPI-generated API types',
      },
      {
        label: 'deck.gl',
        icon: DeckGlIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'WebGL visualization of agents, routes, and heatmaps',
      },
      {
        label: 'MapLibre',
        icon: SiMaplibre,
        iconColor: SiMaplibreHex,
        tooltip: 'Open-source map rendering engine',
      },
    ],
  },
  {
    title: 'Observability',
    badges: [
      {
        label: 'Prometheus',
        icon: SiPrometheus,
        iconColor: SiPrometheusHex,
        tooltip: 'Metrics time-series storage with 7-day retention',
      },
      {
        label: 'Grafana',
        icon: SiGrafana,
        iconColor: SiGrafanaHex,
        tooltip: '10 dashboards across 5 categories with 4 datasources',
      },
      {
        label: 'Loki',
        icon: LokiIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Log aggregation with PII masking',
      },
      {
        label: 'Tempo',
        icon: TempoIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Distributed tracing with correlation IDs',
      },
      {
        label: 'OpenTelemetry',
        icon: SiOpentelemetry,
        iconColor: SiOpentelemetryHex,
        tooltip: 'Unified telemetry gateway (metrics, logs, traces)',
      },
      {
        label: 'Perf Controller',
        icon: PerfControllerIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip:
          'PID auto-throttle sidecar — reads infrastructure headroom from Prometheus, adjusts simulation speed',
      },
    ],
  },
  {
    title: 'DevOps',
    badges: [
      {
        label: 'Docker',
        icon: SiDocker,
        iconColor: SiDockerHex,
        tooltip: 'Compose orchestration with 32 services across 4 profiles',
      },
      {
        label: 'Kubernetes',
        icon: SiKubernetes,
        iconColor: SiKubernetesHex,
        tooltip: 'EKS cluster with Kustomize overlays for local/prod parity',
      },
      {
        label: 'Terraform',
        icon: SiTerraform,
        iconColor: SiTerraformHex,
        tooltip: 'Three-layer IaC: bootstrap, foundation, platform',
      },
      {
        label: 'ArgoCD',
        icon: ArgocdIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'GitOps deployment watching deploy branch with self-heal',
      },
      {
        label: 'GitHub Actions',
        icon: SiGithubactions,
        iconColor: SiGithubactionsHex,
        tooltip: 'CI/CD: lint, type-check, unit tests, integration tests',
      },
    ],
  },
  {
    title: 'Cloud (AWS)',
    badges: [
      {
        label: 'EKS',
        icon: AwsIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Managed Kubernetes with Pod Identity for workload IAM',
      },
      {
        label: 'S3',
        icon: AwsIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Object storage for Bronze, Silver, Gold layers (prod)',
      },
      {
        label: 'RDS',
        icon: AwsIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Managed PostgreSQL for Airflow and Hive Metastore (prod)',
      },
      {
        label: 'CloudFront',
        icon: AwsIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'CDN for frontend and API distribution',
      },
      {
        label: 'Lambda',
        icon: AwsIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Serverless functions for event processing',
      },
      {
        label: 'Secrets Manager',
        icon: AwsIcon,
        iconColor: SELF_HOSTED_COLOR,
        tooltip: 'Credential management (LocalStack locally, AWS in prod)',
      },
    ],
  },
];

function TechBadgeItem({ badge }: { badge: TechBadge }) {
  const Icon = badge.icon;
  return (
    <span className="tech-badge" data-tooltip={badge.tooltip} tabIndex={0}>
      <Icon
        width={16}
        height={16}
        style={{ color: badge.iconColor, flexShrink: 0 }}
        aria-hidden="true"
      />
      {badge.label}
    </span>
  );
}

function TechGroupCard({ group }: { group: TechGroup }) {
  return (
    <div className="tech-group-card">
      <span className="tech-group-title">{group.title}</span>
      <div className="tech-badge-grid">
        {group.badges.map((badge) => (
          <TechBadgeItem key={badge.label} badge={badge} />
        ))}
      </div>
    </div>
  );
}

function TechStack() {
  return (
    <section id="tech-stack" className="landing-section tech-stack-section">
      <h2>Technology Stack</h2>
      <div className="tech-group-grid">
        {TECH_GROUPS.map((group) => (
          <TechGroupCard key={group.title} group={group} />
        ))}
      </div>
    </section>
  );
}

interface ExternalService {
  name: string;
  url: string;
  desc: string;
  icon: IconComponent;
  iconColor: string;
}

function getExternalServices(isLocal: boolean): ExternalService[] {
  return [
    {
      name: 'Grafana',
      url: isLocal
        ? 'http://localhost:3001'
        : 'https://grafana.ridesharing.portfolio.andresbrocco.com',
      desc: 'Multi-datasource dashboards — metrics, logs, traces, and BI analytics',
      icon: SiGrafana,
      iconColor: `#${SiGrafanaHex}`,
    },
    {
      name: 'Airflow',
      url: isLocal
        ? 'http://localhost:8082'
        : 'https://airflow.ridesharing.portfolio.andresbrocco.com',
      desc: '4 DAGs orchestrating Bronze → Silver → Gold transformations',
      icon: SiApacheairflow,
      iconColor: `#${SiApacheairflowHex}`,
    },
    {
      name: 'Trino',
      url: isLocal
        ? 'http://localhost:8084'
        : 'https://trino.ridesharing.portfolio.andresbrocco.com',
      desc: 'Interactive SQL over Delta Lake — query the star schema live',
      icon: SiTrino,
      iconColor: `#${SiTrinoHex}`,
    },
    {
      name: 'Prometheus',
      url: isLocal
        ? 'http://localhost:9090'
        : 'https://prometheus.ridesharing.portfolio.andresbrocco.com',
      desc: 'Raw metrics and PromQL — simulation KPIs and container resources',
      icon: SiPrometheus,
      iconColor: `#${SiPrometheusHex}`,
    },
    {
      name: 'Simulation API',
      url: isLocal
        ? 'http://localhost:8000/docs'
        : 'https://api.ridesharing.portfolio.andresbrocco.com/docs',
      desc: 'FastAPI Swagger docs — start sessions, spawn agents, control speed',
      icon: SiFastapi,
      iconColor: `#${SiFastapiHex}`,
    },
  ];
}

const STATS = [
  { target: 30, suffix: '+', label: 'Technologies' },
  { target: 2000, suffix: '+', label: 'Tests' },
  { target: 10, suffix: '', label: 'Grafana Dashboards' },
  { target: 3, suffix: '', label: 'Terraform Layers' },
] as const;

interface StatCardProps {
  target: number;
  suffix: string;
  label: string;
}

function StatCard({ target, suffix, label }: StatCardProps) {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [ref, isInView] = useInView<HTMLDivElement>({ threshold: 0.4, triggerOnce: true });
  const count = useCountUp({ target, start: isInView || prefersReducedMotion });

  return (
    <div ref={ref} className="stat-card">
      <span className="stat-number">
        {count}
        {suffix}
      </span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

function StatBar() {
  return (
    <div className="stat-bar">
      {STATS.map((stat) => (
        <StatCard key={stat.label} target={stat.target} suffix={stat.suffix} label={stat.label} />
      ))}
    </div>
  );
}

const NAV_SECTIONS = ['architecture', 'tech-stack', 'deep-dives', 'explore'] as const;

const NAV_LABELS: Record<(typeof NAV_SECTIONS)[number], string> = {
  architecture: 'Architecture',
  'tech-stack': 'Tech Stack',
  'deep-dives': 'Deep Dives',
  explore: 'Explore',
};

interface SectionNavProps {
  heroVisible: boolean;
}

function SectionNav({ heroVisible }: SectionNavProps) {
  const activeId = useActiveSection(NAV_SECTIONS);

  function handleNavClick(id: string) {
    const el = document.getElementById(id);
    if (!el) return;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' });
  }

  return (
    <nav
      className={`section-nav${heroVisible ? '' : ' section-nav--visible'}`}
      aria-label="Page sections"
    >
      {NAV_SECTIONS.map((id) => (
        <button
          key={id}
          className={`section-nav-btn${activeId === id ? ' section-nav-btn--active' : ''}`}
          onClick={() => handleNavClick(id)}
          type="button"
          aria-current={activeId === id ? true : undefined}
        >
          {NAV_LABELS[id]}
        </button>
      ))}
    </nav>
  );
}

interface LandingPageProps {
  onLoginClick: () => void;
  isLocal: boolean;
  servicesAvailable: boolean;
  apiKey: string | null;
  onNeedAuth: () => void;
  onServicesChange: (up: boolean) => void;
}

export function LandingPage({
  onLoginClick,
  isLocal,
  servicesAvailable,
  apiKey,
  onNeedAuth,
  onServicesChange,
}: LandingPageProps) {
  const [heroVisible, setHeroVisible] = useState(true);

  useEffect(() => {
    const hero = document.getElementById('hero');
    if (!hero) return;

    const observer = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setHeroVisible(entry.isIntersecting);
      }
    });

    observer.observe(hero);

    return () => {
      observer.disconnect();
    };
  }, []);

  return (
    <div className="landing-container">
      <div className="landing-inner">
        <div id="hero" className="landing-hero">
          <div className="landing-hero-glow" />
          <h1>Rideshare Simulation Platform</h1>
          <p className="landing-subtitle">
            Real-time Event-Driven Data Engineering &mdash; Portfolio Project
          </p>
        </div>

        <SectionNav heroVisible={heroVisible} />

        <TripLifecycleAnimation />

        <StatBar />

        <div className="landing-body">
          <ArchitectureDiagram />

          <TechStack />

          <section id="deep-dives" className="landing-section">
            <h2>Deep Dives</h2>

            {/* ── Deep Dive 1: Simulation Engine ────────────────────── */}
            <details className="deep-dive">
              <summary className="deep-dive-summary">
                <span className="deep-dive-icon" aria-hidden="true">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    width="24"
                    height="24"
                  >
                    <path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16zm-1-5h2v2h-2v-2zm0-8h2v6h-2V7z" />
                  </svg>
                </span>
                <div className="deep-dive-header">
                  <span className="deep-dive-title">Simulation Engine</span>
                  <span className="deep-dive-preview">
                    SimPy discrete-event simulation with DNA-based autonomous agents, H3 geospatial
                    matching, and real Sao Paulo road network routing.
                  </span>
                </div>
                <span className="deep-dive-chevron" aria-hidden="true">
                  &#x203A;
                </span>
              </summary>
              <div className="deep-dive-content">
                <h3>DNA-Based Agent Behavior</h3>
                <p>
                  Immutable behavioral genotypes (Pydantic <code>frozen=True</code>) assigned at
                  creation.
                  <code>DriverDNA</code> governs acceptance rate, patience, and service quality.{' '}
                  <code>RiderDNA</code> governs patience threshold and tipping behavior. Different
                  DNA distributions produce emergent platform dynamics.
                </p>

                <h3>H3 Geospatial Matching</h3>
                <p>
                  Uber H3 hexagons at resolution&nbsp;7 (~5.2&nbsp;km) index driver locations. O(1)
                  neighbor lookups via <code>h3.grid_ring(cell, k=1)</code>. Matching cycles run
                  with dynamic surge pricing updated every 60 simulated seconds.
                </p>

                <h3>Real Road Network</h3>
                <p>
                  OSRM loaded with actual OpenStreetMap data for Sao Paulo. Routes reflect real road
                  geometry, turn restrictions, and travel times.
                </p>

                <h3>Time Acceleration</h3>
                <p>
                  0.5x to 128x real-time speed multiplier. Two-phase pause protocol (RUNNING &rarr;
                  DRAINING &rarr; PAUSED) guarantees no mid-execution trips during checkpoints.
                </p>

                <h3>State Machines &amp; Thread Safety</h3>
                <ul>
                  <li>
                    Enum-based states with <code>VALID_TRANSITIONS</code> enforcement. Terminal
                    states reject further transitions.
                  </li>
                  <li>Events emitted on every state transition for full audit trail.</li>
                  <li>
                    ThreadCoordinator command queue bridges the FastAPI async thread and SimPy
                    simulation thread safely.
                  </li>
                </ul>

                <Zoom>
                  <img
                    src="/screenshots/control-panel-map.svg"
                    alt="Control panel map view showing drivers, riders, active routes, and zone hexagons overlaid on the Sao Paulo road network"
                    className="deep-dive-screenshot"
                    loading="lazy"
                  />
                </Zoom>
                <Zoom>
                  <img
                    src="/screenshots/inspector-popup.svg"
                    alt="Agent inspector popup showing driver DNA parameters and current trip state"
                    className="deep-dive-screenshot"
                    loading="lazy"
                    style={{ marginTop: '12px' }}
                  />
                </Zoom>
              </div>
            </details>

            {/* ── Deep Dive 2: Medallion Data Pipeline ──────────────── */}
            <details className="deep-dive">
              <summary className="deep-dive-summary">
                <span className="deep-dive-icon" aria-hidden="true">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    width="24"
                    height="24"
                  >
                    <path d="M12 3C7 3 3 5.24 3 8v8c0 2.76 4 5 9 5s9-2.24 9-5V8c0-2.76-4-5-9-5zm0 2c4.42 0 7 1.79 7 3s-2.58 3-7 3-7-1.79-7-3 2.58-3 7-3zm7 11c0 1.21-2.58 3-7 3s-7-1.79-7-3v-2.23C6.61 15.69 9.2 16.5 12 16.5s5.39-.81 7-2.23V14zm0-4c0 1.21-2.58 3-7 3s-7-1.79-7-3v-2.23C6.61 11.69 9.2 12.5 12 12.5s5.39-.81 7-2.23V10z" />
                  </svg>
                </span>
                <div className="deep-dive-header">
                  <span className="deep-dive-title">Medallion Data Pipeline</span>
                  <span className="deep-dive-preview">
                    Bronze-Silver-Gold lakehouse on Delta Lake with dual-engine dbt transformations,
                    anomaly detection, and ~40 SQL quality tests.
                  </span>
                </div>
                <span className="deep-dive-chevron" aria-hidden="true">
                  &#x203A;
                </span>
              </summary>
              <div className="deep-dive-content">
                <h3>Bronze Layer</h3>
                <p>
                  Raw JSON events plus 5 metadata columns (<code>_kafka_partition</code>,{' '}
                  <code>_kafka_offset</code>, <code>_kafka_timestamp</code>,{' '}
                  <code>_ingested_at</code>, <code>_ingestion_date</code>). Written via{' '}
                  <code>delta-rs</code> Python bindings &mdash; no JVM, 256&nbsp;MB vs 4&nbsp;GB
                  memory footprint. Dead Letter Queue routing for malformed messages.
                </p>

                <h3>Silver Layer</h3>
                <p>
                  JSON parsed, deduplicated (ROW_NUMBER by <code>event_id</code>), coordinates
                  validated, timestamps standardized. Anomaly detection flags GPS outliers (outside
                  S&atilde;o Paulo bounds), impossible speeds, and zombie drivers (online but no GPS
                  activity). Incremental materialization with <code>_ingested_at</code> watermark.
                </p>

                <h3>Gold Layer</h3>
                <p>
                  Star schema with surrogate keys. SCD Type&nbsp;2 for <code>dim_drivers</code> and{' '}
                  <code>dim_riders</code> with <code>valid_from</code>/<code>valid_to</code>/
                  <code>current_flag</code>. Pre-computed aggregates:{' '}
                  <code>agg_hourly_zone_demand</code>, <code>agg_daily_driver_performance</code>,{' '}
                  <code>agg_daily_platform_revenue</code>, <code>agg_surge_history</code>.
                </p>

                <h3>Dual-Engine dbt</h3>
                <p>
                  dbt-duckdb for fast local development, dbt-spark for production parity.
                  Cross-database macros (<code>json_field()</code>, <code>to_ts()</code>,{' '}
                  <code>epoch_seconds()</code>) abstract engine differences. ~40 SQL tests including
                  custom generic tests: <code>scd_validity</code>, <code>fee_percentage</code>,{' '}
                  <code>fare_calculation</code>.
                </p>

                <h3>Orchestration</h3>
                <ul>
                  <li>
                    Silver transformation DAG — hourly, ShortCircuitOperator skips when Bronze is
                    empty.
                  </li>
                  <li>
                    Gold transformation DAG — triggered by Silver; dimensions &rarr; facts &rarr;
                    aggregates ordering.
                  </li>
                  <li>DLQ monitoring DAG — every 15&nbsp;min, DuckDB over Delta tables.</li>
                  <li>Delta maintenance DAG — daily vacuum and compaction.</li>
                </ul>

                <Zoom>
                  <img
                    src="/screenshots/airflow-dag.svg"
                    alt="Airflow DAG graph view showing the Silver and Gold transformation pipeline task dependencies"
                    className="deep-dive-screenshot"
                    loading="lazy"
                  />
                </Zoom>
                <Zoom>
                  <img
                    src="/screenshots/grafana-data-engineering.svg"
                    alt="Grafana data engineering dashboard showing Kafka consumer lag, Bronze write latency, and DLQ error rates"
                    className="deep-dive-screenshot"
                    loading="lazy"
                    style={{ marginTop: '12px' }}
                  />
                </Zoom>
              </div>
            </details>

            {/* ── Deep Dive 3: Observability ────────────────────────── */}
            <details className="deep-dive">
              <summary className="deep-dive-summary">
                <span className="deep-dive-icon" aria-hidden="true">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    width="24"
                    height="24"
                  >
                    <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" />
                  </svg>
                </span>
                <div className="deep-dive-header">
                  <span className="deep-dive-title">Observability</span>
                  <span className="deep-dive-preview">
                    OpenTelemetry Collector gateway routing metrics to Prometheus, logs to Loki
                    (with PII masking), and traces to Tempo. 5 Grafana dashboard categories.
                  </span>
                </div>
                <span className="deep-dive-chevron" aria-hidden="true">
                  &#x203A;
                </span>
              </summary>
              <div className="deep-dive-content">
                <h3>Unified Telemetry Gateway</h3>
                <p>
                  OpenTelemetry Collector receives all signals and routes: metrics via{' '}
                  <code>remote_write</code> to Prometheus, logs via Loki push API, traces via OTLP
                  gRPC to Tempo. Single configuration point for the entire telemetry pipeline.
                </p>

                <h3>Prometheus Metrics</h3>
                <ul>
                  <li>7-day retention. Scrapes cAdvisor for container CPU/memory.</li>
                  <li>
                    Custom metrics: <code>simulation_active_drivers</code>,{' '}
                    <code>simulation_trips_completed_total</code>,{' '}
                    <code>stream_processor_redis_publish_latency_seconds</code>, GPS aggregation
                    ratios.
                  </li>
                  <li>Alert rules for resource thresholds and simulation-critical events.</li>
                </ul>

                <h3>Grafana Dashboards (5 categories, 4 datasources)</h3>
                <ul>
                  <li>
                    <strong>Monitoring</strong>: Simulation overview, container metrics
                  </li>
                  <li>
                    <strong>Data Engineering</strong>: Kafka consumer lag, Bronze write latency, DLQ
                    error rates, data quality
                  </li>
                  <li>
                    <strong>Business Intelligence</strong>: Zone demand heatmaps, driver
                    performance, revenue analytics (via Trino)
                  </li>
                  <li>
                    <strong>Operations</strong>: End-to-end pipeline health, Airflow DAG status
                  </li>
                  <li>
                    <strong>Performance</strong>: Infrastructure headroom, PID controller state,
                    auto-throttle adjustments
                  </li>
                </ul>

                <h3>Distributed Tracing &amp; PII Masking</h3>
                <p>
                  All events carry <code>session_id</code>, <code>correlation_id</code>,{' '}
                  <code>causation_id</code>. Trace IDs propagated in Kafka message headers. Tempo
                  traces cross-link to Loki logs. Log filter redacts emails (<code>[EMAIL]</code>)
                  and phone numbers (<code>[PHONE]</code>) before emission.
                </p>

                <h3>Performance Engineering</h3>
                <ul>
                  <li>
                    PID auto-throttle sidecar reads a composite infrastructure headroom index (0-1)
                    from Prometheus recording rules every 5s
                  </li>
                  <li>
                    6 headroom components: Kafka consumer lag, SimPy queue depth, CPU, memory,
                    consumption ratio, real-time ratio
                  </li>
                  <li>
                    Asymmetric PID gains: aggressive slowdown (k_down=1.5), gentle ramp-up
                    (k_up=0.15) &mdash; prevents oscillation
                  </li>
                  <li>
                    Dedicated Grafana dashboard with saturation indicators, USE metrics per
                    container, throughput curves, and controller state
                  </li>
                </ul>

                <Zoom>
                  <img
                    src="/screenshots/grafana-simulation.svg"
                    alt="Grafana simulation overview dashboard showing active driver counts and trip throughput metrics"
                    className="deep-dive-screenshot"
                    loading="lazy"
                  />
                </Zoom>
                <Zoom>
                  <img
                    src="/screenshots/grafana-data-engineering.svg"
                    alt="Grafana data engineering dashboard showing Kafka consumer lag, Bronze write latency, and data quality metrics"
                    className="deep-dive-screenshot"
                    loading="lazy"
                    style={{ marginTop: '12px' }}
                  />
                </Zoom>
              </div>
            </details>

            {/* ── Deep Dive 4: Infrastructure & Quality ─────────────── */}
            <details className="deep-dive">
              <summary className="deep-dive-summary">
                <span className="deep-dive-icon" aria-hidden="true">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    width="24"
                    height="24"
                  >
                    <path d="M19.35 10.04A7.49 7.49 0 0 0 12 4C9.11 4 6.6 5.64 5.35 8.04A5.994 5.994 0 0 0 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM19 18H6c-2.21 0-4-1.79-4-4 0-2.05 1.53-3.76 3.56-3.97l1.07-.11.5-.95A5.469 5.469 0 0 1 12 6c2.62 0 4.88 1.86 5.39 4.43l.3 1.5 1.53.11A2.98 2.98 0 0 1 22 15c0 1.65-1.35 3-3 3z" />
                  </svg>
                </span>
                <div className="deep-dive-header">
                  <span className="deep-dive-title">Infrastructure &amp; Quality</span>
                  <span className="deep-dive-preview">
                    Three-layer Terraform IaC, EKS with ArgoCD GitOps, LocalStack-to-AWS one-env-var
                    migration, and a 4-tier test strategy across 120+ test files.
                  </span>
                </div>
                <span className="deep-dive-chevron" aria-hidden="true">
                  &#x203A;
                </span>
              </summary>
              <div className="deep-dive-content">
                <h3>Three-Layer Terraform</h3>
                <p>
                  Bootstrap (S3 state bucket + DynamoDB lock) &rarr; Foundation (VPC, DNS, CDN, ECR,
                  Secrets, IAM &mdash; ~$7.50/month always-on) &rarr; Platform (EKS, RDS, ALB
                  &mdash; ~$0.65/hour on-demand). Platform reads Foundation outputs via{' '}
                  <code>terraform_remote_state</code>.
                </p>

                <h3>GitOps Deployment</h3>
                <p>
                  ArgoCD watches the <code>deploy</code> branch with <code>selfHeal: true</code>.
                  Kustomize overlays handle local vs. production differences. Same container images
                  in both environments. Pod Identity (not IRSA) for all workload IAM roles.
                </p>

                <h3>LocalStack-to-AWS Migration</h3>
                <p>
                  Complete AWS Secrets Manager compatibility via LocalStack for development. All
                  secret groups (<code>api-key</code>, <code>core</code>, <code>data-pipeline</code>
                  , <code>monitoring</code>) structured identically. <code>AWS_ENDPOINT_URL</code>{' '}
                  is the only configuration change for production.
                </p>

                <h3>4-Tier Test Strategy</h3>
                <ul>
                  <li>
                    <strong>Unit</strong>: pytest + Vitest with markers (
                    <code>@pytest.mark.unit</code>, <code>@pytest.mark.slow</code>,{' '}
                    <code>@pytest.mark.critical</code>)
                  </li>
                  <li>
                    <strong>Integration</strong>: testcontainers with full Docker stack,{' '}
                    <code>@pytest.mark.requires_profiles()</code>
                  </li>
                  <li>
                    <strong>Performance</strong>: 4 scenarios (baseline, stress test, memory leak
                    detection, speed scaling)
                  </li>
                  <li>
                    <strong>Contract</strong>: OpenAPI spec compliance (fails CI on type drift),
                    security header validation
                  </li>
                </ul>

                <h3>Security &amp; CI/CD</h3>
                <ul>
                  <li>
                    Security headers: CSP, HSTS, X-Frame-Options. Rate limiting per API key/IP.
                  </li>
                  <li>
                    WebSocket sliding window (5 connections per 60s). Secrets never in{' '}
                    <code>.env</code> files.
                  </li>
                  <li>
                    GitHub Actions: <code>ci.yml</code> (lint, type-check, unit tests) and{' '}
                    <code>integration-tests.yml</code>.
                  </li>
                  <li>Pre-commit hooks: black, ruff, mypy, eslint, prettier, detect-secrets.</li>
                </ul>
              </div>
            </details>
          </section>

          <section id="explore" className="landing-section landing-services">
            <h2>Explore the Platform</h2>

            <DeployPanel
              isLocal={isLocal}
              apiKey={apiKey}
              onNeedAuth={onNeedAuth}
              onServicesChange={onServicesChange}
            />

            <div className="landing-services-grid">
              <button
                onClick={onLoginClick}
                className={`landing-service-card${!servicesAvailable ? ' landing-service-card--disabled' : ''}`}
                disabled={!servicesAvailable}
              >
                <SiReact
                  width={32}
                  height={32}
                  className="landing-service-icon"
                  style={{ color: `#${SiReactHex}` }}
                  aria-hidden="true"
                />
                <span className="landing-service-name">Control Panel</span>
                <span className="landing-service-desc">
                  Real-time simulation map — watch drivers and riders move across São Paulo
                </span>
              </button>
              {getExternalServices(isLocal).map((s) => {
                const Icon = s.icon;

                if (!servicesAvailable) {
                  return (
                    <span
                      key={s.name}
                      className="landing-service-card landing-service-card--disabled"
                      aria-disabled="true"
                    >
                      <Icon
                        width={32}
                        height={32}
                        className="landing-service-icon"
                        style={{ color: s.iconColor }}
                        aria-hidden="true"
                      />
                      <span className="landing-service-name">{s.name}</span>
                      <span className="landing-service-desc">{s.desc}</span>
                    </span>
                  );
                }

                return (
                  <a
                    key={s.name}
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="landing-service-card"
                  >
                    <Icon
                      width={32}
                      height={32}
                      className="landing-service-icon"
                      style={{ color: s.iconColor }}
                      aria-hidden="true"
                    />
                    <span className="landing-service-name">{s.name}</span>
                    <span className="landing-service-desc">{s.desc}</span>
                  </a>
                );
              })}
            </div>
          </section>

          <footer className="landing-footer">
            <p className="landing-footer-note">
              The platform is deployed on-demand for demonstrations and interviews to minimize cloud
              costs.
            </p>
            <div className="landing-footer-actions">
              <a
                href="https://github.com/andresbrocco/rideshare-simulation-platform"
                target="_blank"
                rel="noopener noreferrer"
                className="landing-github-link"
              >
                View on GitHub &rarr;
              </a>
            </div>
            <p className="landing-footer-author">
              Built by Andre Sbrocco
              {' · '}
              <a
                href={LINKEDIN_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="landing-footer-link"
                aria-label="LinkedIn profile"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width={16}
                  height={16}
                  viewBox="0 0 24 24"
                  fill="#0A66C2"
                  style={{ verticalAlign: 'middle' }}
                  aria-hidden="true"
                >
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
              </a>
              {' · '}
              <a href="mailto:andresbroco@gmail.com" className="landing-footer-link">
                andresbroco@gmail.com
              </a>
            </p>
          </footer>
        </div>
      </div>
    </div>
  );
}
