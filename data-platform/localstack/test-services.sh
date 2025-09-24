#!/bin/bash
# Test LocalStack AWS service emulation

set -e

ENDPOINT="http://localhost:4566"
AWS_REGION="us-east-1"

echo "Testing LocalStack services..."

export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="us-east-1"

# Test Secrets Manager
echo "1. Testing Secrets Manager..."
aws --endpoint-url=$ENDPOINT secretsmanager create-secret \
    --name test-db-password \
    --secret-string "my-secret-password-123" \
    --region $AWS_REGION

aws --endpoint-url=$ENDPOINT secretsmanager get-secret-value \
    --secret-id test-db-password \
    --region $AWS_REGION

# Test SNS
echo "2. Testing SNS..."
TOPIC_ARN=$(aws --endpoint-url=$ENDPOINT sns create-topic \
    --name test-notifications \
    --region $AWS_REGION \
    --query 'TopicArn' \
    --output text)

aws --endpoint-url=$ENDPOINT sns publish \
    --topic-arn $TOPIC_ARN \
    --message "Test notification from LocalStack" \
    --region $AWS_REGION

# Test SQS
echo "3. Testing SQS..."
QUEUE_URL=$(aws --endpoint-url=$ENDPOINT sqs create-queue \
    --queue-name test-queue \
    --region $AWS_REGION \
    --query 'QueueUrl' \
    --output text)

aws --endpoint-url=$ENDPOINT sqs send-message \
    --queue-url $QUEUE_URL \
    --message-body "Test message" \
    --region $AWS_REGION

aws --endpoint-url=$ENDPOINT sqs receive-message \
    --queue-url $QUEUE_URL \
    --region $AWS_REGION

echo "All LocalStack services working!"
