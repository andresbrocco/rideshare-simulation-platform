# CONTEXT.md — DNS

## Purpose

Placeholder Terraform module that acknowledges the need for a Route 53 ALIAS record pointing `api.<domain>` at the Application Load Balancer, but does not create that record itself. It exists to document the manual step and to output the expected API domain name for downstream modules.

## Responsibility Boundaries

- **Owns**: Outputting the `api.<domain>` FQDN string for use by other Terraform resources.
- **Delegates to**: The AWS Load Balancer Controller (running inside Kubernetes) for actual ALB creation; a human operator or a second Terraform apply for creating the Route 53 ALIAS record.
- **Does not handle**: Route 53 zone management, ACM certificate issuance, or ALB provisioning.

## Non-Obvious Details

- The module contains no real Terraform-managed AWS resources. Its only resource is a `null_resource` that prints instructions at apply time.
- The Route 53 ALIAS record cannot be created in the same Terraform apply that sets up the EKS cluster because the ALB DNS name is only known after the Kubernetes Ingress resource is applied and the AWS Load Balancer Controller provisions the ALB. This is a chicken-and-egg dependency: Terraform cannot reference an ALB that does not yet exist.
- Any automation that depends on `outputs.api_domain` receives only a computed string (`"api.<domain_name>"`); it does not verify that a corresponding DNS record actually exists.
