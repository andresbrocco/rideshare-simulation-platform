# CONTEXT.md — Route53

## Purpose

Creates and owns the Route 53 public hosted zone for the project domain (`ridesharing.portfolio.andresbrocco.com`) and optionally registers an apex A alias record pointing to the CloudFront distribution. This module is part of the foundation layer, meaning it is provisioned before platform-level resources (EKS, ALB, service DNS records).

## Responsibility Boundaries

- **Owns**: The Route 53 hosted zone and the apex domain A alias record (pointing to CloudFront).
- **Delegates to**: The platform-level `dns` module for subdomain records (e.g., wildcard or per-service CNAME/A records tied to the ALB).
- **Does not handle**: ACM certificate creation or validation DNS records (those live in the `acm` module), nor any subdomain records beyond the apex.

## Key Concepts

- **Apex alias record**: Route 53 does not support CNAME at the zone apex (`ridesharing.portfolio.andresbrocco.com`), so an A alias record pointing to the CloudFront distribution is used instead. This is why a separate `cloudfront_distribution_hosted_zone_id` variable is required — CloudFront distributions have a fixed hosted zone ID (`Z2FDTNDATAQYW2`) that must be passed explicitly for alias resolution.
- **Conditional creation**: The apex alias record is guarded by `count = var.cloudfront_distribution_domain_name != "" ? 1 : 0`, allowing the hosted zone to be provisioned in an initial bootstrap pass before CloudFront is deployed.

## Non-Obvious Details

- The `name_servers` output must be manually configured as NS records in the parent zone (`portfolio.andresbrocco.com`) to complete DNS delegation. Terraform cannot do this automatically if the parent zone is managed outside this codebase. Until delegation is in place, the hosted zone exists in Route 53 but is not publicly resolvable.
- Applying this module without providing `cloudfront_distribution_domain_name` is intentional and valid during foundation bootstrap; the apex record is added in a subsequent apply once CloudFront is available.
- The module exports `zone_id` for use by the `acm` module (DNS validation records) and the platform `dns` module (subdomain records).

## Related Modules

- [infrastructure/terraform/foundation/modules/cloudfront](../cloudfront/CONTEXT.md) — Reverse dependency — Provides distribution_id, distribution_domain, distribution_arn (+1 more)
