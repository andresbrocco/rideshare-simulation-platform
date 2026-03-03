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
} from '@icons-pack/react-simple-icons';
import DeltaLakeIcon from '../../public/icons/tech/delta-lake.svg?react';
import DbtIcon from '../../public/icons/tech/dbt.svg?react';
import GreatExpectationsIcon from '../../public/icons/tech/great-expectations.svg?react';
import SimpyIcon from '../../public/icons/tech/simpy.svg?react';
import LokiIcon from '../../public/icons/tech/loki.svg?react';
import TempoIcon from '../../public/icons/tech/tempo.svg?react';
import DeckGlIcon from '../../public/icons/tech/deck-gl.svg?react';
import OsrmIcon from '../../public/icons/tech/osrm.svg?react';
import { useActiveSection } from '../hooks/useActiveSection';
import { useCountUp } from '../hooks/useCountUp';
import { useInView } from '../hooks/useInView';
import { ArchitectureDiagram } from './ArchitectureDiagram';
import { TripLifecycleAnimation } from './TripLifecycleAnimation';

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
        tooltip: 'Multi-datasource dashboards across 4 categories',
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
    ],
  },
];

const INFRA_ITEMS = [
  'Docker',
  'Kubernetes',
  'Terraform',
  'ArgoCD',
  'GitHub Actions',
  'AWS EKS',
  'CloudFront',
  'LocalStack',
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
      <p className="tech-infra-footnote">
        Also:{' '}
        {INFRA_ITEMS.map((name, i) => (
          <span key={name} className="tech-infra-item">
            {name}
            {i < INFRA_ITEMS.length - 1 ? ', ' : ''}
          </span>
        ))}
      </p>
    </section>
  );
}

interface ExternalService {
  name: string;
  url: string;
  desc: string;
}

function getExternalServices(isLocal: boolean): ExternalService[] {
  return [
    {
      name: 'Grafana',
      url: isLocal
        ? 'http://localhost:3001'
        : 'https://grafana.ridesharing.portfolio.andresbrocco.com',
      desc: 'Observability dashboards',
    },
    {
      name: 'Airflow',
      url: isLocal
        ? 'http://localhost:8082'
        : 'https://airflow.ridesharing.portfolio.andresbrocco.com',
      desc: 'Pipeline orchestration',
    },
    {
      name: 'Trino',
      url: isLocal
        ? 'http://localhost:8084'
        : 'https://trino.ridesharing.portfolio.andresbrocco.com',
      desc: 'Interactive SQL engine',
    },
    {
      name: 'Prometheus',
      url: isLocal
        ? 'http://localhost:9090'
        : 'https://prometheus.ridesharing.portfolio.andresbrocco.com',
      desc: 'Metrics & PromQL',
    },
    {
      name: 'Simulation API',
      url: isLocal
        ? 'http://localhost:8000/docs'
        : 'https://api.ridesharing.portfolio.andresbrocco.com/docs',
      desc: 'REST API docs (Swagger)',
    },
  ];
}

const STATS = [
  { target: 30, suffix: '+', label: 'Services' },
  { target: 8, suffix: '', label: 'Kafka Topics' },
  { target: 120, suffix: '+', label: 'Tests' },
  { target: 4, suffix: '', label: 'Grafana Dashboard\nCategories' },
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
}

export function LandingPage({ onLoginClick, isLocal }: LandingPageProps) {
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

          <section className="landing-section landing-services">
            <h2>Explore the Platform</h2>
            <div className="landing-services-grid">
              <button onClick={onLoginClick} className="landing-service-card">
                <span className="landing-service-name">Control Panel</span>
                <span className="landing-service-desc">Real-time simulation map</span>
              </button>
              {getExternalServices(isLocal).map((s) => (
                <a
                  key={s.name}
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="landing-service-card"
                >
                  <span className="landing-service-name">{s.name}</span>
                  <span className="landing-service-desc">{s.desc}</span>
                </a>
              ))}
            </div>
          </section>

          <section className="landing-section landing-cta">
            <p>
              The platform is deployed on-demand for demonstrations and interviews to minimize cloud
              costs.
            </p>
            <a
              href="https://github.com/andresbrocco/rideshare-simulation-platform"
              target="_blank"
              rel="noopener noreferrer"
              className="landing-github-link"
            >
              View on GitHub &rarr;
            </a>
          </section>
        </div>
      </div>
    </div>
  );
}
