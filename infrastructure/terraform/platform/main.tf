# EKS Module
module "eks" {
  source = "./modules/eks"

  project_name    = var.project_name
  cluster_version = var.cluster_version

  subnet_ids      = data.terraform_remote_state.foundation.outputs.public_subnet_ids
  eks_nodes_sg_id = data.terraform_remote_state.foundation.outputs.eks_nodes_sg_id

  cluster_role_arn = data.terraform_remote_state.foundation.outputs.eks_cluster_role_arn
  node_role_arn    = data.terraform_remote_state.foundation.outputs.eks_nodes_role_arn

  node_instance_type = var.node_instance_type
  node_count         = var.node_count
  node_disk_size     = var.node_disk_size
}

# RDS Module
module "rds" {
  source = "./modules/rds"

  project_name     = var.project_name
  postgres_version = var.postgres_version
  instance_class   = var.rds_instance_class

  subnet_ids    = data.terraform_remote_state.foundation.outputs.public_subnet_ids
  rds_sg_id     = data.terraform_remote_state.foundation.outputs.rds_sg_id
  rds_secret_id = data.terraform_remote_state.foundation.outputs.rds_secret_id
}

# ALB Controller and Helm Charts Module
module "alb" {
  source = "./modules/alb"

  cluster_name = module.eks.cluster_name
  vpc_id       = data.terraform_remote_state.foundation.outputs.vpc_id
  aws_region   = var.aws_region
}

# DNS Module
module "dns" {
  source = "./modules/dns"

  domain_name = var.domain_name
}
