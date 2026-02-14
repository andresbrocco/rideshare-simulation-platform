output "github_oidc_provider_arn" {
  description = "ARN of GitHub OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}

output "github_actions_role_arn" {
  description = "ARN of GitHub Actions role"
  value       = aws_iam_role.github_actions.arn
}

output "eks_cluster_role_arn" {
  description = "ARN of EKS cluster role"
  value       = aws_iam_role.eks_cluster.arn
}

output "eks_nodes_role_arn" {
  description = "ARN of EKS nodes role"
  value       = aws_iam_role.eks_nodes.arn
}

output "simulation_role_arn" {
  description = "ARN of simulation IRSA role"
  value       = aws_iam_role.simulation.arn
}

output "bronze_ingestion_role_arn" {
  description = "ARN of bronze-ingestion IRSA role"
  value       = aws_iam_role.bronze_ingestion.arn
}

output "airflow_role_arn" {
  description = "ARN of airflow IRSA role"
  value       = aws_iam_role.airflow.arn
}

output "trino_role_arn" {
  description = "ARN of trino IRSA role"
  value       = aws_iam_role.trino.arn
}

output "hive_metastore_role_arn" {
  description = "ARN of hive-metastore IRSA role"
  value       = aws_iam_role.hive_metastore.arn
}

output "eso_role_arn" {
  description = "ARN of External Secrets Operator IRSA role"
  value       = aws_iam_role.eso.arn
}
