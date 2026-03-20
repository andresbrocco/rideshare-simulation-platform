# Infrastructure Diagrams

Ten diagrams covering Docker, Kubernetes, Terraform, ArgoCD, and GitHub Actions as applied to this project.

---

## 1. Docker Compose Service Dependency Graph

Services organized by startup phase. Arrows represent `depends_on` blocking conditions (`healthy` or `completed_successfully`). Dashed borders indicate one-shot containers that run and exit. All services implicitly depend on `secrets-init` completing (shown via the dashed edge to each profile group).

```mermaid
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

---

## 2. Secrets Flow: Local vs Production

Two parallel paths to the same result: credentials injected into service environments. Local uses a shared Docker volume with `.env` files. Production uses External Secrets Operator syncing Kubernetes Secrets from AWS Secrets Manager.

```mermaid
flowchart TB
    subgraph LOCAL["Local Development — Docker Compose"]
        direction LR
        LS2["LocalStack<br/>Secrets Manager<br/>emulation"]
        SEED["seed-secrets.py<br/>upserts 7 secret groups<br/>under rideshare/*<br/>default: admin/admin"]
        FETCH["fetch-secrets.py<br/>reads groups, applies<br/>key transformations:<br/>Airflow __, GF_ prefixes,<br/>bcrypt hash for Trino"]
        VOL[("secrets-volume<br/>/secrets/core.env<br/>/secrets/data-pipeline.env<br/>/secrets/monitoring.env")]
        ENT["Container entrypoint<br/>set -a<br/>. /secrets/core.env<br/>set +a<br/>exec app"]

        LS2 --> SEED --> FETCH --> VOL --> ENT
    end

    subgraph PROD["Production — EKS"]
        direction LR
        SM["AWS Secrets Manager<br/>rideshare/api-key<br/>rideshare/core<br/>rideshare/data-pipeline<br/>rideshare/monitoring<br/>(real random passwords)"]
        SS["SecretStore CRD<br/>points ESO at<br/>AWS Secrets Manager<br/>(node role credentials)"]
        ES["ExternalSecret CRDs<br/>api-keys-sync → 1 key<br/>app-credentials-sync → 14 keys"]
        KS["Kubernetes Secrets<br/>api-keys<br/>app-credentials"]
        POD["Pod spec<br/>env:<br/>  - name: REDIS_PASSWORD<br/>    valueFrom:<br/>      secretKeyRef:<br/>        name: app-credentials<br/>        key: REDIS_PASSWORD"]

        SM --> SS --> ES --> KS --> POD
    end

    style LOCAL fill:#e3f2fd,stroke:#1565c0
    style PROD fill:#e8f5e9,stroke:#2e7d32
