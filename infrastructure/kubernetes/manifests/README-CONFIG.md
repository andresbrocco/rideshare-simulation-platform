# ConfigMaps and Secrets Usage Guide

## Overview

This directory contains Kubernetes ConfigMaps and Secrets that centralize configuration for all services in the rideshare platform.

## Files

- **configmap-core.yaml** - Core services configuration (Kafka, Redis, OSRM, Simulation, Stream Processor, OTel)
- **configmap-data-pipeline.yaml** - Data pipeline configuration (MinIO, PostgreSQL, Spark, Hive Metastore, Trino, LocalStack)
- **secret-credentials.yaml** - Database passwords and service credentials
- **secret-api-keys.yaml** - API keys and application secrets

## Applying Configuration

```bash
# Apply all ConfigMaps and Secrets
kubectl apply -f infrastructure/kubernetes/manifests/configmap-core.yaml
kubectl apply -f infrastructure/kubernetes/manifests/configmap-data-pipeline.yaml
kubectl apply -f infrastructure/kubernetes/manifests/secret-credentials.yaml
kubectl apply -f infrastructure/kubernetes/manifests/secret-api-keys.yaml
```

## Using ConfigMaps in Pods

### Option 1: Individual Environment Variables

```yaml
env:
- name: KAFKA_BOOTSTRAP_SERVERS
  valueFrom:
    configMapKeyRef:
      name: core-config
      key: KAFKA_BOOTSTRAP_SERVERS
- name: REDIS_HOST
  valueFrom:
    configMapKeyRef:
      name: core-config
      key: REDIS_HOST
```

### Option 2: All Keys as Environment Variables

```yaml
envFrom:
- configMapRef:
    name: core-config
```

## Using Secrets in Pods

### Individual Secret Values

```yaml
env:
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: api-keys
      key: API_KEY
- name: MINIO_ROOT_PASSWORD
  valueFrom:
    secretKeyRef:
      name: app-credentials
      key: MINIO_ROOT_PASSWORD
```

### All Secret Keys as Environment Variables

```yaml
envFrom:
- secretRef:
    name: app-credentials
```

## Configuration Categories

### Core Config (core-config)
- Kafka connection strings and settings
- Redis connection settings
- OSRM routing service URL
- Simulation parameters
- Stream processor configuration
- API and logging settings
- CORS origins
- OpenTelemetry configuration (OTLP endpoint, deployment environment, log format)

### Data Pipeline Config (data-pipeline-config)
- MinIO endpoint and settings
- PostgreSQL (Airflow) connection details
- PostgreSQL (Hive Metastore) connection details
- Hive Metastore URI
- Trino host and port
- Spark settings
- LocalStack AWS emulator endpoint

### App Credentials (app-credentials)
- Redis passwords
- MinIO root user/password and access keys
- PostgreSQL passwords (Airflow, Hive Metastore)
- Kafka SASL credentials (for production)

### API Keys (api-keys)
- Simulation API key
- Airflow Fernet key

## Production Considerations

**IMPORTANT**: The current secrets use development defaults. For production:

1. **Generate strong credentials**:
   ```bash
   # Example: Generate random password
   openssl rand -base64 32

   # Example: Generate Airflow Fernet key
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **Use Kubernetes Secrets management**:
   - External secrets operators (e.g., External Secrets Operator)
   - Cloud provider secret stores (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault)
   - HashiCorp Vault integration

3. **Enable RBAC**:
   - Restrict secret access to specific service accounts
   - Use pod security policies

4. **Update sensitive values**:
   - MINIO_ROOT_PASSWORD
   - AIRFLOW_POSTGRES_PASSWORD
   - POSTGRES_METASTORE_PASSWORD
   - API_KEY
   - AIRFLOW_FERNET_KEY
   - KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD (if using SASL)
   - REDIS_PASSWORD (recommended for production)

5. **Enable encryption at rest** for Secrets in etcd.

## Testing

Run the test script to verify ConfigMaps and Secrets are correctly configured:

```bash
./infrastructure/kubernetes/tests/test_config_secrets.sh
```

This validates:
- ConfigMaps apply successfully
- Secrets apply successfully
- ConfigMaps are readable
- Secrets are Opaque type with data
- Pods can read environment variables from ConfigMaps and Secrets

## Verifying Configuration

```bash
# View ConfigMap (values visible)
kubectl get configmap core-config -o yaml

# View Secret (values base64 encoded)
kubectl get secret app-credentials -o yaml

# Decode a secret value
kubectl get secret api-keys -o jsonpath='{.data.API_KEY}' | base64 -d
```
