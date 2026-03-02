# --------------------------------------------------------------------------
# EKS Access Entries — grant cluster admin to CI/CD role and local dev user.
# Uses API mode (API_AND_CONFIG_MAP) so access is managed via EKS API
# instead of the deprecated aws-auth ConfigMap.
# --------------------------------------------------------------------------
resource "aws_eks_access_entry" "github_actions" {
  cluster_name  = module.eks.cluster_name
  principal_arn = data.terraform_remote_state.foundation.outputs.github_actions_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "github_actions" {
  cluster_name  = module.eks.cluster_name
  principal_arn = data.terraform_remote_state.foundation.outputs.github_actions_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

resource "aws_eks_access_entry" "deploy_user" {
  cluster_name  = module.eks.cluster_name
  principal_arn = var.deploy_user_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "deploy_user" {
  cluster_name  = module.eks.cluster_name
  principal_arn = var.deploy_user_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

# EKS Module
module "eks" {
  source = "./modules/eks"

  project_name    = var.project_name
  cluster_version = var.cluster_version

  subnet_ids      = data.terraform_remote_state.foundation.outputs.public_subnet_ids
  eks_nodes_sg_id = data.terraform_remote_state.foundation.outputs.eks_nodes_sg_id
  vpc_cidr        = data.terraform_remote_state.foundation.outputs.vpc_cidr

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

# --------------------------------------------------------------------------
# EKS Pod Identity associations for workload IAM roles.
# EKS injects AWS credentials into pods by matching (cluster, namespace,
# service_account) to the linked IAM role — no OIDC provider or annotation
# on the ServiceAccount is required.
# --------------------------------------------------------------------------
resource "aws_eks_pod_identity_association" "simulation" {
  cluster_name    = module.eks.cluster_name
  namespace       = "rideshare-prod"
  service_account = "simulation"
  role_arn        = data.terraform_remote_state.foundation.outputs.simulation_role_arn
}

resource "aws_eks_pod_identity_association" "bronze_ingestion" {
  cluster_name    = module.eks.cluster_name
  namespace       = "rideshare-prod"
  service_account = "bronze-ingestion"
  role_arn        = data.terraform_remote_state.foundation.outputs.bronze_ingestion_role_arn
}

resource "aws_eks_pod_identity_association" "airflow" {
  cluster_name    = module.eks.cluster_name
  namespace       = "rideshare-prod"
  service_account = "airflow-scheduler"
  role_arn        = data.terraform_remote_state.foundation.outputs.airflow_role_arn
}

resource "aws_eks_pod_identity_association" "airflow_webserver" {
  cluster_name    = module.eks.cluster_name
  namespace       = "rideshare-prod"
  service_account = "airflow-webserver"
  role_arn        = data.terraform_remote_state.foundation.outputs.airflow_role_arn
}

resource "aws_eks_pod_identity_association" "trino" {
  cluster_name    = module.eks.cluster_name
  namespace       = "rideshare-prod"
  service_account = "trino"
  role_arn        = data.terraform_remote_state.foundation.outputs.trino_role_arn
}

resource "aws_eks_pod_identity_association" "hive_metastore" {
  cluster_name    = module.eks.cluster_name
  namespace       = "rideshare-prod"
  service_account = "hive-metastore"
  role_arn        = data.terraform_remote_state.foundation.outputs.hive_metastore_role_arn
}

resource "aws_eks_pod_identity_association" "loki" {
  cluster_name    = module.eks.cluster_name
  namespace       = "rideshare-prod"
  service_account = "loki"
  role_arn        = data.terraform_remote_state.foundation.outputs.loki_role_arn
}

resource "aws_eks_pod_identity_association" "tempo" {
  cluster_name    = module.eks.cluster_name
  namespace       = "rideshare-prod"
  service_account = "tempo"
  role_arn        = data.terraform_remote_state.foundation.outputs.tempo_role_arn
}

resource "aws_eks_pod_identity_association" "eso" {
  cluster_name    = module.eks.cluster_name
  namespace       = "external-secrets"
  service_account = "external-secrets"
  role_arn        = data.terraform_remote_state.foundation.outputs.eso_role_arn
}