```

---

## 3. Kubernetes Resource Topology

How Kubernetes resource types relate to each other within the cluster. Workload controllers create Pods. Pods consume ConfigMaps, Secrets, and storage. Services route traffic to Pods. Ingress/Gateway exposes Services externally.

```mermaid
flowchart TB
    subgraph EXT["External Traffic"]
        GW["Gateway + HTTPRoute<br/><small>local: Envoy Gateway, path-based</small>"]
        ING["Ingress<br/><small>prod: 6 ALB rules, subdomain-based</small>"]
    end

    subgraph NS["Namespace: rideshare-prod"]
        subgraph WL["Workload Controllers → create Pods"]
            DEP["Deployments (17)<br/><small>simulation, stream-processor, redis,<br/>grafana, prometheus, minio, trino...</small>"]
            STS["StatefulSets (3)<br/><small>kafka (stable identity for KRaft),<br/>airflow-postgres, postgres-metastore</small>"]
            DS["DaemonSets (2)<br/><small>cadvisor (every node, reads Docker socket),<br/>otel-collector-logs (reads /var/log/pods)</small>"]
            CJ["CronJob (1)<br/><small>bronze-init: register Delta tables<br/>every 10min, concurrencyPolicy: Replace</small>"]
            JOB["Jobs (2)<br/><small>kafka-init, minio-init<br/>run-to-completion, no restart</small>"]
        end

        subgraph NET["Networking"]
            SVC["Services (ClusterIP)<br/><small>stable DNS name + IP<br/>load balances across pod replicas</small>"]
            HL["Headless Service<br/><small>kafka: clusterIP=None<br/>DNS resolves to pod IPs directly<br/>enables kafka-0.kafka:29092</small>"]
        end

        subgraph CFG["Configuration"]
            CM["ConfigMaps (12+)<br/><small>core-config, prometheus-config,<br/>grafana-dashboards-*, loki-config,<br/>otel-collector-config, airflow-dags...</small>"]
            SEC["Secrets (2)<br/><small>api-keys (API_KEY)<br/>app-credentials (14 keys)<br/>managed by ESO</small>"]
        end

        subgraph STR["Storage"]
            ED["emptyDir<br/><small>ephemeral, lost on pod restart<br/>used by most services</small>"]
            PVC["PersistentVolumeClaim<br/><small>kafka-data: 10Gi EBS gp3 (prod)<br/>survives pod restarts</small>"]
            HP["hostPath<br/><small>DaemonSets only:<br/>/var/log, /sys, /var/run/docker.sock</small>"]
        end

        PODS["Pods<br/><small>init containers (wait-for-X polls)<br/>→ main container</small>"]
    end

    subgraph ESO_NS["Namespace: external-secrets"]
        ESO["External Secrets Operator<br/><small>Helm chart v0.11.0</small>"]
    end

    GW --> SVC
    ING --> SVC
    DEP --> PODS
    STS --> PODS
    DS --> PODS
    CJ --> JOB
    JOB --> PODS
    SVC --> PODS
    HL --> PODS
    CM -->|"volumeMounts /<br/>envFrom"| PODS
    SEC -->|"env.valueFrom.<br/>secretKeyRef"| PODS
    ED --> PODS
    PVC --> PODS
    HP --> PODS
    ESO -->|"syncs AWS SM<br/>→ K8s Secrets"| SEC

    style EXT fill:#fce4ec,stroke:#c62828
    style NS fill:#f5f5f5,stroke:#424242
    style WL fill:#e3f2fd,stroke:#1565c0
    style NET fill:#e8f5e9,stroke:#2e7d32
    style CFG fill:#fff3e0,stroke:#e65100
    style STR fill:#f3e5f5,stroke:#6a1b9a
    style ESO_NS fill:#e0f2f1,stroke:#00695c
```

---

## 4. Terraform Three-Layer Architecture

Infrastructure split into three workspaces with different lifecycles and costs. `bootstrap` runs once. `foundation` is long-lived and cheap. `platform` is ephemeral and expensive — created on deploy, destroyed on teardown. Outputs flow from foundation to platform via `terraform_remote_state`.

```mermaid
flowchart TB
    subgraph BOOT["bootstrap/ — Run once, local state"]
        B_S3["aws_s3_bucket<br/>rideshare-tf-state-*<br/><small>versioning enabled,<br/>prevent_destroy</small>"]
    end

    subgraph FOUND["foundation/ — Long-lived, ~$8/month at rest"]
        F_VPC["VPC<br/><small>10.0.0.0/16, 2 public subnets,<br/>IGW, 3 security groups</small>"]
        F_IAM["IAM Roles<br/><small>CI OIDC role (GitHub Actions),<br/>EKS cluster/node roles,<br/>9 Pod Identity workload roles,<br/>Glue job role</small>"]
        F_S3["S3 Buckets (11)<br/><small>bronze, silver, gold, checkpoints,<br/>frontend, logs, loki, tempo,<br/>build-assets, ai-chat, tf-state</small>"]
        F_ECR["ECR Repos (8)<br/><small>one per service, scan-on-push,<br/>keep last 3 images</small>"]
        F_SEC["Secrets Manager (10)<br/><small>rideshare/*<br/>random passwords via<br/>hashicorp/random</small>"]
        F_DNS["Route 53 + ACM<br/><small>hosted zone + wildcard cert<br/>ACM forced to us-east-1</small>"]
        F_CF["CloudFront<br/><small>SPA distribution,<br/>Origin Access Control → S3</small>"]
        F_GLUE["Glue Catalog<br/><small>bronze, silver, gold DBs</small>"]
        F_LAM["Lambda Functions (3)<br/><small>auth-deploy, ai-chat, rds-reset</small>"]
        F_DDB["DynamoDB + KMS<br/><small>visitor tables, encrypted</small>"]
    end

    subgraph PLAT["platform/ — Ephemeral, ~$0.31/hour"]
        P_EKS["EKS Cluster<br/><small>v1.35, API auth mode,<br/>public endpoint only</small>"]
        P_NG["Node Group<br/><small>1x t3.xlarge, AL2023,<br/>50GB gp3, IMDSv2</small>"]
        P_ADD["EKS Add-ons (5)<br/><small>vpc-cni, kube-proxy, coredns,<br/>ebs-csi, pod-identity-agent</small>"]
        P_RDS["RDS PostgreSQL<br/><small>db.t4g.micro, v16.6,<br/>encrypted, 7-day backups</small>"]
        P_HELM["Helm Releases (3)<br/><small>ALB Controller, ESO,<br/>kube-state-metrics</small>"]
        P_PI["Pod Identity Associations (9)<br/><small>simulation, bronze-ingestion,<br/>airflow, trino, hive-metastore,<br/>loki, tempo, ESO, ALB controller</small>"]
    end

    BOOT -->|"creates state bucket<br/>used by both layers below"| FOUND

    FOUND -->|"terraform_remote_state<br/><small>vpc_id, subnet_ids, sg_ids,<br/>role_arns, secret_ids</small>"| PLAT

    style BOOT fill:#e8eaf6,stroke:#283593
    style FOUND fill:#e8f5e9,stroke:#2e7d32
    style PLAT fill:#fff3e0,stroke:#e65100
