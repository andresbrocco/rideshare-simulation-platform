# Read foundation outputs from remote state
data "terraform_remote_state" "foundation" {
  backend = "s3"

  config = {
    bucket = "rideshare-tf-state"
    key    = "foundation/terraform.tfstate"
    region = "us-east-1"
  }
}

# Current AWS account and region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
