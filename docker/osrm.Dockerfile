FROM osrm/osrm-backend:latest

WORKDIR /data

# Update apt sources to use archive.debian.org for EOL stretch
RUN sed -i 's/deb.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i '/stretch-updates/d' /etc/apt/sources.list && \
    apt-get update && apt-get install -y wget curl && \
    rm -rf /var/lib/apt/lists/*

COPY docker/scripts/osrm-init.sh /usr/local/bin/osrm-init.sh
RUN chmod +x /usr/local/bin/osrm-init.sh

EXPOSE 5000

CMD ["/usr/local/bin/osrm-init.sh"]
