FROM osrm/osrm-backend:latest

WORKDIR /data

RUN apt-get update && apt-get install -y wget curl && \
    rm -rf /var/lib/apt/lists/*

COPY docker/scripts/osrm-init.sh /usr/local/bin/osrm-init.sh
RUN chmod +x /usr/local/bin/osrm-init.sh

EXPOSE 5000

CMD ["/usr/local/bin/osrm-init.sh"]
