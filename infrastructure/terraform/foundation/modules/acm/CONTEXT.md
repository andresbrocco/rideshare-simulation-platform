# CONTEXT.md — ACM

## Purpose

Provisions and validates an AWS Certificate Manager (ACM) TLS certificate for the platform's public domain. Handles the full lifecycle: certificate request, automatic DNS validation record creation in Route 53, and blocking until the certificate reaches `ISSUED` status.

## Responsibility Boundaries

- **Owns**: ACM certificate resource, Route 53 DNS validation records, certificate validation waiter
- **Delegates to**: Route 53 (DNS zone must already exist and be provided via `route53_zone_id`)
- **Does not handle**: CloudFront distribution configuration, DNS zone creation, or domain registration

## Key Concepts

- **DNS validation**: Rather than email-based validation, the module uses DNS validation — it writes CNAME records to Route 53 that ACM checks to prove domain ownership. The `for_each` over `domain_validation_options` handles both the primary domain and all SANs in a single pass.
- **`create_before_destroy`**: The lifecycle rule ensures that when a certificate is replaced (e.g., adding a new SAN), the new certificate is validated and ready before the old one is destroyed, preventing a gap in TLS coverage.

## Non-Obvious Details

- **Must use `aws.us_east_1` provider alias**: CloudFront only accepts ACM certificates provisioned in `us-east-1`, regardless of the application's primary AWS region. The caller (root module) must pass `providers = { aws = aws.us_east_1 }` when invoking this module, or the certificate will be created in the wrong region and CloudFront will reject it.
- **`certificate_arn` output references the validation resource, not the certificate**: The output is `aws_acm_certificate_validation.main.certificate_arn` rather than `aws_acm_certificate.main.arn`. This means any downstream resource that depends on the output will implicitly wait for validation to complete before proceeding.
- **Validation timeout is 10 minutes**: DNS propagation can be slow. If Route 53 is not authoritative for the zone (e.g., NS records not delegated), validation will silently time out after 10 minutes and Terraform will error.

## Related Modules

- [infrastructure/terraform/foundation/modules/cloudfront](../cloudfront/CONTEXT.md) — Reverse dependency — Provides distribution_id, distribution_domain, distribution_arn (+1 more)
