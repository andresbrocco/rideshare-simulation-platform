# CONTEXT.md — LocalStack

## Purpose

Local AWS service emulation for development and testing. Provides Secrets Manager, SNS, and SQS APIs on a single endpoint so application code can use standard AWS SDKs without connecting to real AWS infrastructure or incurring cloud costs.

## Responsibility Boundaries

- **Owns**: Local AWS API emulation, service lifecycle, endpoint routing
- **Delegates to**: Application services for actual AWS SDK usage, Docker Compose for container orchestration
- **Does not handle**: Production AWS integration, persistent state (ephemeral by design), real IAM authentication

## Key Concepts

**Enabled Services**: Only three AWS services are activated — Secrets Manager (secret storage and retrieval), SNS (pub/sub messaging), and SQS (message queuing). Configured via the `SERVICES` environment variable in Docker Compose.

**Unified Endpoint**: All AWS services are accessible through a single endpoint at `http://localhost:4566`. The standard AWS CLI and SDKs work by setting `--endpoint-url` to this address.

**Ephemeral Data**: `PERSISTENCE=0` means all state (secrets, topics, queues) is lost on container restart. This is intentional for local development — state is recreated by init scripts or application startup logic.

**Dummy Credentials**: Any credentials work (`test`/`test` by convention). LocalStack does not validate IAM authentication.

## Non-Obvious Details

Data is ephemeral by design — all state is lost on container restart. This prevents stale state from accumulating across development sessions but means any required secrets or queues must be recreated after each restart.

The `test-services.sh` validation script requires the AWS CLI to be installed locally on the host machine. It creates test resources (a secret, an SNS topic, an SQS queue) and verifies round-trip functionality.

Port range 4510-4559 is reserved for individual service APIs but the unified endpoint on 4566 is the primary access point for all services.

## Related Modules

- **[infrastructure/docker](../../infrastructure/docker/)** — Deployment orchestration; defines the LocalStack container under the `data-pipeline` profile
