FROM golang:1.25-alpine AS build

ARG MINIO_RELEASE=RELEASE.2025-10-15T17-29-55Z

RUN apk add --no-cache git ca-certificates curl

WORKDIR /src
RUN git clone https://github.com/minio/minio.git . && \
    git checkout ${MINIO_RELEASE} && \
    CGO_ENABLED=0 go build -tags kqueue --trimpath -o /minio .

FROM alpine:3.20
RUN apk add --no-cache ca-certificates curl
COPY --from=build /minio /usr/bin/minio
EXPOSE 9000 9001
ENTRYPOINT ["/usr/bin/minio"]
