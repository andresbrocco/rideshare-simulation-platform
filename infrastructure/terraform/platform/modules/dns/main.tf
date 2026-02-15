# Note: The actual ALB is created by the AWS Load Balancer Controller when the
# Kubernetes Ingress resource is applied. This DNS record should be created after
# the ALB exists, or managed outside Terraform.
#
# The Route 53 ALIAS record for api.${var.domain_name} must be created manually
# or via a second terraform apply after the Ingress resource creates the ALB.

resource "null_resource" "dns_note" {
  provisioner "local-exec" {
    command = <<-EOT
      echo "DNS record for api.${var.domain_name} must be created after ALB is provisioned by Kubernetes Ingress."
      echo "ALB DNS name will be available from the Ingress resource status."
      echo "Create Route 53 ALIAS record: api.${var.domain_name} -> ALB DNS name"
    EOT
  }
}
