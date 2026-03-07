# CONTEXT.md — Cloudfront

## Purpose

Provisions a CloudFront distribution that serves the React control-panel SPA from a private S3 bucket over HTTPS with a custom domain. Also attaches the S3 bucket policy that grants CloudFront read access via Origin Access Control.

## Responsibility Boundaries

- **Owns**: CloudFront distribution configuration, Origin Access Control (OAC) resource, and the S3 bucket policy that authorizes it
- **Delegates to**: `s3` module (bucket creation), `acm` module (certificate provisioning), `route53` module (DNS alias record)
- **Does not handle**: CI/CD asset upload to S3, cache invalidation, or WAF attachment

## Key Concepts

- **Origin Access Control (OAC)**: The modern replacement for Origin Access Identity (OAI). Uses SigV4 signing to allow CloudFront to fetch objects from a private S3 bucket without making the bucket public. The bucket policy restricts access to `cloudfront.amazonaws.com` with a condition on `AWS:SourceArn` matching this specific distribution.
- **SPA error routing**: Both 403 and 404 S3 responses are rewritten to return `index.html` with HTTP 200. 403 is included because S3 returns 403 (not 404) for missing objects when the bucket is private, which is the normal case for client-side routes not matching a real S3 key.

## Non-Obvious Details

- The `cache_policy_id` value `658327ea-f89d-4fab-a63d-7e88639e58f6` is the AWS-managed **CachingOptimized** policy. It is not a project-specific resource — it is hardcoded by its well-known AWS ID.
- The ACM certificate (`certificate_arn`) **must** be provisioned in `us-east-1` regardless of the deployment region. CloudFront is a global service and only reads certificates from that region. The `acm` module is deployed separately into `us-east-1` to satisfy this constraint.
- `minimum_protocol_version = "TLSv1.2_2021"` enforces the strictest standard AWS TLS policy available for SNI-based distributions.

## Related Modules

- [infrastructure/terraform/foundation/modules/acm](../acm/CONTEXT.md) — Dependency — Provisions and DNS-validates an ACM TLS certificate for the platform's public do...
- [infrastructure/terraform/foundation/modules/route53](../route53/CONTEXT.md) — Dependency — Route 53 hosted zone and apex CloudFront alias record for the project domain
- [infrastructure/terraform/foundation/modules/s3](../s3/CONTEXT.md) — Dependency — Provision and configure all platform S3 buckets across medallion lakehouse, simu...
