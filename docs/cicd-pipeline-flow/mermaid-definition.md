# CI/CD Pipeline Flow

The full path from code push to production deployment. Automated workflows trigger on push/CI success. Manual workflows handle platform lifecycle (deploy, teardown, reset). The `deploy` branch bridges Terraform-provisioned infrastructure with ArgoCD-managed workloads.

```mermaid
---
title: CI/CD Pipeline Flow
---
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
