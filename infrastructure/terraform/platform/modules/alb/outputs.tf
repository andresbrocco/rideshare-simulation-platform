output "alb_controller_role_arn" {
  description = "ARN of AWS Load Balancer Controller IAM role"
  value       = aws_iam_role.alb_controller.arn
}

output "helm_releases" {
  description = "Deployed Helm releases"
  value = {
    alb_controller     = helm_release.aws_load_balancer_controller.name
    external_secrets   = helm_release.external_secrets.name
    kube_state_metrics = helm_release.kube_state_metrics.name
  }
}
