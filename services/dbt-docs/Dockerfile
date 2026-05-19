FROM python:3.13-slim AS builder
WORKDIR /dbt
COPY dbt-project/ .
RUN pip install --no-cache-dir \
    dbt-core \
    dbt-duckdb==1.10.0 \
    duckdb==1.4.4 \
    deltalake==1.4.2
RUN dbt deps --profiles-dir .
ENV DUCKDB_PATH=":memory:"
ENV S3_ENDPOINT="localhost:1"
ENV AWS_ACCESS_KEY_ID="dummy"
ENV AWS_SECRET_ACCESS_KEY="dummy"
ENV DBT_S3_PROVIDER="config"
RUN dbt docs generate --profiles-dir . --target duckdb

FROM nginx:alpine
COPY --from=builder /dbt/target/index.html /usr/share/nginx/html/
COPY --from=builder /dbt/target/manifest.json /usr/share/nginx/html/
COPY --from=builder /dbt/target/catalog.json /usr/share/nginx/html/
COPY --from=builder /dbt/target/sources.json /usr/share/nginx/html/
COPY --from=builder /dbt/target/graph_summary.json /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
