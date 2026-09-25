# Running published Woobe container packages

Woobe publishes four independently deployable Core container packages to GHCR:

```text
ghcr.io/a1b3rt0m3rcad0/woobe-api:<VERSION>
ghcr.io/a1b3rt0m3rcad0/woobe-workers:<VERSION>
ghcr.io/a1b3rt0m3rcad0/woobe-frontend:<VERSION>
ghcr.io/a1b3rt0m3rcad0/woobe-embed:<VERSION>
```

`woobe-core` is not a standalone process image. It is the shared Python domain/runtime package and migration owner embedded in the API and Workers images.

All application images in one deployment should use the same Woobe platform version.

## Pull the images

```bash
VERSION=0.14.0

docker pull ghcr.io/a1b3rt0m3rcad0/woobe-api:$VERSION
docker pull ghcr.io/a1b3rt0m3rcad0/woobe-workers:$VERSION
docker pull ghcr.io/a1b3rt0m3rcad0/woobe-frontend:$VERSION
docker pull ghcr.io/a1b3rt0m3rcad0/woobe-embed:$VERSION
```

The root [`.env.example`](../../.env.example) is the canonical environment-variable inventory. The root [`compose.yaml`](../../compose.yaml) is the canonical wiring reference for PostgreSQL, MongoDB, Redis, RabbitMQ, storage, migrations and application services.

## API package

Image:

```text
ghcr.io/a1b3rt0m3rcad0/woobe-api:<VERSION>
```

Default process:

```text
uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips *
```

Exposed port: `8000`.

The API requires the Woobe relational/runtime infrastructure to be reachable. At minimum, configure the deployment-specific values for PostgreSQL, Redis, MongoDB, encryption/authentication and public-origin enforcement.

Representative configuration:

```env
WOOBE_EDITION=core
WOOBE_ENVIRONMENT=production

WOOBE_DATABASE_URL=postgresql://woobe:<password>@postgres.example.internal:5432/woobe
WOOBE_REDIS_URL=redis://redis.example.internal:6379/0
WOOBE_MONGODB_URL=mongodb://mongo.example.internal:27017
WOOBE_MONGODB_DATABASE=woobe
WOOBE_RUN_PERSISTENCE_MODE=event_journal

WOOBE_ENCRYPTION_KEY=<strong-random-secret>
WOOBE_SECRET_KEY=<different-strong-random-secret>
WOOBE_CHAT_TOKEN_SIGNING_KEY=<third-strong-random-secret>

WOOBE_CORS_ORIGINS=https://app.example.com,https://chat.example.com
WOOBE_TRUSTED_HOSTS=api.example.com

WOOBE_STORAGE_DRIVER=local
WOOBE_UPLOAD_LOCAL_DIR=/app/storage/uploads
```

If local Knowledge storage is used, mount a persistent volume at `/app/storage/uploads`.

Example:

```bash
docker run -d \
  --name woobe-api \
  --env-file .env \
  -p 8000:8000 \
  -v woobe_uploads:/app/storage/uploads \
  ghcr.io/a1b3rt0m3rcad0/woobe-api:0.14.0
```

Readiness:

```text
GET http://localhost:8000/ready
```

### Migrations

Schema migration is explicit and must complete before API/Workers rollout. The API image contains the Core migration history:

```bash
docker run --rm \
  --env-file .env \
  ghcr.io/a1b3rt0m3rcad0/woobe-api:0.14.0 \
  alembic -c packages/woobe-core/alembic.ini upgrade head
```

The database hostname in `WOOBE_DATABASE_URL` must be resolvable from that container.

## Workers package

Image:

```text
ghcr.io/a1b3rt0m3rcad0/woobe-workers:<VERSION>
```

Default process:

```text
python -m worker_main
```

Workers do not expose the public HTTP API. They consume background work and runtime persistence flows.

They require the same compatible Core data/runtime services as the API plus RabbitMQ.

Representative configuration:

```env
WOOBE_EDITION=core
WOOBE_ENVIRONMENT=production

WOOBE_DATABASE_URL=postgresql://woobe:<password>@postgres.example.internal:5432/woobe
WOOBE_REDIS_URL=redis://redis.example.internal:6379/0
WOOBE_MONGODB_URL=mongodb://mongo.example.internal:27017
WOOBE_MONGODB_DATABASE=woobe
WOOBE_RUN_PERSISTENCE_MODE=event_journal

WOOBE_RABBITMQ_URL=amqp://woobe:<password>@rabbitmq.example.internal:5672/
WOOBE_RABBITMQ_EXCHANGE=woobe.events

WOOBE_ENCRYPTION_KEY=<same-encryption-key-used-by-api>

WOOBE_STORAGE_DRIVER=local
WOOBE_UPLOAD_LOCAL_DIR=/app/storage/uploads

WOOBE_WORKER_HEALTH_FILE=/tmp/woobe/worker-health.json
WOOBE_NETWORK_WORKER_PREFETCH=4
WOOBE_NETWORK_WORKER_SLOTS=4
```

