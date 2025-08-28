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
COPY simulation/pyproject.toml simulation/pyproject.toml

# Install dependencies including dev
RUN cd simulation && uv pip install --system -e ".[dev]"

# Create directories for mounted volumes
RUN mkdir -p simulation/src data && chown -R simuser:simuser /app

USER simuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose API port
EXPOSE 8000

# Source mounted via docker-compose volume
CMD ["python", "-m", "src.main"]

# Production stage - optimized for size
FROM base AS production

COPY simulation/pyproject.toml simulation/pyproject.toml

RUN cd simulation && uv pip install --system .

COPY simulation/src /app/src
COPY data/sao-paulo /app/data/sao-paulo

RUN mkdir -p /app/data/db && chown -R simuser:simuser /app

USER simuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Health check for container orchestration
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "src.main"]
