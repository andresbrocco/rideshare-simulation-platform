FROM busybox:1.37-musl AS healthcheck

FROM otel/opentelemetry-collector-contrib:0.96.0
COPY --from=healthcheck /bin/wget /usr/bin/wget
