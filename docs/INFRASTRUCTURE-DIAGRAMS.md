# Infrastructure Diagrams

Ten diagrams covering Docker, Kubernetes, Terraform, ArgoCD, and GitHub Actions as applied to this project.

---

## 1. Docker Compose Service Dependency Graph

Services organized by startup phase. Arrows represent `depends_on` blocking conditions (`healthy` or `completed_successfully`). Dashed borders indicate one-shot containers that run and exit. All services implicitly depend on `secrets-init` completing (shown via the dashed edge to each profile group).

![Docker Compose Dependencies](diagrams/out/infra-01-docker-compose.svg)

---

## 2. Secrets Flow: Local vs Production

Two parallel paths to the same result: credentials injected into service environments. Local uses a shared Docker volume with `.env` files. Production uses External Secrets Operator syncing Kubernetes Secrets from AWS Secrets Manager.

![Secrets Flow](diagrams/out/infra-02-secrets-flow.svg)

---

## 3. Kubernetes Resource Topology

How Kubernetes resource types relate to each other within the cluster. Workload controllers create Pods. Pods consume ConfigMaps, Secrets, and storage. Services route traffic to Pods. Ingress/Gateway exposes Services externally.

![K8s Resource Topology](diagrams/out/infra-03-k8s-topology.svg)

---

## 4. Terraform Three-Layer Architecture

Infrastructure split into three workspaces with different lifecycles and costs. `bootstrap` runs once. `foundation` is long-lived and cheap. `platform` is ephemeral and expensive — created on deploy, destroyed on teardown. Outputs flow from foundation to platform via `terraform_remote_state`.

![Terraform Layers](diagrams/out/infra-04-terraform-layers.svg)

---

## 5. Network Topology: Three Access Paths

Three different networking models depending on context. Docker Compose exposes services via host port mapping. Kind cluster uses Envoy Gateway with path-based routing. Production EKS uses an AWS ALB with subdomain-based routing.

![Network Access Paths](diagrams/out/infra-05-network-paths.svg)

---

## 6. CI/CD Pipeline Flow

The full path from code push to production deployment. Automated workflows trigger on push/CI success. Manual workflows handle platform lifecycle (deploy, teardown, reset). The `deploy` branch bridges Terraform-provisioned infrastructure with ArgoCD-managed workloads.

![CI/CD Pipeline](diagrams/out/infra-06-cicd-pipeline.svg)

---

## 7. IAM & Authentication Chains

Two distinct trust chains: GitHub Actions authenticates via OIDC federation (short-lived tokens, no stored credentials). EKS workloads authenticate via Pod Identity (the Pod Identity Agent DaemonSet intercepts SDK requests and vends temporary STS credentials).

![IAM Chains](diagrams/out/infra-07-iam-chains.svg)

---

## 8. Kustomize Overlay Composition

A template-free layering system. Base manifests define all resources with local-dev defaults. The shared `aws-production` component patches images, endpoints, storage, and adds production-only resources. Two mutually exclusive overlays select the Trino catalog backend (Hive Metastore vs AWS Glue).

![Kustomize Composition](diagrams/out/infra-08-kustomize.svg)

---

## 9. ArgoCD GitOps Reconciliation Loop

ArgoCD continuously reconciles the `deploy` branch with live cluster state. The deploy workflow is the only writer to the `deploy` branch. Self-heal reverts manual `kubectl` changes. Prune deletes resources removed from Git. Replica counts are excluded from drift detection to allow manual scaling.

![ArgoCD Loop](diagrams/out/infra-09-argocd.svg)

---

## 10. EKS Cluster Bootstrap Sequence

Strict ordering constraints during cluster creation. Each step unlocks the next. vpc-cni must exist before nodes can reach `Ready`. The ALB controller's mutating webhook must be ready before coredns/ebs-csi addons install (otherwise the webhook rejects their pods). ArgoCD is installed last, after all cluster infrastructure is stable.

![EKS Bootstrap](diagrams/out/infra-10-eks-bootstrap.svg)
