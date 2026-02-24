#!/usr/bin/env bash
set -e

# Generate TypeScript types from OpenAPI spec
npx openapi-typescript ../../schemas/api/openapi.json -o src/types/api.generated.ts
npx prettier --write src/types/api.generated.ts