```

---

## 5. Network Topology: Three Access Paths

Three different networking models depending on context. Docker Compose exposes services via host port mapping. Kind cluster uses Envoy Gateway with path-based routing. Production EKS uses an AWS ALB with subdomain-based routing.

```mermaid
flowchart TB
    subgraph DOCKER["Local: Docker Compose"]
        D_HOST["Host Machine<br/>localhost"]
        D_NET["Docker Bridge Network<br/><small>rideshare-network<br/>all services on same network</small>"]
        D_DNS["Service Discovery<br/><small>container name = DNS hostname<br/>kafka:29092, redis:6379,<br/>osrm:5000, minio:9000</small>"]
        D_PORTS["Host Port Mapping<br/><small>:8000 → simulation<br/>:5173 → control-panel<br/>:3001 → grafana<br/>:9092 → kafka<br/>:8082 → airflow<br/>:8084 → trino</small>"]

        D_HOST --> D_PORTS --> D_NET --> D_DNS
    end

    subgraph KIND["Local: Kind Cluster"]
        K_HOST["Host Machine<br/>localhost:80"]
        K_GW["Envoy Gateway<br/><small>GatewayClass: eg<br/>Gateway: rideshare-gateway</small>"]
        K_ROUTE["HTTPRoute Rules<br/><small>/api/* → simulation:8000<br/>/airflow/* → airflow:8082<br/>/grafana/* → grafana:3001<br/>/prometheus/* → prometheus:9090<br/>/trino/* → trino:8080<br/>/ → frontend:80</small>"]
        K_SVC["ClusterIP Services<br/><small>in-cluster DNS:<br/>simulation.default.svc:8000</small>"]

        K_HOST --> K_GW -->|"URLRewrite:<br/>strip path prefix"| K_ROUTE --> K_SVC
    end

    subgraph EKS["Production: AWS EKS"]
        P_DNS["Route 53<br/><small>*.ridesharing.portfolio<br/>.andresbrocco.com<br/>wildcard ALIAS → ALB</small>"]
        P_ALB["AWS ALB<br/><small>IngressGroup: rideshare<br/>(single ALB for all services)<br/>HTTPS :443 with ACM cert<br/>target-type: ip</small>"]
        P_ING["6 Ingress Resources<br/><small>api.* → simulation:8000<br/>control-panel.* → frontend:80<br/>grafana.* → grafana:3001<br/>airflow.* → airflow:8082<br/>trino.* → trino:8080<br/>prometheus.* → prometheus:9090</small>"]
        P_SVC["ClusterIP Services<br/><small>VPC CNI: real pod IPs<br/>simulation.rideshare-prod.svc:8000</small>"]

        P_DNS --> P_ALB --> P_ING --> P_SVC
    end

    style DOCKER fill:#e3f2fd,stroke:#1565c0
    style KIND fill:#f3e5f5,stroke:#6a1b9a
    style EKS fill:#e8f5e9,stroke:#2e7d32