When local Knowledge storage is used, API and Workers must see the same persistent upload storage.

Example:

```bash
docker run -d \
  --name woobe-workers \
  --env-file .env \
  -v woobe_uploads:/app/storage/uploads \
  ghcr.io/a1b3rt0m3rcad0/woobe-workers:0.14.0
```

Workers may be scaled independently from API:

```text
API      x2
Workers  x10
```

The root Compose contract remains the reference for dependency ordering: migrations first, then Workers after PostgreSQL/RabbitMQ/Redis/MongoDB are available.

## Frontend package

Image:

```text
ghcr.io/a1b3rt0m3rcad0/woobe-frontend:<VERSION>
```

Exposed port: `8080`.

The published Frontend image is deployment-neutral. Configure its public endpoints when the container starts:

```env
WOOBE_PUBLIC_API_URL=https://api.example.com
WOOBE_PUBLIC_CHAT_EMBED_URL=https://chat.example.com
```

Example:

```bash
docker run -d \
  --name woobe-frontend \
  -p 8080:8080 \
  -e WOOBE_PUBLIC_API_URL=https://api.example.com \
  -e WOOBE_PUBLIC_CHAT_EMBED_URL=https://chat.example.com \
  ghcr.io/a1b3rt0m3rcad0/woobe-frontend:0.14.0
```

These are runtime values. The image does not need to be rebuilt when the API or Embed public domains change.

## Embed package

Image:

```text
ghcr.io/a1b3rt0m3rcad0/woobe-embed:<VERSION>
```

Exposed port: `8080`.

The Embed image is a static browser artifact and currently requires no container environment variables:

```bash
docker run -d \
  --name woobe-embed \
  -p 8081:8080 \
  ghcr.io/a1b3rt0m3rcad0/woobe-embed:0.14.0
```

Health endpoint:

```text
GET http://localhost:8081/chat/v1/health
```

For self-hosted use, load the published script from the Embed origin and pass the Woobe API origin explicitly:

```html
<script src="https://chat.example.com/chat/v1/embed.js"></script>
<div id="support"></div>
<script>
  const chat = window.WoobeChat.mount({
    container: "#support",
    surfaceId: "surface_...",
    sessionToken: "...",
    apiBaseUrl: "https://api.example.com"
  });
</script>
```

`sessionToken` must be a valid ChatSurface Session token issued through the Woobe API. `surfaceId` identifies the configured ChatSurface.

For self-hosting, set `apiBaseUrl` explicitly. If it is omitted, the loader's public default is `https://api.woobe.ai`.

If the iframe assets are served from a different origin/path than the loader script, `iframeBaseUrl` can also be supplied to `WoobeChat.mount(...)`.

## Minimal Compose using published images

For a real deployment, prefer the full root `compose.yaml` contract or translate it to your orchestrator. The application-image portion looks like:

```yaml
services:
  api:
    image: ghcr.io/a1b3rt0m3rcad0/woobe-api:0.14.0
    env_file: [.env]
    ports:
      - "8000:8000"
    volumes:
      - woobe_uploads:/app/storage/uploads

  workers:
    image: ghcr.io/a1b3rt0m3rcad0/woobe-workers:0.14.0
    env_file: [.env]
    volumes:
      - woobe_uploads:/app/storage/uploads

  frontend:
    image: ghcr.io/a1b3rt0m3rcad0/woobe-frontend:0.14.0
    environment:
      WOOBE_PUBLIC_API_URL: https://api.example.com
      WOOBE_PUBLIC_CHAT_EMBED_URL: https://chat.example.com
    ports:
      - "8080:8080"

  embed:
    image: ghcr.io/a1b3rt0m3rcad0/woobe-embed:0.14.0
    ports:
      - "8081:8080"

volumes:
  woobe_uploads:
```

This fragment intentionally omits PostgreSQL, MongoDB, Redis, RabbitMQ and the explicit migration job. Those dependencies still exist and must be supplied externally or defined in the deployment. The root `compose.yaml` remains the complete supported Core topology.

## Version rule

Do not mix platform versions unless a release explicitly documents compatibility.

Prefer:

```text
woobe-api       0.14.0
woobe-workers   0.14.0
woobe-frontend  0.14.0
woobe-embed     0.14.0
```

rather than independently upgrading individual application images.

## Configuration reference

- Full variable inventory: [`.env.example`](../../.env.example)
- Canonical self-host wiring: [`compose.yaml`](../../compose.yaml)
- Production deployment: [`production-deployment.md`](production-deployment.md)
- Upgrades: [`../UPGRADING.md`](../UPGRADING.md)
