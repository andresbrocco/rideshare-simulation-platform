# CONTEXT.md — Bootstrap

## Purpose

Creates the S3 bucket that stores Terraform remote state for all other Terraform layers (`foundation`, `platform`). This module must be applied once before any other layer can be initialized, because it provisions the backend that those layers depend on.

## Responsibility Boundaries

- **Owns**: The S3 state bucket lifecycle — creation, versioning, encryption, and public-access blocking
- **Delegates to**: `foundation` and `platform` layers for all actual infrastructure resources
- **Does not handle**: DynamoDB state locking (not used), IAM permissions for the deploy user, or any application-level resources

## Key Concepts

- **Bootstrap ordering**: This layer has no remote backend configured — its own state is stored locally (`terraform.tfstate` committed or kept on the operator's machine). All other layers reference the bucket it creates via `-backend-config` at `terraform init` time.
- **Account-scoped naming**: The bucket name is `rideshare-tf-state-{account_id}`, derived at apply time from `aws_caller_identity`, ensuring global uniqueness without hardcoding.

## Non-Obvious Details

- `prevent_destroy = true` is set on the S3 bucket, so `terraform destroy` in this layer will error. The bucket must be manually deleted (emptied first) if the platform is being fully decommissioned.
- The `outputs.tf` emits ready-to-paste `terraform init` commands (`foundation_init_command`, `platform_init_command`) that include the resolved bucket name — useful because the bucket name is only known after apply.
- This layer's local `terraform.tfstate` is the only state not stored remotely; losing it means losing track of the bucket resource in Terraform, though the bucket itself remains in AWS.
