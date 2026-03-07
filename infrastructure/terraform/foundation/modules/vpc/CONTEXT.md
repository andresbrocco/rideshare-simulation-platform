# CONTEXT.md — VPC

## Purpose

Provisions the AWS VPC networking layer for the rideshare platform, including the VPC itself, public subnets across multiple availability zones, routing infrastructure, and the three security groups required by EKS nodes, the Application Load Balancer, and RDS PostgreSQL.

## Responsibility Boundaries

- **Owns**: VPC, internet gateway, public subnets, route tables, and all three platform security groups (ALB, EKS nodes, RDS)
- **Delegates to**: The EKS module for cluster creation, the ALB module for load balancer provisioning, the RDS module for database provisioning
- **Does not handle**: Private subnets or NAT gateways (the platform uses only public subnets with EKS managed node groups), DNS zones, or certificate management

## Key Concepts

This module uses a public-only subnet design — all subnets have `map_public_ip_on_launch = true` and route directly to the internet gateway. There are no private subnets or NAT gateways.

Public subnets carry two Kubernetes-specific tags (`kubernetes.io/role/elb = 1` and `kubernetes.io/cluster/<name>-eks = shared`) that the AWS Load Balancer Controller requires to discover subnets for ALB provisioning.

## Non-Obvious Details

- **Security groups live here, not in their consumer modules**: All three security groups (ALB, EKS nodes, RDS) are defined in this VPC module and exported as outputs. This co-location avoids circular dependencies between modules that would arise if each module created its own security group referencing another module's resources.

- **EKS nodes use a broad VPC CIDR rule, not a SG-to-SG reference**: The EKS nodes security group allows all TCP from the VPC CIDR (`10.0.0.0/16`) rather than referencing only the ALB security group. This is intentional — EKS creates its own cluster security group automatically, which cannot be referenced by Terraform at plan time. Using a CIDR rule ensures health checks and pod traffic from both the Terraform-managed ALB SG and the EKS-managed cluster SG are permitted.

- **RDS security group has dual ingress rules**: Both an explicit SG reference (`eks_nodes` SG) and a VPC CIDR rule exist for port 5432. The SG reference covers the Terraform-managed node SG; the CIDR rule covers EKS-assigned pod IPs and the cluster SG created outside Terraform control.
