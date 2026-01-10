# Local Overlay - Kind Cluster

Kustomize overlay for local development using Kind (Kubernetes in Docker).

## Purpose

This overlay configures the rideshare simulation for local development:
- Small resource limits suitable for laptops
- Local storage using hostPath
- NodePort services for easy access
- Single replicas for most services
- Development environment variables

## Prerequisites

- Docker installed
- Kind installed (`brew install kind`)
- kubectl installed

## Usage

```bash
# Create Kind cluster (if not exists)
kind create cluster --name rideshare-local

# Apply local configuration
kubectl apply -k .

# Port forward to access services
kubectl port-forward -n rideshare-local svc/frontend 3000:3000
kubectl port-forward -n rideshare-local svc/simulation 8000:8000
```

## Resource Limits (Local)

- Simulation: 500m CPU, 1Gi memory
- Stream Processor: 200m CPU, 512Mi memory
- Frontend: 100m CPU, 256Mi memory
- Kafka: 500m CPU, 1Gi memory
- Redis: 100m CPU, 512Mi memory
- Spark Master: 500m CPU, 1Gi memory
- Spark Worker: 500m CPU, 2Gi memory (1 replica)
