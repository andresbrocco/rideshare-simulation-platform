# CONTEXT.md — Secrets Manager

## Purpose

Generates all production credentials for the rideshare platform and stores them in AWS Secrets Manager. Passwords are randomly generated at `terraform apply` time and never exist outside of Terraform state and Secrets Manager. Services retrieve credentials at runtime by fetching the appropriate secret.

## Responsibility Boundaries

- **Owns**: Random credential generation, secret creation, secret versioning, and ARN/name outputs consumed by IAM and Kubernetes modules
- **Delegates to**: The platform module to backfill the RDS endpoint into the `rds` secret after the database is created
- **Does not handle**: IAM policies granting workloads access to these secrets (managed by the `iam` module), or the mechanics of how pods fetch secrets at runtime

## Key Concepts

**Secret grouping**: Credentials are merged into logical functional groups rather than one secret per service. The three primary groups are:
- `{project}/api-key` — simulation service API key
- `{project}/core` — Kafka, Redis, Schema Registry credentials
- `{project}/data-pipeline` — MinIO, PostgreSQL (Airflow + Metastore), and all Airflow internal secrets (Fernet key, JWT secret, API secret, admin password)
- `{project}/monitoring` — Grafana admin credentials
- `{project}/rds` — RDS master credentials and endpoint

This grouping limits the number of Secrets Manager API calls a pod must make at startup, since each secret fetch has a cost and latency.

**Airflow Fernet key**: Generated via `random_bytes` (not `random_password`) because Airflow requires a 32-byte URL-safe base64 string. The `.base64` attribute of `random_bytes` provides this format directly. Using `random_password` would produce a string that fails Airflow's Fernet key validation.

## Non-Obvious Details

- **GitHub PAT uses `lifecycle { ignore_changes }`**: The secret is seeded with a placeholder value (`ghp_placeholder_set_real_token_in_production`) on first apply. The `ignore_changes` lifecycle rule prevents Terraform from overwriting the real token if it has been updated out-of-band via the AWS Console or CLI. This is intentional — the real token must be set manually after initial provisioning.
- **RDS secret has an empty `ENDPOINT` field**: The `rds` secret is created with `ENDPOINT = ""` because the RDS instance does not exist yet at foundation apply time. The platform module updates this field after the RDS instance is created, using the `rds_secret_id` output from this module.
- **API key length differs from others**: The simulation API key is hardcoded to 32 characters while all other passwords use `var.password_length` (default 16). This reflects the different security profile of an externally-presented API key versus internal service-to-service credentials.
- **Secret names are prefixed with `var.project_name`**: All secrets follow the pattern `{project_name}/{secret-type}` (e.g., `rideshare/core`). IAM policies that grant secret access reference these names, so the `project_name` variable must be consistent across foundation and IAM modules.
