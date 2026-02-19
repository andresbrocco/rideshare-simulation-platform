import { useEffect } from 'react';
import { TripLifecycleAnimation } from './TripLifecycleAnimation';

export function OfflineMode() {
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    const prevHeight = document.body.style.height;
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';
    return () => {
      document.body.style.overflow = prevOverflow;
      document.body.style.height = prevHeight;
    };
  }, []);

  return (
    <div className="offline-container">
      <div className="offline-inner">
        <div className="offline-hero">
          <div className="offline-hero-glow" />
          <div className="offline-status-badge">
            <span className="offline-status-dot" />
            Demo Offline
          </div>
          <h1>Rideshare Simulation Platform</h1>
          <p className="offline-subtitle">
            Real-time Event-Driven Data Engineering &mdash; Portfolio Project
          </p>
        </div>

        <TripLifecycleAnimation />

        <div className="offline-body">
          <div className="offline-overview">
            <p>
              An event-driven data engineering platform combining a discrete-event simulation engine
              with a medallion lakehouse pipeline. The system simulates a rideshare platform in
              S&atilde;o Paulo, Brazil, generating synthetic events that flow through Bronze &rarr;
              Silver &rarr; Gold data architecture for analytics.
            </p>
          </div>

          <div className="offline-two-col">
            <section className="offline-section">
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

            <section className="offline-section">
              <h2>Technology Stack</h2>
              <div className="offline-tech-grid">
                <span className="offline-tech-badge">Python 3.13</span>
                <span className="offline-tech-badge">TypeScript</span>
                <span className="offline-tech-badge">Apache Kafka</span>
                <span className="offline-tech-badge">Delta Lake</span>
                <span className="offline-tech-badge">Apache Trino</span>
                <span className="offline-tech-badge">dbt</span>
                <span className="offline-tech-badge">Great Expectations</span>
                <span className="offline-tech-badge">SimPy</span>
                <span className="offline-tech-badge">Kubernetes</span>
                <span className="offline-tech-badge">ArgoCD</span>
                <span className="offline-tech-badge">Grafana</span>
                <span className="offline-tech-badge">Prometheus</span>
              </div>
            </section>
          </div>

          <section className="offline-section offline-pipeline">
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

          <section className="offline-section offline-cta">
            <p>
              The platform is deployed on-demand for demonstrations and interviews to minimize cloud
              costs.
            </p>
            <a
              href="https://github.com/andresbrocco/rideshare-simulation-platform"
              target="_blank"
              rel="noopener noreferrer"
              className="offline-github-link"
            >
              View on GitHub &rarr;
            </a>
          </section>
        </div>
      </div>
    </div>
  );
}
