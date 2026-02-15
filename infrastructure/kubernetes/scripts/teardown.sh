#!/bin/bash
set -e

CLUSTER_NAME="${CLUSTER_NAME:-rideshare-local}"
PRESERVE_DATA=false
BACKUP_DIR="${BACKUP_DIR:-/tmp}"

# Parse command line arguments
for arg in "$@"; do
  case $arg in
    --preserve-data)
      PRESERVE_DATA=true
      shift
      ;;
    --backup-dir=*)
      BACKUP_DIR="${arg#*=}"
      shift
      ;;
    *)
      # Unknown option
      ;;
  esac
done

echo "============================================"
echo "Tearing Down Kubernetes Cluster"
echo "============================================"
echo "Cluster: $CLUSTER_NAME"
echo "Preserve data: $PRESERVE_DATA"
echo ""

# Check if cluster exists
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  echo "Cluster '$CLUSTER_NAME' does not exist. Nothing to teardown."
  exit 0
fi

# Preserve data if requested
if [ "$PRESERVE_DATA" = true ]; then
  echo "Backing up persistent data..."
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  BACKUP_FILE="$BACKUP_DIR/rideshare-k8s-backup-$TIMESTAMP.tar.gz"

  # Create backup directory
  TEMP_BACKUP_DIR=$(mktemp -d)
  trap 'rm -rf $TEMP_BACKUP_DIR' EXIT

  echo "Exporting PVC data..."

  # Backup MinIO data
  MINIO_POD=$(kubectl get pods -l app=minio --no-headers 2>/dev/null | awk '{print $1}' | head -n 1 || true)
  if [ -n "$MINIO_POD" ]; then
    echo "  Backing up MinIO data..."
    mkdir -p "$TEMP_BACKUP_DIR/minio"
    kubectl exec -i "$MINIO_POD" -- tar czf - /data 2>/dev/null > "$TEMP_BACKUP_DIR/minio/data.tar.gz" || echo "Warning: MinIO backup failed"
  fi

  # Backup Kafka data
  KAFKA_POD=$(kubectl get pods -l app=kafka --no-headers 2>/dev/null | awk '{print $1}' | head -n 1 || true)
  if [ -n "$KAFKA_POD" ]; then
    echo "  Backing up Kafka data..."
    mkdir -p "$TEMP_BACKUP_DIR/kafka"
    kubectl exec -i "$KAFKA_POD" -- tar czf - /var/lib/kafka/data 2>/dev/null > "$TEMP_BACKUP_DIR/kafka/data.tar.gz" || echo "Warning: Kafka backup failed"
  fi

  # Backup Airflow Postgres data
  AIRFLOW_PG_POD=$(kubectl get pods -l app=airflow-postgres --no-headers 2>/dev/null | awk '{print $1}' | head -n 1 || true)
  if [ -n "$AIRFLOW_PG_POD" ]; then
    echo "  Backing up Airflow Postgres data..."
    mkdir -p "$TEMP_BACKUP_DIR/airflow-postgres"
    kubectl exec -i "$AIRFLOW_PG_POD" -- tar czf - /var/lib/postgresql/data 2>/dev/null > "$TEMP_BACKUP_DIR/airflow-postgres/data.tar.gz" || echo "Warning: Airflow Postgres backup failed"
  fi

  # Backup Superset Postgres data
  SUPERSET_PG_POD=$(kubectl get pods -l app=superset-postgres --no-headers 2>/dev/null | awk '{print $1}' | head -n 1 || true)
  if [ -n "$SUPERSET_PG_POD" ]; then
    echo "  Backing up Superset Postgres data..."
    mkdir -p "$TEMP_BACKUP_DIR/superset-postgres"
    kubectl exec -i "$SUPERSET_PG_POD" -- tar czf - /var/lib/postgresql/data 2>/dev/null > "$TEMP_BACKUP_DIR/superset-postgres/data.tar.gz" || echo "Warning: Superset Postgres backup failed"
  fi

  # Export all manifests
  echo "  Exporting Kubernetes manifests..."
  mkdir -p "$TEMP_BACKUP_DIR/manifests"
  kubectl get all -o yaml > "$TEMP_BACKUP_DIR/manifests/all.yaml" 2>/dev/null || true
  kubectl get pvc -o yaml > "$TEMP_BACKUP_DIR/manifests/pvc.yaml" 2>/dev/null || true
  kubectl get configmap -o yaml > "$TEMP_BACKUP_DIR/manifests/configmap.yaml" 2>/dev/null || true

  # Create tarball
  echo "Creating backup archive: $BACKUP_FILE"
  tar czf "$BACKUP_FILE" -C "$TEMP_BACKUP_DIR" .

  echo "✓ Backup created: $BACKUP_FILE"
  echo ""
fi

# Delete the cluster
echo "Deleting Kind cluster: $CLUSTER_NAME"
kind delete cluster --name "$CLUSTER_NAME"

echo ""
echo "============================================"
echo "✓ Cluster teardown complete!"
echo "============================================"

if [ "$PRESERVE_DATA" = true ]; then
  echo ""
  echo "Backup location: $BACKUP_FILE"
  echo ""
  echo "To restore data:"
  echo "  1. Create new cluster: ./infrastructure/kubernetes/scripts/create-cluster.sh"
  echo "  2. Deploy services: ./infrastructure/kubernetes/scripts/deploy-services.sh"
  echo "  3. Restore from backup: tar xzf $BACKUP_FILE"
fi
