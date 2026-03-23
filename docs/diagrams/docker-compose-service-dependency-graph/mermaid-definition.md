# Docker Compose Service Dependency Graph

Services organized by startup phase. Arrows represent `depends_on` blocking conditions (`healthy` or `completed_successfully`). Dashed borders indicate one-shot containers that run and exit. All services implicitly depend on `secrets-init` completing (shown via the dashed edge to each profile group).

```mermaid
---
title: Docker Compose Service Dependency Graph
---
flowchart TB
    LS["localstack<br/><small>AWS emulation on :4566</small>"]
    SI["secrets-init<br/><small>one-shot: seed-secrets.py → fetch-secrets.py<br/>writes /secrets/core.env, data-pipeline.env, monitoring.env</small>"]
    LI["lambda-init<br/><small>one-shot: deploys auth + chat Lambdas to LocalStack</small>"]

    LS -->|"healthy"| SI -->|"completed"| LI

    subgraph CORE["Core Profile"]
        K["kafka<br/><small>KRaft, SASL/PLAIN</small>"]
        KI["kafka-init<br/><small>one-shot: creates 9 topics</small>"]
        SR["schema-registry<br/><small>BASIC auth</small>"]
        R["redis<br/><small>requirepass</small>"]
        OSRM["osrm<br/><small>Sao Paulo routing</small>"]
        SP["stream-processor"]
        SIM["simulation<br/><small>the main engine</small>"]
        CP["control-panel<br/><small>React + deck.gl</small>"]

        K -->|"healthy"| KI
        KI --> SR
        KI --> SP
        R --> SP
        KI --> SIM
        SR --> SIM
        R --> SIM
        OSRM --> SIM
        SP -->|"healthy"| SIM
        SIM -->|"healthy"| CP
    end

    subgraph DATA["Data-Pipeline Profile"]
        M["minio<br/><small>S3-compatible</small>"]
        MI["minio-init<br/><small>one-shot: creates 7 buckets</small>"]
        BI["bronze-ingestion"]
        PA["postgres-airflow"]
        PM["postgres-metastore"]
        HM["hive-metastore<br/><small>Thrift :9083</small>"]
        TR["trino<br/><small>SQL engine</small>"]
        AW["airflow-webserver<br/><small>runs DB migrations</small>"]
        AS["airflow-scheduler"]
        DT["delta-table-init<br/><small>one-shot: registers Delta tables</small>"]

        M -->|"healthy"| MI
        MI --> BI
        KI --> BI
        PM -->|"healthy"| HM
        M -->|"healthy"| HM
        HM -->|"healthy"| TR
        PA -->|"healthy"| AW
        AW -->|"healthy"| AS
        TR -->|"healthy"| DT
        MI --> DT
    end

    subgraph MON["Monitoring Profile"]
        PR["prometheus"]
        LO["loki"]
        TE["tempo"]
        OT["otel-collector"]
        GR["grafana"]
        CA["cadvisor"]
        KE["kafka-exporter"]
        RE["redis-exporter"]

        MI --> LO
        MI --> TE
        PR --> OT
        LO --> OT
        TE --> OT
        PR --> GR
        LO --> GR
        TE --> GR
    end

    subgraph PERF["Performance Profile"]
        PC["perf-controller<br/><small>PID auto-scaler</small>"]
    end

    SIM --> PC
    PR --> PC
    OT --> PC

    SI -.->|"all services wait<br/>for this to complete"| K
    SI -.-> R
    SI -.-> M
    SI -.-> PA
    SI -.-> PM
    SI -.-> PR
    SI -.-> OSRM

    style SI fill:#fff,stroke:#999,stroke-dasharray: 5 5
    style LI fill:#fff,stroke:#999,stroke-dasharray: 5 5
    style KI fill:#fff,stroke:#999,stroke-dasharray: 5 5
    style MI fill:#fff,stroke:#999,stroke-dasharray: 5 5
    style DT fill:#fff,stroke:#999,stroke-dasharray: 5 5
    style CORE fill:#e3f2fd,stroke:#1565c0
    style DATA fill:#e8f5e9,stroke:#2e7d32
    style MON fill:#f3e5f5,stroke:#6a1b9a
    style PERF fill:#fff3e0,stroke:#e65100
```
