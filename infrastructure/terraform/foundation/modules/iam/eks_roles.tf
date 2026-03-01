# --------------------------------------------------------------------------
# EKS Cluster Role
# --------------------------------------------------------------------------
resource "aws_iam_role" "eks_cluster" {
  name = "${var.project_name}-eks-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-eks-cluster"
  }
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# --------------------------------------------------------------------------
# EKS Node Instance Role
# --------------------------------------------------------------------------
resource "aws_iam_role" "eks_nodes" {
  name = "${var.project_name}-eks-nodes"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-eks-nodes"
  }
}

resource "aws_iam_role_policy_attachment" "eks_nodes_worker" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_nodes_cni" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "eks_nodes_ecr" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "eks_nodes_ebs_csi" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# Secrets Manager read access for External Secrets Operator running on nodes.
# Uses node role instead of IRSA since the EKS Pod Identity webhook may not
# be available during initial cluster bootstrap.
resource "aws_iam_role_policy" "eks_nodes_secrets_manager" {
  name = "secrets-manager-read"
  role = aws_iam_role.eks_nodes.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/*"
      }
    ]
  })
}

# --------------------------------------------------------------------------
# Pod Identity Role: Simulation (S3 checkpoints)
# --------------------------------------------------------------------------
resource "aws_iam_role" "simulation" {
  name = "${var.project_name}-simulation"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-simulation"
  }
}

resource "aws_iam_role_policy" "simulation_s3" {
  name = "s3-checkpoints"
  role = aws_iam_role.simulation.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arns.checkpoints,
          "${var.s3_bucket_arns.checkpoints}/*"
        ]
      }
    ]
  })
}

# --------------------------------------------------------------------------
# Pod Identity Role: Bronze Ingestion (S3 bronze)
# --------------------------------------------------------------------------
resource "aws_iam_role" "bronze_ingestion" {
  name = "${var.project_name}-bronze-ingestion"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-bronze-ingestion"
  }
}

resource "aws_iam_role_policy" "bronze_ingestion_s3" {
  name = "s3-bronze"
  role = aws_iam_role.bronze_ingestion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arns.bronze,
          "${var.s3_bucket_arns.bronze}/*"
        ]
      }
    ]
  })
}

# --------------------------------------------------------------------------
# Pod Identity Role: Airflow (all lakehouse buckets)
# --------------------------------------------------------------------------
resource "aws_iam_role" "airflow" {
  name = "${var.project_name}-airflow"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-airflow"
  }
}

resource "aws_iam_role_policy" "airflow_s3" {
  name = "s3-lakehouse"
  role = aws_iam_role.airflow.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arns.bronze,
          "${var.s3_bucket_arns.bronze}/*",
          var.s3_bucket_arns.silver,
          "${var.s3_bucket_arns.silver}/*",
          var.s3_bucket_arns.gold,
          "${var.s3_bucket_arns.gold}/*"
        ]
      }
    ]
  })
}

# --------------------------------------------------------------------------
# Pod Identity Role: Trino (read-only lakehouse)
# --------------------------------------------------------------------------
resource "aws_iam_role" "trino" {
  name = "${var.project_name}-trino"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-trino"
  }
}

resource "aws_iam_role_policy" "trino_s3" {
  name = "s3-read"
  role = aws_iam_role.trino.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arns.bronze,
          "${var.s3_bucket_arns.bronze}/*",
          var.s3_bucket_arns.silver,
          "${var.s3_bucket_arns.silver}/*",
          var.s3_bucket_arns.gold,
          "${var.s3_bucket_arns.gold}/*"
        ]
      }
    ]
  })
}

# --------------------------------------------------------------------------
# Pod Identity Role: Hive Metastore (read-only lakehouse)
# --------------------------------------------------------------------------
resource "aws_iam_role" "hive_metastore" {
  name = "${var.project_name}-hive-metastore"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-hive-metastore"
  }
}

resource "aws_iam_role_policy" "hive_metastore_s3" {
  name = "s3-read"
  role = aws_iam_role.hive_metastore.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arns.bronze,
          "${var.s3_bucket_arns.bronze}/*",
          var.s3_bucket_arns.silver,
          "${var.s3_bucket_arns.silver}/*",
          var.s3_bucket_arns.gold,
          "${var.s3_bucket_arns.gold}/*"
        ]
      }
    ]
  })
}

# --------------------------------------------------------------------------
# Pod Identity Role: External Secrets Operator (Secrets Manager read)
# --------------------------------------------------------------------------
resource "aws_iam_role" "eso" {
  name = "${var.project_name}-eso"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-eso"
  }
}

resource "aws_iam_role_policy" "eso_secrets_manager" {
  name = "secrets-manager-read"
  role = aws_iam_role.eso.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/*"
      }
    ]
  })
}
