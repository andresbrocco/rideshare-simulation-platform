# Development stage - Vite dev server with HMR
FROM node:20-alpine AS development

WORKDIR /app

COPY control-panel-frontend/package*.json ./

RUN npm install --force

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Build stage - compile React app with Vite
FROM node:20-alpine AS builder

WORKDIR /app

COPY control-panel-frontend/package*.json ./

RUN npm install --force

COPY control-panel-frontend/ .

RUN npm run build

# Production stage - serve with Nginx
FROM nginx:alpine AS production

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
