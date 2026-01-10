# Production Overlay - AWS EKS

Kustomize overlay for production deployment on AWS EKS.

## Purpose

This overlay configures the rideshare simulation for production:
- Production-grade resource limits
- EBS persistent volumes for stateful services
- LoadBalancer services for external access
- Multiple replicas for high availability
- Production environment variables (secrets via AWS Secrets Manager)
- Resource quotas and network policies

## Prerequisites

- AWS CLI configured
- eksctl installed
- kubectl configured for EKS cluster
- Terraform infrastructure applied (Phase 9)

## Usage

```bash
# Ensure EKS cluster context is active
kubectl config current-context

# Apply production configuration
kubectl apply -k .

# Verify deployments
kubectl get pods -n rideshare-prod
kubectl get svc -n rideshare-prod
```

## Resource Limits (Production)

- Simulation: 2 CPU, 4Gi memory (2 replicas)
- Stream Processor: 1 CPU, 2Gi memory (2 replicas)
- Frontend: 500m CPU, 1Gi memory (2 replicas)
- Kafka: 2 CPU, 4Gi memory (3 replicas)
- Redis: 500m CPU, 2Gi memory (2 replicas with Redis Cluster)
- Spark Master: 2 CPU, 4Gi memory
- Spark Worker: 2 CPU, 8Gi memory (3 replicas)

## High Availability

- All stateless services have 2+ replicas
- Kafka uses 3 replicas for quorum
- Redis uses Redis Cluster mode
- Persistent volumes use EBS with snapshots
