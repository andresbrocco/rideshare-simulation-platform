# Look up the current AWS account ID for the state bucket name
data "aws_caller_identity" "current" {}

# Read foundation outputs from remote state
data "terraform_remote_state" "foundation" {
  backend = "s3"

  config = {
    bucket = "rideshare-tf-state-${data.aws_caller_identity.current.account_id}"
    key    = "foundation/terraform.tfstate"
    region = "us-east-1"
  }
}
