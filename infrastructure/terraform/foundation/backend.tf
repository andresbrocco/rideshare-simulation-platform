# Bucket is supplied via -backend-config at init time
# so that the account-specific suffix is not hardcoded here.
# Example:
#   terraform init \
#     -backend-config="bucket=rideshare-tf-state-<ACCOUNT_ID>"
terraform {
  backend "s3" {
    key          = "foundation/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
