# OpenLDAP

> LDAP authentication service for Spark Thrift Server SQL connections

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LDAP_ADMIN_PASSWORD` | Admin password for LDAP directory | `admin` (from LocalStack) | Yes |
| `LDAP_ORGANISATION` | Organization name | `Rideshare Platform` | No |
| `LDAP_DOMAIN` | LDAP domain | `rideshare.local` | No |
| `LDAP_TLS` | Enable TLS | `false` | No |

### LDAP Endpoint

| Protocol | Host | Port | Base DN |
|----------|------|------|---------|
| LDAP | `openldap` (Docker) or `localhost` (host) | 389 | `dc=rideshare,dc=local` |

**Connection String:**
```
ldap://openldap:389
```

### Configuration

| File | Purpose |
|------|---------|
| `bootstrap.ldif` | Initial LDAP directory structure and users |

### Prerequisites

- LocalStack Secrets Manager (for `LDAP_ADMIN_PASSWORD`)
- Docker Compose with `data-pipeline` profile

## Common Tasks

### Start OpenLDAP Service

```bash
# Start as part of data-pipeline profile
docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d openldap

# Check service health
docker compose -f infrastructure/docker/compose.yml ps openldap

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f openldap
```

### Query LDAP Directory

```bash
# Search all entries (from host machine)
ldapsearch -x -H ldap://localhost:389 \
  -b dc=rideshare,dc=local \
  -D cn=admin,dc=rideshare,dc=local \
  -w admin

# List users organizational unit
ldapsearch -x -H ldap://localhost:389 \
  -b ou=users,dc=rideshare,dc=local \
  -D cn=admin,dc=rideshare,dc=local \
  -w admin
```

### Test LDAP Authentication

```bash
# Verify admin user credentials
ldapwhoami -x -H ldap://localhost:389 \
  -D cn=admin,ou=users,dc=rideshare,dc=local \
  -w admin
```

Expected output:
```
dn:cn=admin,ou=users,dc=rideshare,dc=local
```

### Connect to Spark Thrift Server with LDAP Auth

```bash
# Beeline connection using LDAP credentials
docker exec rideshare-spark-thrift-server \
  /opt/spark/bin/beeline \
  -u 'jdbc:hive2://localhost:10000/default' \
  -n admin \
  -p admin \
  -e 'SHOW DATABASES;'
```

## LDAP Directory Structure

The bootstrap.ldif defines:

```
dc=rideshare,dc=local (root)
└── ou=users (organizational unit)
    └── cn=admin,ou=users,dc=rideshare,dc=local
        - username: admin
        - password: admin
        - email: admin@rideshare.local
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `ldapsearch: Can't contact LDAP server` | OpenLDAP not running or port 389 blocked | Check service health: `docker compose ps openldap` |
| `Invalid credentials (49)` | Wrong password | Verify LDAP_ADMIN_PASSWORD in `/secrets/data-pipeline.env` (default: `admin`) |
| Spark Thrift auth fails | LDAP service not healthy | Check `docker compose logs openldap` and verify health check passes |
| `Service Unavailable (51)` | LDAP directory not initialized | Wait for bootstrap.ldif to be processed (check logs) |

### Health Check Details

The service health check runs:
```bash
ldapsearch -x -H ldap://localhost:389 \
  -b dc=rideshare,dc=local \
  -D cn=admin,dc=rideshare,dc=local \
  -w "$LDAP_ADMIN_PASSWORD" \
  -s base
```

Interval: 10s, Timeout: 5s, Retries: 5

### Check Service Status

```bash
# View health status
docker inspect rideshare-openldap --format='{{.State.Health.Status}}'

# View health check logs
docker inspect rideshare-openldap --format='{{json .State.Health}}' | jq
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context and LDAP integration details
- [../../docs/INFRASTRUCTURE.md](../../docs/INFRASTRUCTURE.md) — Docker Compose configuration
- [../scripts/seed-secrets.py](../scripts/seed-secrets.py) — Secrets initialization
