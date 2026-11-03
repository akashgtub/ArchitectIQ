# syntax=docker/dockerfile:1
# ArchitectIQ - Frontend Multi-Stage Containerfile
# Stage 1: Build stage with Node.js 20 Alpine
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests for deterministic reproducible installation
COPY frontend/package.json frontend/package-lock.json ./

# Install exact dependencies via npm ci
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Compile production bundle using Vite
RUN npm run build

# Stage 2: Production runtime with Nginx 1.25 Alpine
FROM nginx:1.25-alpine AS runtime

# Remove default Nginx welcome assets
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled SPA bundle from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy production Nginx reverse proxy configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Healthcheck targeting the Nginx healthz endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/healthz || exit 1

# Start Nginx in foreground mode
CMD ["nginx", "-g", "daemon off;"]
