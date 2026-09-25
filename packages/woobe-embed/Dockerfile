# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=22
ARG NGINX_VERSION=1.29.4

FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /workspace/packages/woobe-embed

COPY packages/woobe-embed/package.json packages/woobe-embed/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY packages/woobe-embed ./
COPY packages/woobe-runtime-client ../woobe-runtime-client
# Tests and typechecking run on native CI runners before release. Keep the\n# multi-architecture production build limited to artifact construction.\nRUN npm run build

FROM nginxinc/nginx-unprivileged:${NGINX_VERSION}-alpine AS runtime

LABEL org.opencontainers.image.title="Woobe Core Embed" \
      org.opencontainers.image.description="Woobe Core browser-facing ChatSurface artifact" \
      org.opencontainers.image.licenses="LicenseRef-Woobe-Core-Sustainable-Use-1.0" \
      org.opencontainers.image.source="https://github.com/A1b3rt0M3rcad0/woobe"

USER root
RUN apk upgrade --no-cache
COPY packages/woobe-embed/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /workspace/packages/woobe-embed/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/chat/v1/health || exit 1
