export function OfflineMode() {
  return (
    <div className="offline-container">
      <div className="offline-content">
        <h1>Rideshare Simulation Platform</h1>
        <p className="subtitle">Real-time Event-Driven Data Engineering Portfolio Project</p>

        <section className="project-overview">
          <h2>About This Project</h2>
          <p>
            An event-driven data engineering platform combining a discrete-event simulation engine
            with a medallion lakehouse pipeline. The system simulates a rideshare platform in
            S&atilde;o Paulo, Brazil, generating synthetic events that flow through Bronze &rarr;
            Silver &rarr; Gold data architecture for analytics.
          </p>
        </section>

        <section className="architecture">
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

        <section className="screenshots">
          <h2>Live Simulation Preview</h2>
          <div className="media-placeholder">
            Screenshots and screen recordings will be added here
          </div>
        </section>

        <section className="offline-notice">
          <div className="alert">
            <h3>Demo Currently Offline</h3>
            <p>
              The live demo is currently offline to minimize cloud costs. The platform is deployed
              on-demand for demonstrations and interviews.
            </p>
            <p>
              <strong>Contact me to schedule a live demo:</strong>
            </p>
            <a
              href="https://github.com/andresbrocco/rideshare-simulation-platform"
              target="_blank"
              rel="noopener noreferrer"
              className="github-link"
            >
              View on GitHub &rarr;
            </a>
          </div>
        </section>

        <section className="tech-stack">
          <h2>Technology Stack</h2>
          <div className="tech-grid">
            <div>Python 3.13 (Simulation, Pipelines)</div>
            <div>TypeScript (Frontend)</div>
            <div>Kafka + Schema Registry</div>
            <div>Delta Lake + Trino</div>
            <div>DBT + Great Expectations</div>
            <div>Kubernetes + ArgoCD</div>
          </div>
        </section>
      </div>
    </div>
  );
}
