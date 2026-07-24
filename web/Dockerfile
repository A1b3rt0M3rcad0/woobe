# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=22
ARG NGINX_VERSION=1.29.4

FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .
RUN --mount=type=secret,id=web_env,target=/.env.web,required=true \
    tr -d '\r' < /.env.web > /tmp/projectrai-web.env \
    && grep -Eq '^VITE_API_URL=https?://[^[:space:]]+$' /tmp/projectrai-web.env \
    && ! grep -Eq '^(POSTGRES_|RABBITMQ_|PROJECTRAI_)' /tmp/projectrai-web.env \
    && npm run build

FROM nginxinc/nginx-unprivileged:${NGINX_VERSION}-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/nginx-health || exit 1