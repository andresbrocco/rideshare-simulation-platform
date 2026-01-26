# Docker Compose Profiles

This project uses Docker Compose profiles to enable selective service startup. For profile contents and usage examples, see `CLAUDE.md` or run `docker compose config`.

## Important Notes

- **Without profiles**: Running `docker compose up -d` starts nothing (all services have explicit profiles)
- **Memory limits**: Docker enforces limits - services exceeding their allocation will be killed
- **Health checks**: All services have health checks; dependents wait for healthy status
- **Docker Desktop**: May need to increase memory allocation in Preferences > Resources

## Memory Requirements Summary

| Configuration | Total Memory |
|--------------|--------------|
| core only | ~3.4GB |
| data-pipeline only | ~5GB |
| core + data-pipeline | ~8.5GB |
| All profiles | ~10.5GB |
