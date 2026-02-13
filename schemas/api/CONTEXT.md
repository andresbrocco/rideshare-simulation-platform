# CONTEXT.md — API

## Purpose

OpenAPI 3.1 specification for the Rideshare Simulation Control Panel REST API. Serves as the contract between the FastAPI backend and the React frontend, enabling type-safe client code generation and automated drift detection.

## Responsibility Boundaries

- **Owns**: OpenAPI 3.1 JSON schema exported from FastAPI app, schema components for all request/response models (ControlResponse, DriverStateResponse, TripMetrics, etc.), endpoint definitions for simulation control, agent management, puppet control, metrics, and health checks
- **Delegates to**: FastAPI for automatic schema generation from Pydantic models, openapi-typescript for TypeScript type generation, openapi-spec-validator for schema validation in CI
- **Does not handle**: API implementation (services/simulation/src/api/), client usage (services/frontend/), schema evolution policy (breaking changes require coordination)

## Key Concepts

**Contract-First Generation** — The OpenAPI spec is not written manually. It is auto-generated from FastAPI route definitions and Pydantic models using FastAPI's `app.openapi()` method. Python type hints become JSON Schema types. This ensures the spec always reflects actual backend behavior.

**Dual Artifact System** — Two artifacts are generated from this spec and committed to version control:
- TypeScript types (services/frontend/src/types/api.generated.ts): Used by frontend for type-safe API calls
- OpenAPI JSON (schemas/api/openapi.json): Source of truth for contract validation

**Endpoint Categories** — The API surface is organized into functional areas:
- `/simulation/*`: Lifecycle control (start, pause, resume, stop, reset, speed adjustment)
- `/agents/drivers/{id}`, `/agents/riders/{id}`: Query agent state and DNA
- `/agents/puppet/*`: Manual control endpoints for automated testing (go online, accept offer, drive to pickup, rate trip)
- `/metrics/*`: Aggregated metrics (overview, zones, trips, drivers, riders, performance, infrastructure)
- `/health`, `/auth/validate`: Operational endpoints

**API Authentication** — All endpoints except `/health` require `X-API-Key` header. WebSocket connections use `Sec-WebSocket-Protocol: apikey.<key>` subprotocol for authentication.

## Non-Obvious Details

The spec contains over 70 schema components but only a single file. Large schema definitions (ActiveTripInfo, DriverStateResponse, RiderStatisticsResponse) include complex nested structures that must remain synchronized with backend Pydantic models.

Changes to backend models automatically update the spec when re-exported, but the developer must remember to run the export script and commit the result. CI validates that committed spec matches generated spec to prevent drift.

Puppet endpoints (e.g., `/agents/puppet/drivers/{id}/drive-to-pickup`) return immediately but trigger asynchronous background actions. Clients must use WebSocket or polling to observe state changes.

## Related Modules

- **[services/simulation/src/api/routes](../../services/simulation/src/api/routes/CONTEXT.md)** — FastAPI route implementations that generate this OpenAPI spec; changes to routes automatically update the schema
- **[services/frontend/src/components](../../services/frontend/src/components/CONTEXT.md)** — Frontend components consume TypeScript types generated from this spec for type-safe API interaction
- **[schemas](../CONTEXT.md)** — Parent schema directory; API schemas define REST contract while Kafka schemas define event contracts
