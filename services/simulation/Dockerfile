# Base stage - common dependencies
FROM python:3.13-slim AS base

# Install system dependencies for confluent-kafka, shapely, and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    librdkafka-dev \
    libgeos-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 simuser

WORKDIR /app

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

# Development stage - source code mounted as volume
FROM base AS development

# Copy dependency files first for layer caching
COPY pyproject.toml pyproject.toml

# Create src directory placeholder for editable install
RUN mkdir -p src

# Install dependencies including dev (editable install for development)
RUN uv pip install --system -e ".[dev]"

# Create directories for mounted volumes
RUN mkdir -p data db && chown -R simuser:simuser /app

USER simuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

# Expose API port
EXPOSE 8000

# Source mounted via docker-compose volume
WORKDIR /app/src
CMD ["python", "main.py"]

# Production stage - optimized for size
FROM base AS production

COPY pyproject.toml pyproject.toml
COPY src /app/src
COPY data /app/data
COPY schemas /app/schemas

RUN uv pip install --system .

RUN mkdir -p /app/db && chown -R simuser:simuser /app

USER simuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

EXPOSE 8000

# Health check for container orchestration
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

WORKDIR /app/src
CMD ["python", "main.py"]
