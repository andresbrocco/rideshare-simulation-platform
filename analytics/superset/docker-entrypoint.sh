#!/bin/bash
set -e

echo "Installing PyHive and Thrift for Spark connectivity..."
pip install --target=/tmp/python-packages pyhive thrift

echo "Starting Superset server..."
exec /usr/bin/run-server.sh
