# LocalStack - AWS Service Emulation

LocalStack provides local AWS cloud service emulation for development and testing.

## Enabled Services

- **Secrets Manager** - Store and retrieve secrets
- **SNS** - Simple Notification Service for pub/sub messaging
- **SQS** - Simple Queue Service for message queuing

## Quick Start

```bash
# Start LocalStack
docker compose up -d localstack

# Check health
curl http://localhost:4566/_localstack/health
```

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Endpoint | http://localhost:4566 | Unified API endpoint |
| Memory | 512MB | Container memory limit |
| Persistence | Disabled | Data is ephemeral |

## AWS CLI Usage

Configure dummy credentials:

```bash
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="us-east-1"
```

All commands require `--endpoint-url`:

```bash
# Secrets Manager
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
    --name my-secret --secret-string "secret-value"

# SNS
aws --endpoint-url=http://localhost:4566 sns create-topic --name my-topic

# SQS
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name my-queue
```

## Python boto3 Usage

```python
import boto3

# Configure client to use LocalStack
client = boto3.client(
    'secretsmanager',
    endpoint_url='http://localhost:4566',
    aws_access_key_id='test',
    aws_secret_access_key='test',
    region_name='us-east-1'
)

# Use normally
client.create_secret(Name='my-secret', SecretString='my-value')
```

## Testing

Run the test script to verify all services:

```bash
./data-platform/localstack/test-services.sh
```
