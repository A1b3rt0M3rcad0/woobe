# PostgreSQL backup and restore runbook

## Initial objectives

- RPO: 24 hours for the MVP until continuous archiving is introduced.
- RTO: 4 hours for a single-region restore, including validation and traffic re-enable.
- Retention: 7 daily, 4 weekly and 3 monthly encrypted backups.
- Restore drill: at least monthly and before every release candidate.

These are operational objectives, not guarantees. Production requires encrypted object storage, access logging, immutability/retention controls and a separate account or failure domain.

## Backup

Run `scripts/backup_postgres.sh` from a PostgreSQL client image or controlled operations host. It creates a custom-format dump and SHA-256 sidecar with restrictive permissions.

```bash
docker run --rm --network projectrai_data \
  --env-file /run/secrets/projectrai.env \
  -e POSTGRES_HOST=db \
  -v /srv/projectrai/backups:/backups \
  -v "$PWD/scripts:/scripts:ro" \
  postgres:17-alpine /scripts/backup_postgres.sh
```

After creation, copy the dump and checksum to encrypted off-host storage. A backup is not accepted until the checksum is verified after upload.

## Restore drill

Never test restore against the production database. Provision an isolated database at the same major PostgreSQL/pgvector version, apply access restrictions, then run:

```bash
RESTORE_FILE=/backups/projectrai-YYYYMMDDTHHMMSSZ.dump \
RESTORE_CONFIRM=restore-projectrai \
POSTGRES_HOST=restore-db \
POSTGRES_USER="$POSTGRES_USER" \
POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
POSTGRES_DB=projectrai_restore \
./scripts/restore_postgres.sh
```

Validate:

1. `alembic current` reports the expected head.
2. tenant, membership, API-key, agent, session, trace and usage row counts are plausible.
3. authentication, project overview and mock runtime smoke checks pass against the restored database.
4. no cross-tenant access is possible.
5. measured restore time is within the 4-hour RTO.

Record backup identifier, checksum, start/end timestamps, operator, target environment, row-count checks and smoke evidence. The stage-07 gate remains incomplete until one restore drill has been executed in staging and linked in the PR.

## Recovery sequence

1. Declare the incident and stop writes.
2. Identify the latest verified backup satisfying the RPO.
3. Provision an isolated replacement database.
4. Restore and validate as above.
5. Update the secret-managed database endpoint.
6. Run `/ready`, authenticated smoke and cross-tenant checks.
7. Re-enable traffic gradually and retain the failed database for forensic analysis.
