# Kubernetes Internal Networking

Service-to-service communication inside the EKS cluster. All services use ClusterIP (internal only). DNS names follow the `service-name:port` convention. The VPC CNI plugin assigns each pod a real VPC IP address.

```mermaid
---
title: Kubernetes Internal Networking
---
flowchart TB
    subgraph RT["Real-Time Pipeline"]
        SIM["simulation:8000"]
        KAFKA["kafka-0.kafka:29092<br/>headless StatefulSet"]
        SR["schema-registry:8081"]
        SP["stream-processor:8080"]
        REDIS["redis:6379"]
        OSRM["osrm:5000"]
    end

    subgraph BATCH["Batch Pipeline"]
        BI["bronze-ingestion"]
        AF["airflow:8082<br/>scheduler + webserver"]
        TRINO["trino:8080"]
        HIVE["hive-metastore:9083<br/>Thrift protocol"]
    end

    subgraph STORE["Storage"]
        S3["S3 / MinIO:9000"]
        PG_HIVE["postgres-metastore:5432"]
        PG_AF["airflow-postgres:5432"]
        RDS["RDS PostgreSQL:5432<br/>external to cluster"]
    end

    subgraph MON["Monitoring"]
        GRAF["grafana:3001"]
        PROM["prometheus:9090"]
        LOKI["loki:3100"]
        TEMPO["tempo:4317"]
        OTEL["otel-collector:4317"]
    end

    %% Real-time event flow
    SIM -->|"publish events"| KAFKA
    SIM -->|"route geometry"| OSRM
    SIM -->|"checkpoint state"| RDS
    SP -->|"consume events"| KAFKA
    SP -->|"validate schemas"| SR
    SP -->|"fan-out state"| REDIS

    %% Batch data flow
    BI -->|"consume events"| KAFKA
    BI -->|"write bronze layer"| S3
    AF -->|"orchestrate DBT"| TRINO
    TRINO -->|"catalog queries"| HIVE
    TRINO -->|"read/write Delta"| S3
    HIVE -->|"metadata"| PG_HIVE
    AF -->|"DAG state"| PG_AF

    %% Monitoring flow
    PROM -.->|"scrape /metrics"| SIM
    PROM -.->|"scrape /metrics"| SP
    OTEL -.->|"forward metrics"| PROM
    OTEL -.->|"forward logs"| LOKI
    OTEL -.->|"forward traces"| TEMPO
    GRAF -->|"query metrics"| PROM
    GRAF -->|"query logs"| LOKI
    GRAF -->|"query traces"| TEMPO
    GRAF -->|"query analytics"| TRINO

    style RT fill:#e3f2fd,stroke:#1565c0
    style BATCH fill:#e8f5e9,stroke:#2e7d32
    style STORE fill:#fff3e0,stroke:#e65100
    style MON fill:#f3e5f5,stroke:#6a1b9a
```
