FROM python:3.13-slim

WORKDIR /app

# Install curl for health checks (no gcc/librdkafka — this service doesn't use Kafka directly)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Run the performance controller
CMD ["python", "-m", "src.main"]
