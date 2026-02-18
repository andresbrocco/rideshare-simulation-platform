variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "rideshare"
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.33"
}

variable "subnet_ids" {
  description = "Subnet IDs for EKS cluster and nodes"
  type        = list(string)
}

variable "eks_nodes_sg_id" {
  description = "Security group ID for EKS nodes from foundation"
  type        = string
}

variable "cluster_role_arn" {
  description = "EKS cluster IAM role ARN from foundation"
  type        = string
}

variable "node_role_arn" {
  description = "EKS node IAM role ARN from foundation"
  type        = string
}

variable "node_instance_type" {
  description = "EC2 instance type for nodes"
  type        = string
  default     = "t3.xlarge"
}

variable "node_count" {
  description = "Number of nodes (fixed, no autoscaling)"
  type        = number
  default     = 3
}

variable "node_disk_size" {
  description = "EBS volume size per node (GB)"
  type        = number
  default     = 50
}
