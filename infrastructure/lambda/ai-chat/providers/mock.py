"""Mock LLM provider for local development and CI testing.

Returns pre-written responses for the four starter questions shown in the
frontend chat UI.  All other questions receive a generic fallback.

This module uses only Python stdlib — no external packages required.
It is safe to deploy as a Lambda layer with requirements-mock.txt (boto3 only).

Usage::

    from providers.mock import Provider

    p = Provider()
    response = p.complete(
        system_prompt="...",
        messages=[{"role": "user", "content": "What is the architecture?"}],
    )
    print(response.text)   # returns a detailed mock answer
    print(response.cached) # True for starter questions
"""

from llm_adapter import LLMProvider, LLMResponse

# ---------------------------------------------------------------------------
# Pre-written starter responses
# ---------------------------------------------------------------------------

_STARTER_RESPONSES: dict[str, str] = {
    "What is the architecture of this platform?": (
        "This platform is a five-layer event-driven data engineering system built to simulate "
        "a rideshare service in São Paulo, Brazil.\n\n"
        "1. **Simulation layer** — A SimPy discrete-event simulation drives synthetic "
        "driver and rider agents with DNA-based behavioural profiles. Geospatial matching "
        "uses Uber's H3 hexagonal grid at resolution 7, giving O(1) driver lookups within "
        "any cell.\n\n"
        "2. **Streaming layer** — Events are published to Apache Kafka. A stream processor "
        "fans out real-time state to Redis, which feeds WebSocket connections to the "
        "frontend map.\n\n"
        "3. **Medallion lakehouse** — Raw events land in a Bronze Delta Lake table, are "
        "cleaned into Silver, and aggregated into a Gold star schema. All tables live on "
        "MinIO (local) or S3 (production).\n\n"
        "4. **Orchestration & quality** — Apache Airflow schedules daily DBT "
        "transformations. Great Expectations validates data quality at each layer.\n\n"
        "5. **Observability** — Prometheus scrapes metrics from every service. Grafana "
        "dashboards visualise simulation throughput, pipeline health, and data quality. "
        "Loki aggregates structured JSON logs."
    ),
    "How does the simulation engine work?": (
        "The simulation engine is built on **SimPy**, a Python discrete-event simulation "
        "framework.\n\n"
        "Each driver and rider is modelled as a SimPy generator process. The simulation "
        "clock advances in virtual time; no wall-clock sleeping is involved.\n\n"
        "**Agent DNA** — Every agent has an immutable `DNA` Pydantic model (frozen=True) "
        "that encodes personality traits: patience, tip propensity, cancellation tendency, "
        "and preferred operating zones. DNA is generated procedurally at agent spawn time.\n\n"
        "**Trip lifecycle** — A rider sends a ride request; the engine finds the nearest "
        "available driver within the same or adjacent H3 cell; the driver transitions "
        "through states (`available → en_route_pickup → on_trip → available`). Each state "
        "transition emits a Kafka event.\n\n"
        "**Control plane** — A FastAPI REST API (separate thread) lets the frontend pause, "
        "resume, and tune the simulation. A `ThreadCoordinator` command queue bridges the "
        "API thread and the SimPy event loop safely.\n\n"
        "**Scale** — The default configuration spawns 50 drivers and 200 riders. At 10× "
        "speed-up the engine generates roughly 2,000–4,000 Kafka events per simulated hour."
    ),
    "What technologies are used?": (
        "Here is a breakdown of the key technologies in the stack:\n\n"
        "| Layer | Technology |\n"
        "|-------|------------|\n"
        "| Simulation | Python 3.13, SimPy, H3, Haversine, OSRM |\n"
        "| Streaming | Apache Kafka, Schema Registry, Confluent Python client |\n"
        "| Storage | Delta Lake (delta-rs), MinIO / S3, Redis |\n"
        "| Transformation | DBT (dbt-core + dbt-trino), Apache Trino |\n"
        "| Orchestration | Apache Airflow 2.x |\n"
        "| Data quality | Great Expectations |\n"
        "| Backend APIs | FastAPI (simulation), AWS Lambda (ai-chat) |\n"
        "| Frontend | React 18, TypeScript, deck.gl (map), Zustand |\n"
        "| Observability | Prometheus, Grafana, Loki, OpenTelemetry |\n"
        "| Infrastructure | Docker Compose (local), Terraform + EKS (production) |\n"
        "| LLM | Anthropic Claude (production), Mock (CI / dev) |\n\n"
        "Everything runs locally via Docker Compose with a single `docker compose up` command. "
        "Production runs on AWS EKS with ArgoCD GitOps continuous delivery."
    ),
    "How does data flow through the system?": (
        "Data follows two parallel paths from the simulation to the consumer:\n\n"
        "**Real-time path** (for the live map):\n"
        "Simulation → Kafka topic → Stream Processor → Redis pub/sub → "
        "WebSocket server → React frontend\n\n"
        "Latency is typically under 100 ms end-to-end.\n\n"
        "**Analytics path** (for dashboards and SQL queries):\n"
        "Simulation → Kafka → Bronze ingestion job → Delta Lake (raw) → "
        "Airflow-scheduled DBT → Silver (cleaned) → Gold (star schema) → "
        "Trino SQL engine → Grafana / Superset\n\n"
        "**Event envelope** — Every Kafka message contains correlation fields "
        "(`session_id`, `correlation_id`, `causation_id`) so events can be joined "
        "across services in Trino without a separate event-ID lookup.\n\n"
        "**Deduplication** — The Silver layer deduplicates by event UUID using a "
        "MERGE INTO operation on the Delta table, making the pipeline idempotent.\n\n"
        "**Retention** — Bronze data is kept for 90 days. Gold aggregates are retained "
        "indefinitely for portfolio analysis."
    ),
}

_FALLBACK_RESPONSE = (
    "That's a great question! While I'm running in mock mode and can't answer arbitrary "
    "questions with full detail, I can tell you that this platform covers simulation, "
    "streaming, lakehouse architecture, orchestration, and observability.\n\n"
    "Try one of the starter questions to get a detailed answer about the architecture, "
    "simulation engine, technology stack, or data flow."
)

# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class Provider(LLMProvider):
    """Mock LLM provider with zero external dependencies.

    Returns pre-written answers for the four starter questions.  All other
    inputs receive a generic fallback response.  Token counts are always 0.

    Args:
        model: Ignored. Accepted for interface compatibility with other providers.
    """

    def __init__(self, model: str = "") -> None:
        self._model = model

    def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        """Return a mock response based on the last user message.

        Scans ``messages`` from the end to find the most recent ``"user"`` role
        message.  If that message matches one of the four starter questions
        exactly, returns the corresponding pre-written answer with
        ``cached=True``.  Otherwise returns the generic fallback with
        ``cached=False``.

        Args:
            system_prompt: Ignored by the mock provider.
            messages: Conversation history.  Each entry must have
                ``"role"`` and ``"content"`` keys.

        Returns:
            LLMResponse with text, cached flag, and zero token counts.
        """
        last_user_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_content = msg.get("content", "")
                break

        if last_user_content in _STARTER_RESPONSES:
            return LLMResponse(
                text=_STARTER_RESPONSES[last_user_content],
                input_tokens=0,
                output_tokens=0,
                cached=True,
            )

        return LLMResponse(
            text=_FALLBACK_RESPONSE,
            input_tokens=0,
            output_tokens=0,
            cached=False,
        )
