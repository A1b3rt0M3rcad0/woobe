# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=22
ARG NGINX_VERSION=1.29.4

FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app

ARG VITE_API_URL

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .
RUN node -e "const value=process.env.VITE_API_URL; if (!value) throw new Error('VITE_API_URL build argument is required'); const url=new URL(value); if (!['http:','https:'].includes(url.protocol)) throw new Error('VITE_API_URL must use http or https')" \
    && npm run build

FROM nginxinc/nginx-unprivileged:${NGINX_VERSION}-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/nginx-health || exit 1