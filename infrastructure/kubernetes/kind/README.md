# Kind Cluster Configuration

This directory contains the Kind (Kubernetes in Docker) cluster configuration for local development and testing of the rideshare simulation platform.

## Prerequisites

- **Docker Desktop** running with at least 10GB memory allocated
- **kind** v0.31.0+ installed
- **kubectl** v1.35.0+ installed
- Ports 80 and 443 available on localhost

### Installing Kind

```bash
# macOS (Homebrew)
brew install kind

# Linux
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.31.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Verify installation
kind --version
```

### Installing kubectl

```bash
# macOS (Homebrew)
brew install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/v1.35.0/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify installation
kubectl version --client
```

## Cluster Architecture

The cluster is configured with:

| Node | Role | Purpose |
|------|------|---------|
| rideshare-local-control-plane | control-plane | API server, scheduler, controller-manager |
| rideshare-local-worker | worker | General workloads |
| rideshare-local-worker2 | worker | General workloads |

### Resource Allocation

Total Docker memory: 10GB
- Control plane: ~1GB
- Worker nodes: ~4.5GB each
- System overhead: ~1GB

Resource limits are enforced by Docker Desktop settings, not Kind configuration.

### Port Mappings

| Host Port | Container Port | Purpose |
|-----------|---------------|---------|
| 80 | 80 | HTTP Ingress |
| 443 | 443 | HTTPS Ingress |
| 30000 | 30000 | NodePort (optional) |
| 30001 | 30001 | NodePort (optional) |

## Usage

### Create Cluster

```bash
# From repository root
kind create cluster --config infrastructure/kubernetes/kind/cluster-config.yaml --name rideshare-local

# Verify cluster is running
kubectl cluster-info --context kind-rideshare-local

# Check nodes
kubectl get nodes
```

### Delete Cluster

```bash
kind delete cluster --name rideshare-local
```

### Switch kubectl Context

```bash
# List available contexts
kubectl config get-contexts

# Switch to Kind cluster
kubectl config use-context kind-rideshare-local
```

## Networking

- **Pod subnet**: 10.244.0.0/16
- **Service subnet**: 10.96.0.0/12
- **CNI**: kindnet (default)

## Storage

Kind provides a default `standard` StorageClass that uses hostPath provisioner for PersistentVolumeClaims.

```bash
# Verify storage class
kubectl get storageclass
```

## Local Registry Support

To use a local Docker registry with Kind, follow the official guide:
https://kind.sigs.k8s.io/docs/user/local-registry/

Basic setup:

```bash
# Create registry container
docker run -d --restart=always -p 5000:5000 --name kind-registry registry:2

# Connect registry to Kind network
docker network connect kind kind-registry

# Configure containerd to use the registry (run inside each node)
docker exec rideshare-local-control-plane bash -c \
  'mkdir -p /etc/containerd/certs.d/localhost:5000 && \
   echo "[host.\"http://kind-registry:5000\"]" > /etc/containerd/certs.d/localhost:5000/hosts.toml'
```

## Troubleshooting

### Cluster fails to create

1. Ensure Docker Desktop is running with sufficient resources
2. Check if ports 80/443 are already in use: `lsof -i :80`
3. Try deleting any existing cluster: `kind delete cluster --name rideshare-local`

### Nodes not ready

```bash
# Check node status
kubectl describe nodes

# Check system pods
kubectl get pods -n kube-system
```

### Port conflicts

If ports 80 or 443 are in use, stop the conflicting service or modify the `extraPortMappings` in `cluster-config.yaml`.
