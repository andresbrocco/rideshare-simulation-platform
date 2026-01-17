#!/bin/bash
# Export all Superset dashboards to JSON for version control

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARDS_DIR="$(cd "${SCRIPT_DIR}/../dashboards" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/../tests/venv/bin/python3"

echo "Exporting Superset dashboards..."

export_dashboard() {
    local slug=$1
    local output_file="${DASHBOARDS_DIR}/${slug}.json"

    echo "Exporting dashboard: ${slug}"

    ${VENV_PYTHON} -c "
import requests
import json
import sys

base_url = 'http://localhost:8088'
session = requests.Session()

login_url = f'{base_url}/api/v1/security/login'
login_data = {
    'username': 'admin',
    'password': 'admin',
    'provider': 'db',
    'refresh': True
}

response = session.post(login_url, json=login_data)
if response.status_code != 200:
    print(f'Login failed: {response.text}', file=sys.stderr)
    sys.exit(1)

token_data = response.json()
access_token = token_data.get('access_token')
session.headers.update({'Authorization': f'Bearer {access_token}'})

list_url = f'{base_url}/api/v1/dashboard/'
response = session.get(list_url)
if response.status_code != 200:
    print(f'Failed to fetch dashboards: {response.text}', file=sys.stderr)
    sys.exit(1)

dashboards = response.json().get('result', [])
dashboard_id = None
for dashboard in dashboards:
    if dashboard.get('slug') == '${slug}':
        dashboard_id = dashboard.get('id')
        break

if not dashboard_id:
    print(f'Dashboard with slug ${slug} not found', file=sys.stderr)
    sys.exit(1)

export_url = f'{base_url}/api/v1/dashboard/export/'
params = {'q': json.dumps([dashboard_id])}
response = session.get(export_url, params=params)

if response.status_code != 200:
    print(f'Failed to export dashboard: {response.text}', file=sys.stderr)
    sys.exit(1)

with open('${output_file}', 'wb') as f:
    f.write(response.content)

print(f'Exported ${slug} to ${output_file}')
"
}

export_dashboard "operations"
export_dashboard "driver-performance"
export_dashboard "demand-analysis"
export_dashboard "revenue-analytics"

echo "All dashboards exported successfully!"
