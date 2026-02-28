variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for ALB controller"
  type        = string
}

variable "aws_region" {
  description = "AWS region for ALB controller"
  type        = string
}
