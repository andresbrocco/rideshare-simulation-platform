# EKS Cluster
resource "aws_eks_cluster" "main" {
  name     = "${var.project_name}-eks"
  role_arn = var.cluster_role_arn
  version  = var.cluster_version

  vpc_config {
    subnet_ids              = var.subnet_ids
    security_group_ids      = [var.eks_nodes_sg_id]
    endpoint_public_access  = true
    endpoint_private_access = false
  }

  tags = {
    Name = "${var.project_name}-eks"
  }
}

# Allow ALB health checks to reach pods on the EKS-managed cluster security group.
# Nodes only get the cluster SG (not the custom eks_nodes_sg), so the ALB must be
# allowed inbound on the cluster SG. VPC CIDR covers all ALB SGs.
resource "aws_vpc_security_group_ingress_rule" "alb_to_cluster_sg" {
  security_group_id = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id

  ip_protocol = "tcp"
  from_port   = 0
  to_port     = 65535
  cidr_ipv4   = var.vpc_cidr
  description = "Allow TCP from VPC for ALB health checks"
}

# EKS Pod Identity Agent — required for Pod Identity associations (ALB controller, etc.)
resource "aws_eks_addon" "pod_identity_agent" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "eks-pod-identity-agent"

  depends_on = [
    aws_eks_node_group.main
  ]
}

# Launch template for EKS nodes with IMDS hop limit 2
# checkov:skip=CKV_AWS_341:EKS pods require hop limit 2 to reach IMDS through container networking
resource "aws_launch_template" "eks_nodes" {
  name_prefix = "${var.project_name}-eks-"

  instance_type = var.node_instance_type

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = var.node_disk_size
      volume_type = "gp3"
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project_name}-eks-node"
    }
  }
}

# EKS Managed Node Group
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-node-group"
  node_role_arn   = var.node_role_arn
  subnet_ids      = var.subnet_ids

  scaling_config {
    desired_size = var.node_count
    min_size     = var.node_count
    max_size     = var.node_count
  }

  launch_template {
    id      = aws_launch_template.eks_nodes.id
    version = aws_launch_template.eks_nodes.latest_version
  }

  ami_type = "AL2023_x86_64_STANDARD"

  tags = {
    Name = "${var.project_name}-node-group"
  }

  depends_on = [
    aws_eks_cluster.main
  ]
}

# OIDC Provider for IRSA
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [
    data.tls_certificate.cluster.certificates[0].sha1_fingerprint
  ]

  tags = {
    Name = "${var.project_name}-eks-oidc"
  }
}
