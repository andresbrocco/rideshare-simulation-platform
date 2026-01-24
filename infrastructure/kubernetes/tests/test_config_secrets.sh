#!/bin/bash
set -e

echo "Testing ConfigMaps and Secrets..."

# Test 1: Apply ConfigMaps
echo "Test 1: Applying ConfigMaps"
kubectl apply -f infrastructure/kubernetes/manifests/configmap-core.yaml
kubectl apply -f infrastructure/kubernetes/manifests/configmap-data-platform.yaml

# Test 2: Apply Secrets
echo "Test 2: Applying Secrets"
kubectl apply -f infrastructure/kubernetes/manifests/secret-credentials.yaml
kubectl apply -f infrastructure/kubernetes/manifests/secret-api-keys.yaml

# Test 3: Verify ConfigMaps exist
echo "Test 3: Verifying ConfigMaps exist"
kubectl get configmap core-config -o yaml
kubectl get configmap data-platform-config -o yaml

# Test 4: Verify Secrets exist (values should be opaque)
echo "Test 4: Verifying Secrets exist with opaque data"
kubectl get secret app-credentials -o jsonpath='{.type}' | grep -q "Opaque"
kubectl get secret api-keys -o jsonpath='{.type}' | grep -q "Opaque"

# Verify secret data fields exist but don't display values
kubectl get secret app-credentials -o jsonpath='{.data}' | grep -q "."
kubectl get secret api-keys -o jsonpath='{.data}' | grep -q "."

# Test 5: Verify pod can read environment variables from ConfigMap
echo "Test 5: Deploying test pod to verify ConfigMap/Secret injection"

# Create test pod that uses ConfigMaps and Secrets
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: config-test-pod
spec:
  containers:
  - name: test
    image: busybox:latest
    command: ['sh', '-c', 'echo "KAFKA_BOOTSTRAP_SERVERS=\$KAFKA_BOOTSTRAP_SERVERS" && echo "REDIS_HOST=\$REDIS_HOST" && echo "API_KEY=\$API_KEY" && sleep 3600']
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
    - name: API_KEY
      valueFrom:
        secretKeyRef:
          name: api-keys
          key: API_KEY
  restartPolicy: Never
EOF

# Wait for pod to be running
kubectl wait --for=condition=Ready pod/config-test-pod --timeout=60s

# Verify environment variables are set
echo "Verifying KAFKA_BOOTSTRAP_SERVERS is set:"
kubectl exec config-test-pod -- sh -c 'echo $KAFKA_BOOTSTRAP_SERVERS' | grep -q "kafka"

echo "Verifying REDIS_HOST is set:"
kubectl exec config-test-pod -- sh -c 'echo $REDIS_HOST' | grep -q "redis"

echo "Verifying API_KEY is set from secret:"
kubectl exec config-test-pod -- sh -c 'test -n "$API_KEY"'

# Cleanup test pod
kubectl delete pod config-test-pod

echo "All ConfigMap and Secret tests passed!"
