# CONTEXT.md — Docs

## Purpose

Cross-cutting documentation for the rideshare simulation platform that does not belong to any single service. Contains developer-facing guides for operational tasks that span multiple infrastructure layers.

## Responsibility Boundaries

- **Owns**: Platform-level operational guides (deployment, data migration)
- **Delegates to**: Individual service directories for service-specific docs; `infrastructure/` for Terraform/Kubernetes configuration files
- **Does not handle**: API references, architecture diagrams, code patterns, or testing guides (those are generated separately or live closer to their subject)

## Non-Obvious Details

The directory previously held several architectural reference documents (ARCHITECTURE.md, DEPENDENCIES.md, PATTERNS.md, SECURITY.md, TESTING.md, INFRASTRUCTURE.md) that are referenced by CLAUDE.md and CONTEXT.md files throughout the codebase. Those files are currently absent (deleted from working tree). If cross-cutting architectural documentation is needed, those filenames are the expected locations based on existing references in `CLAUDE.md`.

## Related Modules

- [docs/other](other/CONTEXT.md) — Reverse dependency — Provides API_CONTRACT.md, DOCKER_PROFILES.md, kafka_partitioning.md (+3 more)
