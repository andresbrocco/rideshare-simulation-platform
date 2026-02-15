terraform {
  backend "s3" {
    bucket         = "rideshare-tf-state"
    key            = "platform/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "rideshare-tf-state-lock"
    encrypt        = true
  }
}
