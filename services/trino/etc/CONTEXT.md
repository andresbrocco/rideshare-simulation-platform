# CONTEXT.md — Trino etc

## Purpose

Holds all Trino server-level configuration files: coordinator settings, JVM tuning, file-based access control, and query event logging. This is the complete configuration surface for the Trino coordinator node as it runs in Docker.

## Responsibility Boundaries

- **Owns**: Trino process configuration (coordinator mode, HTTP port, JVM heap, access control rules)
- **Delegates to**: `services/trino/etc/catalog/` for connector-level catalog configuration, container entrypoint scripts for template substitution at runtime
- **Does not handle**: Table registration (done by `scripts/register-trino-tables.py`), schema definitions (owned by dbt and the stream processor), TLS termination

## Key Concepts

**File layout**: Static files (`config.properties`, `node.properties`, `jvm.config`, `event-listener.properties`, `rules.json`) are mounted directly into `/etc/trino/`. The `access-control.properties` references `/tmp/trino-etc/` (not `/etc/trino/`) because the entrypoint copies config to `/tmp/trino-etc` before use (to sidestep bind-mount UID ownership issues on Linux CI runners).

**Single-user security model**: Only the `admin` account is defined. `rules.json` enforces access control via an ordered catalog ACL: `admin` gets `all` on every catalog; all other users are blocked from `system` (preventing schema enumeration), granted `read-only` on `delta`, and `read-only` as a catch-all fallback.

## Non-Obvious Details

- **`rules.json` ordering is load-bearing**: Trino evaluates catalog ACL rules in order and applies the first match. The `system` deny rule for `"user": ".*"` must appear before the read-only catch-all or it would be shadowed. The admin rule must appear first to grant full access before the deny rules are reached.
- **`security.refresh-period=60s`**: The access control rules reload every 60 seconds. A brief window exists after a `rules.json` change before it takes effect.
- **`node-scheduler.include-coordinator=true`**: Trino is running as a single-node coordinator that also schedules work on itself (no separate workers). This is a dev/analytics-only configuration — production clusters separate coordinator and worker roles.
- **`-Xmx1G` JVM heap**: Memory is deliberately constrained for Docker resource limits. Queries against large Delta tables may spill to disk or fail with OOM if this limit is too low; it is a known trade-off for local development.
- **Event listener**: `query-event-listener` logs completed queries to Trino's standard log output, enabling query audit trails via Docker/Loki log collection without requiring an external listener plugin.
