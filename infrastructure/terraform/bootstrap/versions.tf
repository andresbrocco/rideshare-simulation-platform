terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.28.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "rideshare-simulation-platform"
      ManagedBy   = "terraform"
      Environment = "bootstrap"
    }
  }
}
