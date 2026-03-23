# External Access, DNS & ALB Routing

How HTTP requests travel from a user's browser to backend services. Three distinct paths.

- **Apex domain** serves the React SPA via CloudFront + S3
- **Wildcard subdomains** route through a single shared ALB to EKS pods
- **Lambda Function URLs** are direct HTTPS endpoints (no ALB/DNS)

```mermaid
---
title: External Access, DNS & ALB Routing
---
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
