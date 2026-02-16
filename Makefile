# Makefile for rideshare-simulation-platform CI pipeline
# Mirrors GitHub Actions workflows for local execution
# IMPORTANT: This file uses TABS for indentation, not spaces

.PHONY: ci lint test build help clean venvs install-deps lint-python lint-frontend lint-terraform test-unit test-integration test-fast test-coverage build-frontend

# Default target
.DEFAULT_GOAL := help

# Configuration
COMPOSE_FILE := infrastructure/docker/compose.yml
PYTHON := ./venv/bin/python3
PIP := ./venv/bin/pip
PYTEST := ./venv/bin/pytest
PRE_COMMIT := pre-commit

# Service paths
SIM_DIR := services/simulation
STREAM_DIR := services/stream-processor
FRONTEND_DIR := services/frontend
DBT_DIR := tools/dbt
AIRFLOW_DIR := services/airflow
GX_DIR := tools/great-expectations
LAKEHOUSE_DIR := schemas/lakehouse

##@ Main Targets

ci: lint test build	## Run full CI pipeline (lint + test + build)
	@echo "✅ CI pipeline completed successfully"

lint: install-deps lint-python lint-frontend lint-terraform	## Run all linting and type checking
	@echo "✅ All linting and type checking passed"

test: test-unit	## Run test suite (unit tests)
	@echo "✅ All tests passed"

build: build-frontend	## Run build steps
	@echo "✅ Build completed"

##@ Installation

install-deps: venvs	## Install all dependencies (Python and Node.js)
	@echo "Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm ci
	@echo "✅ All dependencies installed"

venvs:	## Create virtual environments and install Python dependencies
	@echo "Creating virtual environments for all services..."
	@# simulation - full dev dependencies for type stubs
	python3 -m venv $(SIM_DIR)/venv
	$(SIM_DIR)/venv/bin/pip install --quiet -e $(SIM_DIR)/[dev]
	$(SIM_DIR)/venv/bin/pip install --quiet boto3-stubs[essential]
	@# stream-processor - install with opentelemetry packages
	python3 -m venv $(STREAM_DIR)/venv
	$(STREAM_DIR)/venv/bin/pip install --quiet -e $(STREAM_DIR)/[dev]
	@# dbt - install with pyspark and pyhive for type checking
	python3 -m venv $(DBT_DIR)/venv
	$(DBT_DIR)/venv/bin/pip install --quiet mypy pyspark pyhive
	@# airflow - install with runtime dependencies for type checking
	python3 -m venv $(AIRFLOW_DIR)/venv
	$(AIRFLOW_DIR)/venv/bin/pip install --quiet mypy types-requests duckdb apache-airflow deltalake
	@# great-expectations - install from requirements.txt (requires Python 3.13)
	python3.13 -m venv $(GX_DIR)/venv
	$(GX_DIR)/venv/bin/pip install --quiet mypy types-PyYAML
	$(GX_DIR)/venv/bin/pip install --quiet -r $(GX_DIR)/requirements.txt
	@# lakehouse - install with pyspark and delta-spark
	python3 -m venv $(LAKEHOUSE_DIR)/venv
	$(LAKEHOUSE_DIR)/venv/bin/pip install --quiet mypy pyspark delta-spark
	@# root venv for integration tests
	python3 -m venv venv
	$(PIP) install --quiet -e .
	@echo "✅ Virtual environments created and dependencies installed"

##@ Linting

lint-python:	## Run Python linting and type checking via pre-commit
	@echo "Running pre-commit on all files..."
	$(PRE_COMMIT) run --all-files

lint-frontend:	## Run frontend linting
	@echo "Running frontend linting..."
	cd $(FRONTEND_DIR) && npm run lint

lint-terraform:	## Run Terraform linting
	@echo "Initializing TFLint plugins..."
	tflint --init --config .tflint.hcl
	@echo "Running TFLint..."
	tflint --config .tflint.hcl

##@ Testing

test-unit:	## Run unit tests for all services
	@echo "Running simulation unit tests..."
	cd $(SIM_DIR) && ./venv/bin/pytest -v --tb=short
	@echo "Running stream-processor unit tests..."
	cd $(STREAM_DIR) && ./venv/bin/pytest -v --tb=short

test-fast:	## Run fast unit tests only (excludes slow tests)
	@echo "Running fast unit tests..."
	cd $(SIM_DIR) && ./venv/bin/pytest -m "unit and not slow" -v --tb=short

test-coverage:	## Run all tests with coverage report
	@echo "Running tests with coverage..."
	cd $(SIM_DIR) && ./venv/bin/pytest -v --cov=src --cov-report=term-missing --cov-report=html
	@echo "Coverage report generated in $(SIM_DIR)/htmlcov/"

test-integration:	## Run integration tests (requires Docker services)
	@echo "⚠️  Integration tests require Docker services to be running"
	@echo "Starting Docker services..."
	docker compose -f $(COMPOSE_FILE) --profile core --profile data-pipeline up -d
	@echo "Waiting for services to be ready (60s)..."
	@sleep 60
	@echo "Running integration tests..."
	$(PYTEST) tests/integration/ -v --tb=short --junitxml=test-results.xml
	@echo "Cleaning up Docker services..."
	docker compose -f $(COMPOSE_FILE) --profile core --profile data-pipeline down -v --remove-orphans

##@ Build

build-frontend:	## Build frontend production bundle
	@echo "Building frontend..."
	cd $(FRONTEND_DIR) && npm run build
	@echo "✅ Frontend build completed"

##@ Cleanup

clean:	## Remove all virtual environments, build artifacts, and caches
	@echo "Cleaning up..."
	rm -rf $(SIM_DIR)/venv
	rm -rf $(STREAM_DIR)/venv
	rm -rf $(DBT_DIR)/venv
	rm -rf $(AIRFLOW_DIR)/venv
	rm -rf $(GX_DIR)/venv
	rm -rf $(LAKEHOUSE_DIR)/venv
	rm -rf venv
	rm -rf $(FRONTEND_DIR)/node_modules
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf $(SIM_DIR)/htmlcov
	rm -rf $(SIM_DIR)/.pytest_cache
	rm -rf $(STREAM_DIR)/.pytest_cache
	rm -rf .pytest_cache
	rm -rf test-results.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup completed"

##@ Help

help:	## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
