# Network Architecture Diagrams

Four diagrams covering the cloud networking layers of the rideshare simulation platform on AWS (EKS).

---

## 1. VPC & Network Topology

The physical network layout — what lives where. No data flow, just structure.

- **Public subnets only** — no private subnets or NAT Gateway (saves ~$32/month)
- **Two AZs** — required by ALB, provides basic fault tolerance
- **Single EKS node** — cost optimization for portfolio project (~$0.31/hr)

```mermaid
flowchart TB
    INET(("Internet"))

    subgraph VPC["VPC: rideshare-vpc | 10.0.0.0/16"]
        IGW["Internet Gateway<br/>rideshare-igw"]

        RT["Route Table<br/>0.0.0.0/0 -> IGW<br/>10.0.0.0/16 -> local"]

        subgraph AZA["Availability Zone: us-east-1a"]
            subgraph SUBA["Public Subnet: 10.0.1.0/24"]
                NODE["EKS Node<br/>t3.xlarge, 1 node"]
                RDS["RDS PostgreSQL<br/>db.t4g.micro<br/>publicly_accessible = false"]
                LRDS["Lambda: rds-reset<br/>in-VPC, egress to RDS only"]
            end
        end

        subgraph AZB["Availability Zone: us-east-1b"]
            subgraph SUBB["Public Subnet: 10.0.2.0/24"]
                HA["Standby<br/>ALB requires min 2 AZs"]
            end
        end

        NONAT["No NAT Gateway<br/>cost optimization: all subnets<br/>are public instead"]
    end

    INET <-->|"public traffic"| IGW
    IGW <--> SUBA
    IGW <--> SUBB
    RT -.- SUBA
    RT -.- SUBB

    style NONAT fill:#fff3e0,stroke:#e65100,stroke-dasharray: 5 5
    style SUBA fill:#e3f2fd,stroke:#1565c0
    style SUBB fill:#e3f2fd,stroke:#1565c0
    style VPC fill:#f5f5f5,stroke:#424242
```

---

## 2. External Access, DNS & ALB Routing

How HTTP requests travel from a user's browser to backend services. Three distinct paths.

- **Apex domain** serves the React SPA via CloudFront + S3
- **Wildcard subdomains** route through a single shared ALB to EKS pods
- **Lambda Function URLs** are direct HTTPS endpoints (no ALB/DNS)

```mermaid
flowchart LR
    B["Browser"]

    subgraph DNS["Route 53"]
        APEX["A record<br/>ridesharing.portfolio<br/>.andresbrocco.com"]
        WILD["A records<br/>*.ridesharing.portfolio<br/>.andresbrocco.com"]
    end

    subgraph CDN["CloudFront CDN"]
        CF["HTTPS only<br/>TLSv1.2<br/>Origin Access Control"]
    end

    S3["S3 Bucket<br/>React SPA static files"]

    subgraph LB["Shared ALB | IngressGroup: rideshare"]
        ALB["HTTPS :443<br/>ACM wildcard certificate<br/>target-type: ip"]
    end

    subgraph PODS["EKS Pods — routed by hostname"]
        SIM["simulation:8000"]
        GRAF["grafana:3001"]
        AIR["airflow:8082"]
        TRI["trino:8080"]
        PROM["prometheus:9090"]
        CP["control-panel:80"]
    end

    subgraph LAM["Lambda Function URLs"]
        AUTH["auth-deploy<br/>visitor auth + platform lifecycle"]
        CHAT["ai-chat<br/>AI assistant"]
    end

    B --> DNS
    APEX -->|"alias"| CF -->|"OAC sigv4"| S3
    WILD -->|"alias"| ALB
    ALB -->|"api.*"| SIM
    ALB -->|"grafana.*"| GRAF
    ALB -->|"airflow.*"| AIR
    ALB -->|"trino.*"| TRI
    ALB -->|"prometheus.*"| PROM
    ALB -->|"control-panel.*"| CP
    B -->|"direct HTTPS<br/>no DNS alias"| LAM

    style DNS fill:#e8f5e9,stroke:#2e7d32
    style LB fill:#e3f2fd,stroke:#1565c0
    style CDN fill:#fff3e0,stroke:#e65100
    style LAM fill:#fce4ec,stroke:#c62828
```

---

## 3. Kubernetes Internal Networking

Service-to-service communication inside the EKS cluster. All services use ClusterIP (internal only). DNS names follow the `service-name:port` convention. The VPC CNI plugin assigns each pod a real VPC IP address.

```mermaid
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

---

## 4. Security & IAM

Two layers of access control: **network perimeter** (Security Groups) and **credential injection** (Pod Identity).

### 4a. Security Group Chain

Each layer only allows traffic from the layer directly above it. The internet can only reach the ALB; the ALB can only reach EKS pods within the VPC; only EKS pods can reach RDS.

```mermaid
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

### 4b. Pod Identity Associations

Each Kubernetes ServiceAccount is mapped to an IAM role via EKS Pod Identity. Pods receive temporary AWS credentials automatically — no secrets in environment variables.

```mermaid
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
