# VPC & Network Topology

The physical network layout — what lives where. No data flow, just structure.

- **Public subnets only** — no private subnets or NAT Gateway (saves ~$32/month)
- **Two AZs** — required by ALB, provides basic fault tolerance
- **Single EKS node** — cost optimization for portfolio project (~$0.31/hr)

```mermaid
---
title: VPC & Network Topology
---
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
