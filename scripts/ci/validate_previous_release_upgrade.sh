#!/usr/bin/env bash
set -euo pipefail

: "${WOOBE_UPGRADE_BASE_SHA:?WOOBE_UPGRADE_BASE_SHA is required}"
: "${WOOBE_CURRENT_API_IMAGE:?WOOBE_CURRENT_API_IMAGE is required}"

owner="${GITHUB_REPOSITORY_OWNER:-A1b3rt0M3rcad0}"
owner="${owner,,}"

git fetch --force --tags origin >/dev/null

previous_tag=""
previous_api_image=""
while IFS= read -r candidate_tag; do
  [[ -n "$candidate_tag" ]] || continue
  [[ "$candidate_tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || continue

  candidate_version="${candidate_tag#v}"
  candidate_image="ghcr.io/${owner}/woobe-api:${candidate_version}"

  if docker manifest inspect "$candidate_image" >/dev/null 2>&1; then
    previous_tag="$candidate_tag"
    previous_api_image="$candidate_image"
    break
  fi

  echo "Skipping reachable tag ${candidate_tag}: published API image ${candidate_image} does not exist"
done < <(
  git tag --merged "$WOOBE_UPGRADE_BASE_SHA" --list 'v[0-9]*' --sort=-version:refname
)

if [[ -z "$previous_tag" || -z "$previous_api_image" ]]; then
  echo "No previously published Woobe release with an API image is reachable from $WOOBE_UPGRADE_BASE_SHA" >&2
  exit 1
fi

echo "Validating upgrade from ${previous_tag} using ${previous_api_image}"

docker pull "$previous_api_image"
docker build --pull --target api --tag "$WOOBE_CURRENT_API_IMAGE" .

suffix="${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
network="woobe-upgrade-${suffix}"
db="woobe-upgrade-postgres-${suffix}"

cleanup() {
  docker rm -f "$db" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network create "$network" >/dev/null
docker run -d   --name "$db"   --network "$network"   -e POSTGRES_USER=woobe   -e POSTGRES_PASSWORD=woobe   -e POSTGRES_DB=woobe   pgvector/pgvector:pg17 >/dev/null

ready=false
for _ in $(seq 1 60); do
  if docker exec "$db" pg_isready -U woobe -d woobe >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != "true" ]]; then
  docker logs "$db" || true
  exit 1
fi

python scripts/generate_self_host_env.py --force
database_url="postgresql://woobe:woobe@${db}:5432/woobe"

run_migration() {
  local image="$1"
  shift
  docker run --rm     --network "$network"     --env-file .env     -e "WOOBE_POSTGRES_URL=${database_url}"     -e "WOOBE_DATABASE_URL=${database_url}"     "$image"     alembic -c packages/woobe-core/alembic.ini "$@"
}

run_migration "$previous_api_image" upgrade head

previous_revision="$(
  docker exec "$db" psql -U woobe -d woobe -Atv ON_ERROR_STOP=1     -c "SELECT version_num FROM alembic_version;"
)"
test -n "$previous_revision"
echo "Previous release schema revision: $previous_revision"

docker exec -i "$db" psql -U woobe -d woobe -v ON_ERROR_STOP=1 <<'SQL'
INSERT INTO identity.workspaces (id, name, slug, status)
VALUES (
  '14000000-0000-0000-0000-000000000001',
  'release-upgrade-probe',
  'release-upgrade-probe',
  'active'
);
SQL

run_migration "$WOOBE_CURRENT_API_IMAGE" upgrade head
run_migration "$WOOBE_CURRENT_API_IMAGE" check

probe="$(
  docker exec "$db" psql -U woobe -d woobe -Atv ON_ERROR_STOP=1     -c "SELECT name || ':' || status FROM identity.workspaces WHERE id = '14000000-0000-0000-0000-000000000001';"
)"
test "$probe" = "release-upgrade-probe:active"

current_revision="$(
  docker exec "$db" psql -U woobe -d woobe -Atv ON_ERROR_STOP=1     -c "SELECT version_num FROM alembic_version;"
)"
test -n "$current_revision"
echo "Current schema revision after upgrade: $current_revision"
echo "Previous-release upgrade validation passed: ${previous_tag} -> PR HEAD"
