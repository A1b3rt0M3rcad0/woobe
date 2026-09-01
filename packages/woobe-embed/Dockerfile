# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=22
ARG NGINX_VERSION=1.29.4

FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .
RUN npm run test && npm run typecheck && npm run build

FROM nginxinc/nginx-unprivileged:${NGINX_VERSION}-alpine AS runtime

LABEL org.opencontainers.image.title="Woobe Core ChatSurface" \
      org.opencontainers.image.description="Woobe Core browser-facing ChatSurface artifact" \
      org.opencontainers.image.licenses="LicenseRef-Woobe-Core-Sustainable-Use-1.0" \
      org.opencontainers.image.source="https://github.com/A1b3rt0M3rcad0/woobe"

USER root
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/chat/v1/health || exit 1