```

---

## 6. CI/CD Pipeline Flow

The full path from code push to production deployment. Automated workflows trigger on push/CI success. Manual workflows handle platform lifecycle (deploy, teardown, reset). The `deploy` branch bridges Terraform-provisioned infrastructure with ArgoCD-managed workloads.

```mermaid
flowchart TB
    PUSH(("Push to main"))

    subgraph CI["ci.yml — Automated on push/PR"]
        LINT["lint-and-typecheck<br/><small>pre-commit --all-files<br/>ruff, mypy ×7, black, TFLint,<br/>hadolint, shellcheck, actionlint,<br/>gitleaks, checkov, kubeconform</small>"]
        TEST["unit-tests<br/><small>pytest: simulation,<br/>stream-processor</small>"]
        FE["frontend-build<br/><small>npm run build</small>"]
        API["api-contract<br/><small>OpenAPI export →<br/>TypeScript type parity</small>"]

        LINT --> TEST
        LINT --> FE
        LINT --> API
    end

    subgraph AUTO["Automated on CI success"]
        BUILD["build-images.yml<br/><small>path-filter per service →<br/>dynamic build matrix<br/>docker buildx → ECR<br/>tags: git-sha + latest<br/>layer cache in ECR</small>"]
        LAND["deploy-landing-page.yml<br/><small>npm build → S3 sync<br/>→ CloudFront invalidation<br/>(only if control-panel changed)</small>"]
    end

    subgraph LAMBDA["Automated on path change"]
        L_AUTH["deploy-lambda-auth<br/><small>services/auth-deploy/**</small>"]
        L_CHAT["deploy-lambda-chat<br/><small>services/ai-chat/**</small>"]
        L_RDS["deploy-lambda-rds-reset<br/><small>services/rds-reset/**</small>"]
    end

    subgraph MANUAL["Manual Triggers — workflow_dispatch"]
        DEPLOY["deploy-platform.yml<br/><small>terraform apply (EKS, RDS, ALB, ESO)<br/>→ resolve YAML placeholders<br/>→ git push --force deploy<br/>→ install ArgoCD<br/>→ 5-phase convergence wait</small>"]
        TEAR["teardown-platform.yml<br/><small>graceful simulation shutdown<br/>→ delete Route 53 record<br/>→ terraform destroy<br/>→ clean orphaned EBS</small>"]
        RESET["reset-platform.yml<br/><small>suspend ArgoCD auto-sync<br/>→ wipe Kafka/S3/RDS/Redis<br/>→ restore ArgoCD<br/>(keeps EKS cluster intact)</small>"]
    end

    ARGO["ArgoCD<br/><small>polls deploy branch<br/>kustomize build → apply<br/>self-heal within 3 min</small>"]

    PUSH --> CI
    CI -->|"success"| BUILD
    CI -->|"control-panel/**"| LAND
    PUSH -->|"Lambda paths"| LAMBDA
    BUILD -.->|"images in ECR"| DEPLOY
    DEPLOY -->|"force-push<br/>deploy branch"| ARGO

    style CI fill:#e3f2fd,stroke:#1565c0
    style AUTO fill:#e8f5e9,stroke:#2e7d32
    style LAMBDA fill:#f3e5f5,stroke:#6a1b9a
    style MANUAL fill:#fff3e0,stroke:#e65100
```

---

## 7. IAM & Authentication Chains

Two distinct trust chains: GitHub Actions authenticates via OIDC federation (short-lived tokens, no stored credentials). EKS workloads authenticate via Pod Identity (the Pod Identity Agent DaemonSet intercepts SDK requests and vends temporary STS credentials).

```mermaid
flowchart LR
    subgraph GH["GitHub Actions — CI/CD Authentication"]
        RUNNER["GitHub Actions Runner<br/><small>runs workflow job</small>"]
        OIDC["GitHub OIDC Token<br/><small>signed JWT proving:<br/>repo, branch, workflow</small>"]
        STS_CI["AWS STS<br/><small>AssumeRoleWith<br/>WebIdentity</small>"]
        ROLE_CI["rideshare-github-actions<br/><small>IAM Role<br/>trust: token.actions.<br/>githubusercontent.com<br/>condition: main branch only</small>"]
        PERMS_CI["Permissions<br/><small>ECR push, EKS deploy,<br/>Terraform state, S3, RDS,<br/>Secrets Manager, Route 53,<br/>CloudFront, Lambda...</small>"]

        RUNNER -->|"1. request token"| OIDC
        OIDC -->|"2. present to AWS"| STS_CI
        STS_CI -->|"3. validate + assume"| ROLE_CI
        ROLE_CI -->|"4. temporary creds"| PERMS_CI
    end

    subgraph K8S["EKS — Workload Authentication"]
        POD["Pod<br/><small>ServiceAccount: simulation<br/>namespace: rideshare-prod</small>"]
        PIA["Pod Identity Agent<br/><small>DaemonSet on every node<br/>intercepts credential requests</small>"]
        STS_POD["AWS STS<br/><small>AssumeRole</small>"]
        ASSOC["Pod Identity Association<br/><small>Terraform resource binding:<br/>(cluster, namespace, SA) → role</small>"]
        ROLE_POD["rideshare-simulation<br/><small>IAM Role<br/>trust: pods.eks.amazonaws.com<br/>actions: AssumeRole, TagSession</small>"]
        PERMS_POD["Scoped Permissions<br/><small>e.g. simulation:<br/>S3 checkpoints R/W only<br/><br/>e.g. loki:<br/>S3 loki bucket R/W only</small>"]

        POD -->|"1. AWS SDK call"| PIA
        PIA -->|"2. lookup association"| ASSOC
        ASSOC -->|"3. resolve role"| STS_POD
        STS_POD -->|"4. assume role"| ROLE_POD
        ROLE_POD -->|"5. temporary creds"| PERMS_POD
    end

    style GH fill:#e3f2fd,stroke:#1565c0
    style K8S fill:#e8f5e9,stroke:#2e7d32
