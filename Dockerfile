# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.14
ARG UV_VERSION=0.11.21

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim AS dependency-builder
COPY --from=uv /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python \
    "python-multipart>=0.0.20" \
    "boto3>=1.35.0" \
    "pypdf>=6.19.0"
RUN /opt/venv/bin/python -c "from pypdf import PdfReader; from pymongo import AsyncMongoClient; print('runtime dependencies available')"

FROM dependency-builder AS core-builder
COPY packages/woobe-core/pyproject.toml packages/woobe-core/pyproject.toml
COPY packages/woobe-core/src/ packages/woobe-core/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python --no-deps --editable packages/woobe-core

FROM core-builder AS workers-builder
COPY packages/woobe-workers/pyproject.toml packages/woobe-workers/pyproject.toml
COPY packages/woobe-workers/src/ packages/woobe-workers/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python --no-deps --editable packages/woobe-workers \
    && uv pip check --python /opt/venv/bin/python

FROM core-builder AS api-builder
COPY packages/woobe-api/pyproject.toml packages/woobe-api/pyproject.toml
COPY packages/woobe-api/src/ packages/woobe-api/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python --no-deps --editable packages/woobe-api \
    && uv pip check --python /opt/venv/bin/python

FROM python:${PYTHON_VERSION}-slim AS runtime-base

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes pip \
    && groupadd --system --gid 10001 woobe \
    && useradd --system --uid 10001 --gid woobe --home-dir /app --shell /usr/sbin/nologin woobe

WORKDIR /app
COPY --chown=woobe:woobe packages/woobe-core/ packages/woobe-core/
COPY --chown=woobe:woobe scripts/docker-entrypoint.sh /usr/local/bin/woobe-entrypoint

RUN sed -i 's/\r$//' /usr/local/bin/woobe-entrypoint \
    && test -x /bin/sh \
    && head -n 1 /usr/local/bin/woobe-entrypoint | grep -qx '#!/bin/sh' \
    && chmod 0555 /usr/local/bin/woobe-entrypoint \
    && mkdir -p /tmp/woobe /app/storage/uploads \
    && chown -R woobe:woobe /tmp/woobe /app/storage

USER 10001:10001
ENTRYPOINT ["/usr/local/bin/woobe-entrypoint"]

FROM runtime-base AS workers

LABEL org.opencontainers.image.title="Woobe Core Workers" \
      org.opencontainers.image.description="Woobe Core background execution process host" \
      org.opencontainers.image.licenses="LicenseRef-Woobe-Core-Sustainable-Use-1.0" \
      org.opencontainers.image.source="https://github.com/A1b3rt0M3rcad0/woobe"

COPY --from=workers-builder --chown=woobe:woobe /opt/venv /opt/venv
COPY --chown=woobe:woobe packages/woobe-workers/src/ packages/woobe-workers/src/

CMD ["python", "-m", "worker_main"]

FROM runtime-base AS api

LABEL org.opencontainers.image.title="Woobe Core API" \
      org.opencontainers.image.description="Woobe Core HTTP/API process host" \
      org.opencontainers.image.licenses="LicenseRef-Woobe-Core-Sustainable-Use-1.0" \
      org.opencontainers.image.source="https://github.com/A1b3rt0M3rcad0/woobe"

COPY --from=api-builder --chown=woobe:woobe /opt/venv /opt/venv
COPY --chown=woobe:woobe packages/woobe-api/src/ packages/woobe-api/src/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
