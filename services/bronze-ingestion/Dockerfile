FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for confluent-kafka (librdkafka) and healthcheck (curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    librdkafka-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Expose health endpoint port
EXPOSE 8080

# Set Python path so "from src.module import ..." works
ENV PYTHONPATH=/app

# Health check using the HTTP health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "src.main"]
