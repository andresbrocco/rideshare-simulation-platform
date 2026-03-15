# infrastructure/policies

> IAM-compatible policy documents applied to MinIO (local) and S3 (production) for access control.

## Quick Reference

### Policy Files

| File | Policy Name | Purpose |
|------|-------------|---------|
| `minio-visitor-readonly.json` | `visitor-readonly` | Read-only access to the `rideshare-gold` bucket for provisioned visitor accounts |

### Bucket Permissions Granted

| Resource | Actions Allowed |
|----------|----------------|
| `arn:aws:s3:::rideshare-gold/*` | `s3:GetObject` |
| `arn:aws:s3:::rideshare-gold` | `s3:ListBucket` |

Visitor accounts receive **no** write access and cannot read Bronze or Silver buckets.

## Usage

### How the Policy Is Applied

The policy document is loaded and registered by `provision_visitor()` on every provisioning call (idempotent). It is consumed from two locations depending on context:

| Context | File Location |
|---------|--------------|
| Lambda runtime (bundled zip) | Co-located alongside `provision_minio_visitor.py` in the zip root |
| Local dev / scripts | `infrastructure/policies/minio-visitor-readonly.json` (this directory) |
| Docker Compose (lambda-local container) | Mounted read-only at `/app/lambda/minio-visitor-readonly.json` |

The provisioning code tries the co-located path first and falls back to the canonical path here.

### Registering the Policy Manually

Against a running local MinIO (port 9001 admin API):

```bash
# Using mc (MinIO client)
mc alias set local http://localhost:9000 minioadmin minioadmin
mc admin policy create local visitor-readonly infrastructure/policies/minio-visitor-readonly.json
```

### Updating the Policy

1. Edit `minio-visitor-readonly.json`
2. The next provisioning call (Lambda invocation or script run) will re-register it — no separate deployment step needed for local dev
3. For production Lambda, re-deploy the Lambda zip via the `deploy-lambda` GitHub Actions workflow (the file is bundled into the zip artifact)

## Common Tasks

### Verify the policy is registered in local MinIO

```bash
mc admin policy info local visitor-readonly
```

### List all MinIO users with this policy

```bash
mc admin user list local
```

### Check which policies are attached to a visitor account

```bash
mc admin user info local <visitor-email>
```

## Troubleshooting

**Policy not found after provisioning**
The provisioning function registers the policy on every call. If it appears missing, confirm the Lambda (or script) had read access to the policy file path. Check the Lambda log for `MinioAdminException`.

**Visitor can list the bucket but cannot read objects**
Verify the `s3:GetObject` statement's `Resource` ends with `/*`. Without the wildcard the object-level permission is absent.

**Policy updates not taking effect in production**
The Lambda zip must be rebuilt and redeployed — the policy JSON is bundled at deploy time. Run the `deploy-lambda` workflow.

## Related

- [services/auth-deploy/README.md](../../services/auth-deploy/README.md) — Lambda that calls `provision_visitor()`
- [infrastructure/scripts/provision_minio_visitor.py](../scripts/provision_minio_visitor.py) — Standalone script version for local dev
