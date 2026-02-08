# syntax=docker/dockerfile:1

# Builder: Bun (much faster than Node/Yarn)

FROM docker.io/oven/bun:1-alpine AS builder
WORKDIR /app

ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL NODE_ENV=production

# Copy package files first for better layer caching
COPY package.json bun.lockb* yarn.lock* ./

# Install dependencies with Bun (10x faster than yarn/npm)
RUN bun install --frozen-lockfile || bun install

# Copy source and build
COPY . .
RUN bun run build

# Runtime Stage
FROM docker.io/nginx:alpine
ENV NGINX_ENTRYPOINT_QUIET_LOGS=1

# Install curl for health checks
RUN apk add --no-cache curl

COPY --from=builder /app/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
