# Development stage - Vite dev server with HMR
FROM node:20-alpine AS development

WORKDIR /app

# Copy package files for dependency installation
COPY package*.json ./

# Create entrypoint script that installs deps if node_modules is empty
# Uses npm ci for reproducible builds from committed package-lock.json
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'if [ ! -d "/app/node_modules/.bin" ]; then' >> /entrypoint.sh && \
    echo '  echo "Installing dependencies..."' >> /entrypoint.sh && \
    echo '  npm ci' >> /entrypoint.sh && \
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

RUN npm run build

# Production stage - serve with Nginx
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
