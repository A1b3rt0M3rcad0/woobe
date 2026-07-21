# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.14
ARG UV_VERSION=0.11.21

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim AS builder
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
    "pypdf>=6.0.0"
RUN /opt/venv/bin/python -c "from pypdf import PdfReader; print('pypdf runtime dependency available')"

FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROJECTRAI_RUN_MIGRATIONS=false

RUN groupadd --system --gid 10001 projectrai \
    && useradd --system --uid 10001 --gid projectrai --home-dir /app --shell /usr/sbin/nologin projectrai

WORKDIR /app
COPY --from=builder --chown=projectrai:projectrai /opt/venv /opt/venv
COPY --chown=projectrai:projectrai src/ src/
COPY --chown=projectrai:projectrai migrations/ migrations/
COPY --chown=projectrai:projectrai alembic.ini ./
COPY --chown=projectrai:projectrai scripts/docker-entrypoint.sh /usr/local/bin/projectrai-entrypoint

# Windows checkouts may convert shell scripts to CRLF. Normalize the entrypoint
# inside the image so the kernel resolves /bin/sh instead of /bin/sh\r.
RUN sed -i 's/\r$//' /usr/local/bin/projectrai-entrypoint \
    && test -x /bin/sh \
    && head -n 1 /usr/local/bin/projectrai-entrypoint | grep -qx '#!/bin/sh' \
    && chmod 0555 /usr/local/bin/projectrai-entrypoint \
    && mkdir -p /tmp/projectrai /app/storage/uploads \
    && chown -R projectrai:projectrai /tmp/projectrai /app/storage

USER 10001:10001
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/projectrai-entrypoint"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
