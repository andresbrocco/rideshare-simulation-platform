# API Contract Testing

This document describes the automated API contract testing system that prevents frontend-backend API drift.

## Overview

FastAPI automatically generates OpenAPI specs from Python type hints. We export this spec, generate TypeScript types from it, and validate the contract in CI.

## Workflow

```
┌─────────────────────────┐
│ Backend (FastAPI)       │
│ - Python type hints     │──┐
│ - Pydantic models       │  │
└─────────────────────────┘  │
                             │ app.openapi()
                             ▼
                    ┌─────────────────────┐
                    │ OpenAPI Spec (JSON) │
                    │ schemas/api/        │
                    │   openapi.json      │
                    └─────────────────────┘
                             │
                             │ openapi-typescript
                             ▼
┌─────────────────────────────────┐
│ Frontend TypeScript Types       │
│ services/control-panel/src/types/    │
│   api.generated.ts              │
└─────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `services/simulation/scripts/export-openapi.py` | Exports OpenAPI spec from FastAPI app |
| `schemas/api/openapi.json` | Committed OpenAPI spec (source of truth) |
| `services/control-panel/src/types/api.generated.ts` | Generated TypeScript types |
| `services/simulation/tests/test_api_contract.py` | Contract validation tests |
| `.github/workflows/ci.yml` | CI workflow (api-contract-validation job) |

## Manual Usage

### Export OpenAPI Spec

```bash
./venv/bin/python3 services/simulation/scripts/export-openapi.py
```

### Generate TypeScript Types

```bash
cd services/control-panel
npm run generate-types
```

### Run Contract Tests

```bash
cd services/simulation
../../venv/bin/python3 -m pytest tests/test_api_contract.py -v
```

## CI Workflow

The CI workflow runs on PR/push when API-related files change:

1. Export OpenAPI spec from FastAPI app
2. Validate spec against OpenAPI 3.x schema
3. Generate TypeScript types
4. Check generated types match committed version

## Test Coverage

| Test | What It Validates |
|------|-------------------|
| `test_openapi_spec_is_valid` | OpenAPI spec is valid JSON Schema |
| `test_openapi_spec_export` | `/openapi.json` endpoint works |
| `test_simulation_status_matches_schema` | `/simulation/status` response structure |
| `test_health_response_matches_schema` | `/health/detailed` response structure |
| `test_typescript_types_generated` | `npm run generate-types` succeeds |
| `test_typescript_types_match_openapi` | Generated types match committed version |

## Adding New Endpoints

When adding a new API endpoint:

1. Add Pydantic models with type hints
2. Define endpoint with `response_model=YourModel`
3. Export OpenAPI spec: `./venv/bin/python3 services/simulation/scripts/export-openapi.py`
4. Generate TypeScript types: `cd services/control-panel && npm run generate-types`
5. Commit both `openapi.json` and `api.generated.ts`
6. Run tests: `cd services/simulation && ../../venv/bin/python3 -m pytest tests/test_api_contract.py -v`

## Tools

| Tool | Version | Purpose |
|------|---------|---------|
| openapi-spec-validator | 0.7.2 | Validate OpenAPI JSON Schema |
| openapi-typescript | 7.13.0 | Generate TypeScript from OpenAPI |
| httpx | 0.28.1 | Test HTTP endpoints |

## Notes

- The OpenAPI spec is committed to version control
- Generated TypeScript types are also committed
- CI fails if types are out of sync with spec
- This catches breaking changes before they reach production
