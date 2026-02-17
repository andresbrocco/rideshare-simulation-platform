# CONTEXT.md — OpenLDAP

## Purpose

Provides LDAP authentication for Spark Thrift Server connections. Enables DBT, Airflow, and other SQL clients to authenticate against the dual-engine testing environment using standardized directory credentials.

## Responsibility Boundaries

- **Owns**: LDAP directory schema for the `rideshare.local` domain, service user definitions for SQL clients
- **Delegates to**: LocalStack Secrets Manager for credential storage (admin password), Spark Thrift Server for authorization decisions post-authentication
- **Does not handle**: Authorization or role-based access control (RBAC), TLS/SSL encryption (disabled in development)

## Key Concepts

**Bootstrap LDIF**: The `bootstrap.ldif` file defines the initial directory structure seeded on container startup. Creates an organizational unit (`ou=users`) and a single service user (`cn=admin,ou=users,dc=rideshare,dc=local`) that Spark Thrift Server validates via LDAP bind operations.

**Single-User Model**: Only one LDAP user exists (`admin`). All DBT connections, Airflow DAGs, and manual queries authenticate as this user. No multi-tenancy or user differentiation.

**Spark Thrift LDAP Authentication**: Spark Thrift Server uses `hive.server2.authentication=LDAP` with `hive.server2.authentication.ldap.url=ldap://openldap:389`. Client credentials are validated via LDAP bind; successful bind grants SQL access.

## Non-Obvious Details

**Optional Component**: OpenLDAP only runs with the `spark-testing` Docker Compose profile. The primary development workflow uses DuckDB (no authentication), and Trino uses Basic Auth (configured separately). LDAP exists solely for validating DBT model compatibility with Hive/Spark before cloud deployment.

**No TLS**: `LDAP_TLS=false` disables encryption. Acceptable for local development but would require certificates and `ldaps://` for production use.

**Health Check Credentials**: The Docker healthcheck sources `LDAP_ADMIN_PASSWORD` from `/secrets/data-pipeline.env` (written by the `secrets-init` service) to perform authenticated `ldapsearch` validation.

**Kubernetes ConfigMap**: The Kubernetes deployment embeds `bootstrap.ldif` inline as a ConfigMap rather than mounting from the repository directory.

## Related Modules

- **[infrastructure/scripts](../scripts/CONTEXT.md)** — Provides secrets management that populates LDAP admin credentials used for authentication binding
- **[tools/dbt](../../tools/dbt/CONTEXT.md)** — DBT connects via LDAP when targeting Spark Thrift Server in the spark-testing profile for dual-engine validation
