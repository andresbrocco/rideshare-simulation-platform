"""Mock LLM provider for local development and CI testing.

Returns pre-written responses for the six starter questions shown in the
frontend chat UI.  All other questions receive a generic fallback.

This module uses only Python stdlib — no external packages required.
It is safe to deploy as a Lambda layer with requirements-mock.txt (boto3 only).

Usage::

    from providers.mock import Provider

    p = Provider()
    response = p.complete(
        system_prompt="...",
        messages=[{"role": "user", "content": "How does deduplication work..."}],
    )
    print(response.text)   # returns a detailed mock answer
    print(response.cached) # True for starter questions
"""

from llm_adapter import LLMProvider, LLMResponse

# ---------------------------------------------------------------------------
# Pre-written starter responses
# ---------------------------------------------------------------------------

_STARTER_RESPONSES: dict[str, str] = {
    "How does deduplication work across the three layers (Stream Processor, Silver, Gold)?": (
        "Each layer uses a different strategy matched to its processing model:\n\n"
        "- **Stream Processor** — Redis `SET NX` with 1-hour TTL on `event_id`. "
        "First-seen events are processed; Kafka at-least-once redeliveries are "
        "silently dropped.\n\n"
        "- **Silver** — DBT `unique_key: 'event_id'` generates `MERGE` (Spark) or "
        "`INSERT OR REPLACE` (DuckDB), handling redeliveries and Bronze reprocessing.\n\n"
        "- **Gold** — Full-refresh materialization rebuilds daily from Silver, so "
        "duplicate accumulation is impossible by construction.\n\n"
        "**Bronze** does not deduplicate — it stores raw Kafka payloads verbatim "
        "to preserve full fidelity for reprocessing."
    ),
    "How do the same DBT models run against both DuckDB locally and Glue in production?": (
        "The key mechanism is `adapter.dispatch()` — model SQL calls generic macros "
        "like `extract_json_field()`, and the active adapter selects the right "
        "implementation.\n\n"
        "- **DuckDB macros** emit `json_extract_string()` and `delta_scan()` to read "
        "Delta tables directly (no JVM required).\n"
        "- **Glue macros** emit `get_json_object()` and read via Spark Delta connector "
        "with Hive Metastore.\n\n"
        "Incremental upserts also differ: DuckDB uses `INSERT OR REPLACE`, Glue uses "
        "`MERGE INTO` — same semantics, each database's native syntax.\n\n"
        "Profile configuration (`profiles.yml`) switches the active adapter. The model "
        "SQL stays clean of dialect branches."
    ),
    "What's the difference between the DBT data quality tests and the Great Expectations suites?": (
        "They validate different concerns at different pipeline stages:\n\n"
        "**DBT tests** run on the **Gold layer** (daily) and check business logic: "
        "SCD Type 2 correctness (no overlapping date ranges), fare calculation accuracy "
        "(`base_fare × distance × surge = total_fare`), and referential integrity "
        "(`fact_trips.driver_sk` → `dim_drivers`). Hard failures block downstream.\n\n"
        "**Great Expectations** runs on the **Silver layer** (hourly) and checks data "
        "quality: GPS coordinate bounds (`mostly=0.99` for noise tolerance), enum "
        "validation against state machine values, and event ID uniqueness. Soft failures "
        "with statistical tolerance.\n\n"
        "Pipeline order: Silver DBT → GX Validation → Gold DBT → DBT Tests."
    ),
    "What happens to analytics if a Kafka consumer group falls behind?": (
        "The **Performance Controller** (PID-based) monitors Kafka consumer lag from "
        "Prometheus and throttles simulation speed to prevent lag from accumulating.\n\n"
        "If Bronze Ingestion does fall behind:\n"
        "- 7-day Kafka retention provides a recovery window\n"
        "- Existing Bronze/Silver/Gold data remains queryable — only freshness degrades\n"
        "- On recovery, Bronze resumes from its last committed offset; Delta Lake's "
        "append-only design prevents corruption during catch-up\n"
        "- Great Expectations validates post-recovery batches\n\n"
        "Stream Processor lag only affects real-time map positions, not analytics."
    ),
    "How does the Bronze DLQ pipeline detect and route malformed events?": (
        "Three validation layers with different routing:\n\n"
        "1. **Schema Registry** (at producer) — events failing JSON Schema validation "
        "are logged as warnings and never published to Kafka.\n\n"
        "2. **Consumer deserialization** (at Bronze Ingestion) — messages failing UTF-8 "
        "decode or JSON parse are routed to per-topic DLQ Delta tables "
        "(e.g. `bronze_trips_dlq`) with error type, message, and Kafka provenance.\n\n"
        "3. **Configurable injection** — the simulation can inject corrupted event copies "
        "at a configurable rate (default 2%) for end-to-end DLQ testing.\n\n"
        "An Airflow DAG checks DLQ tables every 15 minutes and alerts on error rate spikes."
    ),
    "How does visitor provisioning work when the platform isn't even running yet?": (
        "A two-phase design decouples registration from platform availability:\n\n"
        "**Phase 1** (`provision-visitor`) runs with zero platform dependencies — only "
        "Foundation-layer resources (Lambda, DynamoDB, KMS, Secrets Manager, SES). It "
        "stores the visitor record with a KMS-encrypted password, writes a bcrypt hash "
        "to Secrets Manager for Trino, and sends a welcome email.\n\n"
        "**Phase 2** (`reprovision-visitors`) runs after all 15 platform services report "
        "healthy. It scans DynamoDB, decrypts passwords via KMS, and creates accounts in "
        "Grafana, Airflow, MinIO, and the Simulation API.\n\n"
        "On teardown and redeploy, Phase 2 runs again — visitors keep the same credentials."
    ),
}

_FALLBACK_RESPONSE = (
    "That's a great question! While I'm running in mock mode and can't answer arbitrary "
    "questions with full detail, I can tell you that this platform covers simulation, "
    "streaming, lakehouse architecture, orchestration, and observability.\n\n"
    "Try one of the starter questions to get a detailed answer about deduplication, "
    "dual-target DBT, data quality testing, consumer lag handling, DLQ routing, "
    "or visitor provisioning."
)

# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class Provider(LLMProvider):
    """Mock LLM provider with zero external dependencies.

    Returns pre-written answers for the six starter questions.  All other
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
        message.  If that message matches one of the six starter questions
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
