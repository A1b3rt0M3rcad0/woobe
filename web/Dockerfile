# syntax=docker/dockerfile:1.7

ARG NODE_VERSION=22
ARG NGINX_VERSION=1.29.4

FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app

ARG VITE_API_URL

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .
RUN test -n "${VITE_API_URL}" \
    && node -e "const u=new URL(process.argv[1]); if (!['http:','https:'].includes(u.protocol)) process.exit(1)" "${VITE_API_URL}" \
    && VITE_API_URL="${VITE_API_URL}" npm run build \
    && API_ORIGIN="$(node -e "console.log(new URL(process.argv[1]).origin)" "${VITE_API_URL}")" \
    && sed "s|__API_ORIGIN__|${API_ORIGIN}|g" nginx.conf > /tmp/nginx.conf

FROM nginxinc/nginx-unprivileged:${NGINX_VERSION}-alpine AS runtime
COPY --from=builder /tmp/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1:8080/nginx-health || exit 1
