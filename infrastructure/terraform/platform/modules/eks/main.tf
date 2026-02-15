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

  instance_types = [var.node_instance_type]

  disk_size = var.node_disk_size

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
