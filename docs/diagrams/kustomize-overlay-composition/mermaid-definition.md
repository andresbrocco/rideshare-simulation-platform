# Kustomize Overlay Composition

A template-free layering system. Base manifests define all resources with local-dev defaults. The shared `aws-production` component patches images, endpoints, storage, and adds production-only resources. Two mutually exclusive overlays select the Trino catalog backend (Hive Metastore vs AWS Glue).

```mermaid
---
title: Kustomize Overlay Composition
---
flowchart TB
    subgraph BASE["manifests/ — Base Resources"]
        B_WL["17 Deployments, 3 StatefulSets,<br/>2 DaemonSets, 1 CronJob, 2 Jobs"]
        B_SVC["20+ Services (all ClusterIP)"]
        B_CFG["12+ ConfigMaps, 2 ExternalSecrets"]
        B_IMG["Images: rideshare-*:local<br/>imagePullPolicy: Never"]
        B_STORE["Storage: mostly emptyDir"]
        B_LOCAL["Endpoints: LocalStack, MinIO"]
    end

    subgraph COMP["components/aws-production/ — Shared Patches (~20 patches)"]
        C_IMG["Images → ECR URIs<br/>imagePullPolicy: IfNotPresent"]
        C_ING["+ 6 ALB Ingress resources<br/>(subdomain routing, ACM cert)"]
        C_SA["+ 9 ServiceAccounts<br/>(for Pod Identity)"]
        C_STORE["Kafka: emptyDir → EBS PVC<br/>+ EBS gp3 StorageClass"]
        C_EP["Remove LocalStack endpoints<br/>Inject real AWS endpoints"]
        C_RBAC["+ Prometheus ClusterRole/Binding<br/>(K8s service discovery)"]
        C_PKG["+ airflow-dbt-project ConfigMap<br/>+ airflow-ge-project ConfigMap<br/>(packaged tarballs)"]
    end

    subgraph OVL_D["overlays/production-duckdb/"]
        D_INC["Includes: base + aws-production"]
        D_HIVE["+ Hive Metastore Deployment<br/>+ postgres-metastore StatefulSet"]
        D_CAT["Trino catalog: thrift://hive-metastore:9083"]
        D_NS["namespace: rideshare-prod"]
    end

    subgraph OVL_G["overlays/production-glue/"]
        G_INC["Includes: base + aws-production"]
        G_NO["Hive Metastore omitted<br/>postgres-metastore omitted"]
        G_CAT["Trino catalog: AWS Glue Data Catalog"]
        G_DBT["Airflow: DBT_RUNNER=glue"]
    end

    RESOLVED_D["Resolved YAML<br/><small>kustomize build → ~60 resources<br/>with Hive Metastore</small>"]
    RESOLVED_G["Resolved YAML<br/><small>kustomize build → ~55 resources<br/>with Glue catalog</small>"]

    BASE --> COMP
    COMP --> OVL_D --> RESOLVED_D
    COMP --> OVL_G --> RESOLVED_G

    style BASE fill:#e3f2fd,stroke:#1565c0
    style COMP fill:#fff3e0,stroke:#e65100
    style OVL_D fill:#e8f5e9,stroke:#2e7d32
    style OVL_G fill:#f3e5f5,stroke:#6a1b9a
```
