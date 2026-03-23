# Security & IAM

Two layers of access control: **network perimeter** (Security Groups) and **credential injection** (Pod Identity).

## Security Group Chain

Each layer only allows traffic from the layer directly above it. The internet can only reach the ALB; the ALB can only reach EKS pods within the VPC; only EKS pods can reach RDS.

```mermaid
---
title: Security Group Chain
---
flowchart LR
    INET(("Internet<br/>0.0.0.0/0"))

    ALBSG["ALB Security Group<br/>IN: TCP 443, 80 from anywhere<br/>OUT: all"]
    EKSSG["EKS Nodes Security Group<br/>IN: all TCP from 10.0.0.0/16<br/>IN: all protocols from self<br/>OUT: all"]
    RDSSG["RDS Security Group<br/>IN: TCP 5432 from EKS Nodes SG<br/>IN: TCP 5432 from 10.0.0.0/16<br/>OUT: all"]
    LAMBDASG["Lambda Security Group<br/>IN: none<br/>OUT: TCP 5432 to RDS SG only"]

    INET -->|"HTTPS :443<br/>HTTP :80"| ALBSG
    ALBSG -->|"any TCP port<br/>within VPC CIDR"| EKSSG
    EKSSG -->|"PostgreSQL :5432"| RDSSG
    LAMBDASG -->|"PostgreSQL :5432"| RDSSG

    style ALBSG fill:#e3f2fd,stroke:#1565c0
    style EKSSG fill:#e8f5e9,stroke:#2e7d32
    style RDSSG fill:#fff3e0,stroke:#e65100
    style LAMBDASG fill:#fce4ec,stroke:#c62828
```

## Pod Identity Associations

Each Kubernetes ServiceAccount is mapped to an IAM role via EKS Pod Identity. Pods receive temporary AWS credentials automatically — no secrets in environment variables.

```mermaid
---
title: Pod Identity Associations
---
flowchart LR
    subgraph SA["Kubernetes ServiceAccounts"]
        SA_SIM["simulation"]
        SA_BI["bronze-ingestion"]
        SA_AF["airflow-scheduler<br/>airflow-webserver"]
        SA_TR["trino"]
        SA_HM["hive-metastore"]
        SA_LO["loki"]
        SA_TE["tempo"]
        SA_ESO["external-secrets"]
        SA_ALB["aws-load-balancer-controller"]
    end

    PI["EKS Pod Identity Agent<br/>DaemonSet on every node<br/>trust: pods.eks.amazonaws.com"]

    subgraph ROLES["IAM Roles"]
        R_SIM["simulation-role"]
        R_BI["bronze-ingestion-role"]
        R_AF["airflow-role"]
        R_TR["trino-role"]
        R_HM["hive-metastore-role"]
        R_LO["loki-role"]
        R_TE["tempo-role"]
        R_ESO["external-secrets-role"]
        R_ALB["alb-controller-role"]
    end

    SA_SIM --> PI --> R_SIM
    SA_BI --> PI --> R_BI
    SA_AF --> PI --> R_AF
    SA_TR --> PI --> R_TR
    SA_HM --> PI --> R_HM
    SA_LO --> PI --> R_LO
    SA_TE --> PI --> R_TE
    SA_ESO --> PI --> R_ESO
    SA_ALB --> PI --> R_ALB

    style SA fill:#e3f2fd,stroke:#1565c0
    style ROLES fill:#e8f5e9,stroke:#2e7d32
    style PI fill:#fff3e0,stroke:#e65100
```
