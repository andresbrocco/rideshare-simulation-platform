# Read foundation outputs from remote state
data "terraform_remote_state" "foundation" {
  backend = "s3"

  config = {
    bucket = "rideshare-tf-state"
    key    = "foundation/terraform.tfstate"
    region = "us-east-1"
  }
}
