#!/bin/bash
set -e

echo "Testing core service manifests..."

# Test 1: Apply manifests
echo "Test 1: Applying core service manifests"
kubectl apply -f infrastructure/kubernetes/manifests/kafka.yaml
kubectl apply -f infrastructure/kubernetes/manifests/schema-registry.yaml
kubectl apply -f infrastructure/kubernetes/manifests/redis.yaml
kubectl apply -f infrastructure/kubernetes/manifests/osrm.yaml
kubectl apply -f infrastructure/kubernetes/manifests/simulation.yaml
kubectl apply -f infrastructure/kubernetes/manifests/stream-processor.yaml
kubectl apply -f infrastructure/kubernetes/manifests/frontend.yaml

# Test 2: Wait for pods to be Running
echo "Test 2: Waiting for pods to reach Running state (max 5 minutes)"
kubectl wait --for=condition=Ready pod -l app=kafka --timeout=300s
kubectl wait --for=condition=Ready pod -l app=schema-registry --timeout=300s
kubectl wait --for=condition=Ready pod -l app=redis --timeout=300s
kubectl wait --for=condition=Ready pod -l app=osrm --timeout=300s
kubectl wait --for=condition=Ready pod -l app=simulation --timeout=300s
kubectl wait --for=condition=Ready pod -l app=stream-processor --timeout=300s
kubectl wait --for=condition=Ready pod -l app=frontend --timeout=300s

# Test 3: Verify services exist and are accessible
echo "Test 3: Verifying services are created and accessible"
# Kafka uses headless service (clusterIP: None) for StatefulSet DNS
kubectl get svc kafka -o jsonpath='{.spec.clusterIP}' | grep -E '^(None|[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)$'
kubectl get svc schema-registry -o jsonpath='{.spec.clusterIP}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
kubectl get svc redis -o jsonpath='{.spec.clusterIP}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
kubectl get svc osrm -o jsonpath='{.spec.clusterIP}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
kubectl get svc simulation -o jsonpath='{.spec.clusterIP}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
kubectl get svc stream-processor -o jsonpath='{.spec.clusterIP}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
kubectl get svc frontend -o jsonpath='{.spec.clusterIP}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'

echo "All core service tests passed!"
