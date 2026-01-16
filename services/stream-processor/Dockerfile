FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for confluent-kafka and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    librdkafka-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Run the stream processor
CMD ["python", "-m", "src.main"]
