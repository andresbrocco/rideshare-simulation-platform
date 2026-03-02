FROM busybox:1.37-musl AS tools

FROM grafana/loki:3.6.5
COPY --from=tools /bin/busybox /bin/sh
