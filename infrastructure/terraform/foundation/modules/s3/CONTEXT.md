# CONTEXT.md — S3 (Foundation Module)

## Purpose

Provisions and configures all S3 buckets required by the platform. Acts as the single point of S3 resource definition for the foundation layer, providing bucket names and ARNs to consuming modules (IAM, CloudFront, etc.).

## Responsibility Boundaries

- **Owns**: Bucket creation, public access blocking, versioning configuration, and lifecycle policies for all platform buckets
- **Delegates to**: IAM module for access policies; CloudFront module for frontend bucket origin configuration
- **Does not handle**: Bucket policies, CORS rules, or object-level configuration

## Key Concepts

Nine buckets are provisioned across four functional categories:

- **Medallion lakehouse** (`bronze`, `silver`, `gold`): Delta Lake storage layers for raw events, cleaned data, and star schema analytics. Versioning toggled by `enable_versioning` variable; old object versions expire after 90 days via a shared `lakehouse` lifecycle rule applied with `for_each`.
- **Simulation state** (`checkpoints`): Stores serialized simulation snapshots. Versioning is always enabled regardless of `enable_versioning` — a deliberate choice to protect against accidental checkpoint corruption.
- **Observability backends** (`logs`, `loki`, `tempo`): Airflow task logs, Loki log storage, and Tempo trace storage respectively. All three have a 30-day expiration lifecycle rule (not just noncurrent version expiration, but full object expiration).
- **CI artifacts** (`build_assets`): Docker layer cache and other build outputs that must survive soft resets of the data platform. Versioning always enabled.
- **Static hosting** (`frontend`): React SPA served via CloudFront. The `bucket_regional_domain_name` output is consumed by the CloudFront module as the origin domain.

## Non-Obvious Details

- **Bucket naming**: Names follow `{project_name}-{account_suffix}-{layer}` (e.g., `rideshare-123456789012-bronze`). The `account_suffix` is the AWS account ID, injected by the caller to guarantee global uniqueness without a random suffix.
- **Selective always-on versioning**: `checkpoints` and `build_assets` ignore the `enable_versioning` variable and are always versioned. This protects simulation state and CI cache from soft-reset operations that might disable versioning elsewhere.
- **Lifecycle policy distinction**: Lakehouse buckets use `noncurrent_version_expiration` (keeps current version, cleans old ones after 90 days). Observability buckets (`logs`, `loki`, `tempo`) use `expiration` (deletes all objects after 30 days, not just old versions).
- **Frontend bucket has no static website hosting resource**: It is served exclusively through CloudFront with OAC, so `aws_s3_bucket_website_configuration` is intentionally absent. All public access is blocked — CloudFront accesses it via bucket policy, not a public endpoint.

## Related Modules

- [infrastructure/terraform/foundation/modules/cloudfront](../cloudfront/CONTEXT.md) — Reverse dependency — Provides distribution_id, distribution_domain, distribution_arn (+1 more)
