# VPC CNI Add-on — must be installed BEFORE the node group.
# With bootstrap_self_managed_addons = false, nodes have no CNI at boot.
# Without a CNI, nodes stay NotReady and the node group never reaches ACTIVE,
# creating a deadlock if this addon depends_on the node group.
resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"

  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
}

# kube-proxy Add-on — installed before nodes so networking is ready at boot
resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"

  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
}
