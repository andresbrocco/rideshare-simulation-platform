# EKS Cluster Bootstrap Sequence

Strict ordering constraints during cluster creation. Each step unlocks the next. vpc-cni must exist before nodes can reach `Ready`. The ALB controller's mutating webhook must be ready before coredns/ebs-csi addons install (otherwise the webhook rejects their pods). ArgoCD is installed last, after all cluster infrastructure is stable.

```mermaid
---
title: EKS Cluster Bootstrap Sequence
---
flowchart TB
    subgraph TF["Terraform Apply — infrastructure/terraform/platform/"]
        T1["1. EKS Cluster<br/><small>control plane created<br/>API server available</small>"]
        T2["2. vpc-cni + kube-proxy addons<br/><small>MUST exist before nodes join<br/>provides pod networking + Service routing</small>"]
        T3["3. Managed Node Group<br/><small>1x t3.xlarge, AL2023, 50GB gp3<br/>nodes join cluster, reach Ready state</small>"]
        T4["4. eks-pod-identity-agent addon<br/><small>DaemonSet — needs nodes to schedule onto<br/>enables workload IAM credentials</small>"]
        T5["5. ALB Controller (Helm)<br/><small>creates mutating webhook<br/>manages AWS load balancers from Ingress resources</small>"]
        T5B["5b. ESO + kube-state-metrics (Helm)<br/><small>parallel with ALB controller<br/>external secrets sync + K8s metrics</small>"]
        T6["6. coredns + ebs-csi addons<br/><small>installed AFTER ALB webhook ready<br/>avoids webhook race condition</small>"]
        T7["7. RDS PostgreSQL<br/><small>parallel with EKS setup<br/>credentials written to Secrets Manager</small>"]

        T1 --> T2 --> T3 --> T4 --> T5
        T4 --> T5B
        T5 --> T6
        T1 --> T7
    end

    subgraph WF["Deploy Workflow — post-Terraform"]
        W1["8. Create RDS databases<br/><small>kubectl run postgres:16 pod<br/>CREATE DATABASE airflow, metastore<br/>CREATE ROLE with grants</small>"]
        W2["9. Install ArgoCD<br/><small>kubectl apply install.yaml (v3.2.3)<br/>patch argocd-cm for kustomize</small>"]
        W3["10. Apply ArgoCD Application<br/><small>watches deploy branch<br/>kustomize build overlay</small>"]
    end

    subgraph CONVERGE["Phased Workload Convergence"]
        P1["Phase 1 — Infrastructure<br/><small>kafka, redis, prometheus,<br/>loki, tempo</small>"]
        P2["Phase 2 — Schema<br/><small>schema-registry</small>"]
        P3["Phase 3 — Application<br/><small>simulation, stream-processor,<br/>bronze-ingestion, trino, osrm</small>"]
        P4["Phase 4 — Data Pipeline<br/><small>airflow-webserver,<br/>airflow-scheduler</small>"]
        P5["Phase 5 — UI & Observability<br/><small>grafana, control-panel,<br/>performance-controller</small>"]
    end

    POST["Post-convergence<br/><small>provision visitor accounts<br/>start simulation<br/>create Route 53 wildcard DNS</small>"]

    T6 --> W1
    T7 --> W1
    W1 --> W2 --> W3
    W3 --> P1 --> P2 --> P3 --> P4 --> P5 --> POST

    style TF fill:#e3f2fd,stroke:#1565c0
    style WF fill:#fff3e0,stroke:#e65100
    style CONVERGE fill:#e8f5e9,stroke:#2e7d32
```
