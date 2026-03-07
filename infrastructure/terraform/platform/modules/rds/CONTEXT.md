# CONTEXT.md — RDS

## Purpose

Provisions a single PostgreSQL RDS instance shared by two platform services: Airflow (metadata database) and Hive Metastore. Manages the master password lifecycle, subnet group placement, and writes resolved connection details back to a pre-existing Secrets Manager secret.

## Responsibility Boundaries

- **Owns**: RDS instance provisioning, subnet group, random master password generation, writing credentials/endpoint to Secrets Manager
- **Delegates to**: Foundation module for the security group (`rds_sg_id`) and the Secrets Manager secret resource (`rds_secret_id`)
- **Does not handle**: Application-level user creation, database grants, or Hive Metastore database creation (must be done manually after apply)

## Key Concepts

- **Dual-database design**: Only the `airflow` database is created automatically (via `db_name` on the `aws_db_instance` resource). The `metastore` database must be created manually after the RDS instance is running — a `null_resource` prints the required `psql` command as a reminder but does not execute it.
- **Credential injection**: The module populates an existing Secrets Manager secret (created by the foundation module) with `MASTER_USERNAME`, `MASTER_PASSWORD`, `ENDPOINT`, and `PORT` after the instance is ready. Downstream services read from that secret rather than from Terraform outputs.

## Non-Obvious Details

- The `random_password` resource restricts special characters to `!#&*-_=+`. This avoids characters like `%`, `>`, and `[` that break URI-embedded passwords and `psql` connection strings. Changing this constraint on an existing instance requires a manual password rotation.
- `outputs.tf` strips the port suffix from `aws_db_instance.main.endpoint` using `split(":", ...)[0]` because the AWS provider appends `:5432` to the endpoint string, which would break hostname-only consumers.
- `skip_final_snapshot = true` means destroying this module via `terraform destroy` immediately drops all data with no recovery snapshot.
- The `metastore` DB creation step is intentionally left as a manual operation documented in a `null_resource` echo. Any Airflow DAGs or Hive services that depend on it will fail until this step is completed post-apply.
