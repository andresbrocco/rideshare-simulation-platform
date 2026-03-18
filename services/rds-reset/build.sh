#!/usr/bin/env bash
# Install pg8000 into this directory so archive_file can package it.
# Run before `terraform apply` on the foundation stack.
set -euo pipefail
cd "$(dirname "$0")"
pip install -r requirements.txt -t . --upgrade --quiet
echo "Dependencies installed into $(pwd)"
