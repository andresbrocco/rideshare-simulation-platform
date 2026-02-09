FROM busybox:1.37-musl AS healthcheck

FROM grafana/tempo:2.10.0
COPY --from=healthcheck /bin/wget /usr/bin/wget
