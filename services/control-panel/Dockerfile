# Development stage - Vite dev server with HMR
FROM node:20-alpine AS development

WORKDIR /app

# Copy package files for dependency installation
COPY package*.json ./

# Pre-install dependencies at build time to a staging directory.
# At runtime, if the named volume is empty the entrypoint copies these
# (fast file copy) instead of running npm install over the network.
RUN npm install --force && \
    cp -a node_modules /tmp/node_modules && \
    rm -rf node_modules

# Create entrypoint script that seeds the volume from the build-time cache
# Uses cp instead of npm install for fast cold starts
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'if [ ! -d "/app/node_modules/.bin" ]; then' >> /entrypoint.sh && \
    echo '  echo "Seeding node_modules from build cache..."' >> /entrypoint.sh && \
    echo '  cp -a /tmp/node_modules/. /app/node_modules/' >> /entrypoint.sh && \
    echo 'fi' >> /entrypoint.sh && \
    echo 'exec "$@"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

EXPOSE 5173

ENTRYPOINT ["/entrypoint.sh"]
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Build stage - compile React app with Vite
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .
# Production builds need zones.geojson in public/ — sourced from services/simulation/data/
# via Docker Compose bind mount in development; for production, widen the build context.

RUN npm run build

# Static stage - extract build artifacts only (for S3 deployment)
# Usage: docker build --target static -o dist .
FROM scratch AS static
COPY --from=builder /app/dist /

# Production stage - serve with Nginx (for local K8s deployment)
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html

# SPA routing: serve index.html for all routes not matching a file
RUN echo 'server {' > /etc/nginx/conf.d/default.conf && \
    echo '  listen 80;' >> /etc/nginx/conf.d/default.conf && \
    echo '  root /usr/share/nginx/html;' >> /etc/nginx/conf.d/default.conf && \
    echo '  index index.html;' >> /etc/nginx/conf.d/default.conf && \
    echo '  location / {' >> /etc/nginx/conf.d/default.conf && \
    echo '    try_files $uri $uri/ /index.html;' >> /etc/nginx/conf.d/default.conf && \
    echo '  }' >> /etc/nginx/conf.d/default.conf && \
    echo '}' >> /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
