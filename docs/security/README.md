# Security Overview

This document describes the security model for the Rideshare Simulation Platform.

## Current Security Posture

The platform implements a **development-first security model** designed for:

- Local development and demonstrations
- Portfolio showcase purposes
- Synthetic data only (no real PII)
- Quick setup and iteration

This is intentional. The project demonstrates data engineering concepts, not production security hardening.

## Threat Model Comparison

| Aspect | Demo Environment | Production Environment |
|--------|------------------|------------------------|
| Data sensitivity | Synthetic only | Real user PII |
| Network exposure | localhost / Docker | Public internet |
| Attacker motivation | None | Financial, competitive |
| Compliance requirements | None | GDPR, SOC 2, etc. |

## Security Controls Summary

| Component | Authentication | Transport | Notes |
|-----------|---------------|-----------|-------|
| REST API (`/simulation/*`, `/agents/*`, `/metrics/*`) | API key via `X-API-Key` header | HTTP | Protected routes |
| REST API (`/health`) | None | HTTP | Intentionally open for infrastructure |
| WebSocket (`/ws`) | API key via query string | WS | [Known limitation](#known-limitations) |
| Stream Processor (`/health`, `/metrics`) | None | HTTP | Internal monitoring only |

## Known Limitations

These are documented trade-offs for development convenience:

1. **WebSocket query string authentication** - API key exposed in URLs, browser history, server logs
2. **Default API key** - `dev-api-key-change-in-production` is insecure if unchanged
3. **No rate limiting** - All endpoints accept unlimited requests
4. **HTTP transport** - No TLS encryption in local development
5. **Stream processor endpoints** - No authentication on `/health` and `/metrics`

See [development.md](development.md) for detailed explanations of each trade-off.

## Documentation

| Document | Purpose |
|----------|---------|
| [development.md](development.md) | Current security implementation details |
| [production-checklist.md](production-checklist.md) | Steps to harden for production deployment |

## Quick Reference

**Setting the API key:**
```bash
# Generate a secure key
openssl rand -hex 32

# Set in .env
API_KEY=your-generated-key-here
```

**Making authenticated requests:**
```bash
# REST API
curl -H "X-API-Key: $API_KEY" http://localhost:8000/simulation/status

# WebSocket (from browser)
new WebSocket("ws://localhost:8000/ws?api_key=$API_KEY")
```
