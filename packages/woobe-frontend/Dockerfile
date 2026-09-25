# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=22
ARG NGINX_VERSION=1.29.4

FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /workspace/packages/woobe-frontend
COPY packages/woobe-frontend/package.json packages/woobe-frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

FROM deps AS builder
ARG VITE_API_URL=http://127.0.0.1:8000
ARG VITE_CHAT_EMBED_URL=http://127.0.0.1:8081
ARG VITE_WOOBE_EDITION=core
COPY packages/woobe-frontend ./
COPY packages/woobe-runtime-client ../woobe-runtime-client
COPY packages/woobe-ui ../woobe-ui
RUN test -n "${VITE_API_URL}" \
    && test -n "${VITE_CHAT_EMBED_URL}" \
    && test "${VITE_WOOBE_EDITION}" = "core" \
    && VITE_API_URL="${VITE_API_URL}" VITE_CHAT_EMBED_URL="${VITE_CHAT_EMBED_URL}" VITE_WOOBE_EDITION="${VITE_WOOBE_EDITION}" npm run test:run \
    && VITE_API_URL="${VITE_API_URL}" VITE_CHAT_EMBED_URL="${VITE_CHAT_EMBED_URL}" VITE_WOOBE_EDITION="${VITE_WOOBE_EDITION}" npm run build

FROM nginxinc/nginx-unprivileged:${NGINX_VERSION}-alpine AS runtime

LABEL org.opencontainers.image.title="Woobe Core Web" \
      org.opencontainers.image.description="Woobe Core administrative control-plane frontend" \
      org.opencontainers.image.licenses="LicenseRef-Woobe-Core-Sustainable-Use-1.0" \
      org.opencontainers.image.source="https://github.com/A1b3rt0M3rcad0/woobe"

USER root
RUN apk upgrade --no-cache
COPY packages/woobe-frontend/nginx-main.conf /etc/nginx/woobe-nginx.conf
COPY packages/woobe-frontend/nginx.conf /etc/nginx/woobe-server.conf.template
COPY packages/woobe-frontend/docker-entrypoint.sh /usr/local/bin/woobe-web-entrypoint
RUN chmod 0555 /usr/local/bin/woobe-web-entrypoint
COPY --from=builder /workspace/packages/woobe-frontend/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/woobe-web-entrypoint"]
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/nginx-health || exit 1
