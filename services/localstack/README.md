# LocalStack - AWS Service Emulation

> LocalStack 4.12.0 (`localstack/localstack:4.12.0`)

## Purpose

LocalStack provides local AWS cloud service emulation for development and testing.

**Files in this directory:**

| File | Purpose |
|------|---------|
| `test-services.sh` | Validation script that tests Secrets Manager, SNS, and SQS |
| `README.md` | This file |
| `CONTEXT.md` | Architecture context for AI agents |

## Enabled Services

- **Secrets Manager** - Store and retrieve secrets
- **SNS** - Simple Notification Service for pub/sub messaging
- **SQS** - Simple Queue Service for message queuing

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Endpoint | http://localhost:4566 | Unified API endpoint |
| Service Range | 4510-4559 | Individual service API ports |
| Memory | 512MB | Container memory limit |
| Persistence | Disabled (`PERSISTENCE=0`) | Data is ephemeral |
| Region | `us-east-1` | Default AWS region |
| Credentials | `test`/`test` | Dummy credentials (any value works) |
| Profile | `data-pipeline` | Docker Compose profile |

## Quick Start

```bash
# Start LocalStack
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d localstack

# Check health
curl http://localhost:4566/_localstack/health
```

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
./services/localstack/test-services.sh
```

## Troubleshooting

### LocalStack not starting

Check container logs:
```bash
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline logs localstack
```

### Health check failing

Verify the container is running and the endpoint is reachable:
```bash
curl http://localhost:4566/_localstack/health
```

The response should list each enabled service with `"running"` status.

### Services missing from health response

Ensure the `SERVICES` environment variable in Docker Compose includes the required services (`secretsmanager,sns,sqs`).

### State lost after restart

This is expected behavior. `PERSISTENCE=0` means all data is ephemeral. Secrets, topics, and queues must be recreated after each container restart.

### test-services.sh fails

The test script requires the AWS CLI to be installed locally on the host machine. Install it via:
```bash
brew install awscli        # macOS
pip install awscli          # pip
```

## References

- [CONTEXT.md](CONTEXT.md) - Architecture and design decisions
- [LocalStack Documentation](https://docs.localstack.cloud/overview/)
- [LocalStack AWS Service Coverage](https://docs.localstack.cloud/user-guide/aws/feature-coverage/)
- [infrastructure/docker/compose.yml](../../infrastructure/docker/compose.yml) - Docker service definitions