```

---

## 8. Kustomize Overlay Composition

A template-free layering system. Base manifests define all resources with local-dev defaults. The shared `aws-production` component patches images, endpoints, storage, and adds production-only resources. Two mutually exclusive overlays select the Trino catalog backend (Hive Metastore vs AWS Glue).

```mermaid
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

---

## 9. ArgoCD GitOps Reconciliation Loop

ArgoCD continuously reconciles the `deploy` branch with live cluster state. The deploy workflow is the only writer to the `deploy` branch. Self-heal reverts manual `kubectl` changes. Prune deletes resources removed from Git. Replica counts are excluded from drift detection to allow manual scaling.

```mermaid
flowchart LR
    subgraph WF["deploy-platform.yml"]
        CH["Checkout main"]
        RES["Resolve placeholders<br/><small>sed: account-id, image-tag,<br/>rds-endpoint, acm-cert-arn,<br/>alb-sg-id, dbt-runner</small>"]
        PKG["Package projects<br/><small>dbt-project.tar.gz<br/>ge-project.tar.gz</small>"]
        FP["git push --force<br/>origin deploy<br/><small>commit: deploy: resolve<br/>production values [skip ci]</small>"]

        CH --> RES --> PKG --> FP
    end

    subgraph ARGO["ArgoCD — in-cluster controller"]
        POLL["Poll deploy branch<br/><small>~3 min interval</small>"]
        KBUILD["Kustomize build<br/><small>base + component + overlay<br/>→ resolved manifests</small>"]
        DIFF["Compute diff<br/><small>Git desired state<br/>vs cluster live state</small>"]
        SYNC["kubectl apply<br/><small>namespace: rideshare-prod<br/>CreateNamespace=true</small>"]
        RETRY["Retry on failure<br/><small>5 attempts, exponential backoff<br/>5s → 10s → 20s → 40s → 80s<br/>max 3 min</small>"]
    end

    subgraph CLUSTER["EKS Cluster — rideshare-prod"]
        LIVE["Live Resources<br/><small>Deployments, Services,<br/>ConfigMaps, Secrets...</small>"]
        HEAL["Self-Heal<br/><small>manual kubectl edit detected<br/>→ reverted to Git state</small>"]
        PRUNE["Prune<br/><small>resource deleted from Git<br/>→ deleted from cluster</small>"]
        IGNORE["ignoreDifferences<br/><small>Deployment/StatefulSet<br/>spec.replicas excluded<br/>(allows manual scaling)</small>"]
    end

    FP -->|"branch updated"| POLL
    POLL --> KBUILD --> DIFF
    DIFF -->|"changes found"| SYNC --> LIVE
    SYNC -->|"failure"| RETRY --> SYNC
    LIVE -->|"drift detected"| HEAL --> DIFF
    DIFF -->|"resource missing"| PRUNE
    IGNORE -.->|"skipped in<br/>diff check"| DIFF

    style WF fill:#e3f2fd,stroke:#1565c0
    style ARGO fill:#fff3e0,stroke:#e65100
    style CLUSTER fill:#e8f5e9,stroke:#2e7d32
```

---

## 10. EKS Cluster Bootstrap Sequence

Strict ordering constraints during cluster creation. Each step unlocks the next. vpc-cni must exist before nodes can reach `Ready`. The ALB controller's mutating webhook must be ready before coredns/ebs-csi addons install (otherwise the webhook rejects their pods). ArgoCD is installed last, after all cluster infrastructure is stable.

```mermaid
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
