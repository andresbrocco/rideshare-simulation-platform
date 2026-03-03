import { TripLifecycleAnimation } from './TripLifecycleAnimation';

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

interface LandingPageProps {
  onLoginClick: () => void;
  isLocal: boolean;
}

export function LandingPage({ onLoginClick, isLocal }: LandingPageProps) {
  return (
    <div className="landing-container">
      <div className="landing-inner">
        <div className="landing-hero">
          <div className="landing-hero-glow" />
          <h1>Rideshare Simulation Platform</h1>
          <p className="landing-subtitle">
            Real-time Event-Driven Data Engineering &mdash; Portfolio Project
          </p>
        </div>

        <TripLifecycleAnimation />

        <div className="landing-body">
          <div className="landing-overview">
            <p>
              An event-driven data engineering platform combining a discrete-event simulation engine
              with a medallion lakehouse pipeline. The system simulates a rideshare platform in
              S&atilde;o Paulo, Brazil, generating synthetic events that flow through Bronze &rarr;
              Silver &rarr; Gold data architecture for analytics.
            </p>
          </div>

          <div className="landing-two-col">
            <section className="landing-section">
              <h2>Architecture Highlights</h2>
              <ul>
                <li>SimPy discrete-event simulation with DNA-based agent behavior</li>
                <li>Kafka event streaming with Schema Registry validation</li>
                <li>Medallion lakehouse (Bronze/Silver/Gold) on Delta Lake</li>
                <li>Airflow-orchestrated DBT transformations</li>
                <li>React + deck.gl real-time visualization</li>
                <li>Prometheus + Grafana observability</li>
              </ul>
            </section>

            <section className="landing-section">
              <h2>Technology Stack</h2>
              <div className="landing-tech-grid">
                <span className="landing-tech-badge">Python 3.13</span>
                <span className="landing-tech-badge">TypeScript</span>
                <span className="landing-tech-badge">Apache Kafka</span>
                <span className="landing-tech-badge">Delta Lake</span>
                <span className="landing-tech-badge">Apache Trino</span>
                <span className="landing-tech-badge">dbt</span>
                <span className="landing-tech-badge">Great Expectations</span>
                <span className="landing-tech-badge">SimPy</span>
                <span className="landing-tech-badge">Kubernetes</span>
                <span className="landing-tech-badge">ArgoCD</span>
                <span className="landing-tech-badge">Grafana</span>
                <span className="landing-tech-badge">Prometheus</span>
              </div>
            </section>
          </div>

          <section className="landing-section landing-pipeline">
            <h2>Data Pipeline</h2>
            <div className="pipeline-flow">
              <div className="pipeline-stage">
                <span className="pipeline-stage-label">Simulation</span>
                <span className="pipeline-stage-desc">SimPy + Kafka</span>
              </div>
              <span className="pipeline-arrow">&rarr;</span>
              <div className="pipeline-stage pipeline-bronze">
                <span className="pipeline-stage-label">Bronze</span>
                <span className="pipeline-stage-desc">Raw Events</span>
              </div>
              <span className="pipeline-arrow">&rarr;</span>
              <div className="pipeline-stage pipeline-silver">
                <span className="pipeline-stage-label">Silver</span>
                <span className="pipeline-stage-desc">Validated</span>
              </div>
              <span className="pipeline-arrow">&rarr;</span>
              <div className="pipeline-stage pipeline-gold">
                <span className="pipeline-stage-label">Gold</span>
                <span className="pipeline-stage-desc">Star Schema</span>
              </div>
              <span className="pipeline-arrow">&rarr;</span>
              <div className="pipeline-stage pipeline-analytics">
                <span className="pipeline-stage-label">Analytics</span>
                <span className="pipeline-stage-desc">Trino + Grafana</span>
              </div>
            </div>
          </section>

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
