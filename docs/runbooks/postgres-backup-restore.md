# Woobe PostgreSQL backup and restore

A backup is only useful after a restore has been validated. Keep database backups off-host and protect them with encryption, access logging and retention controls appropriate to the deployment.

## Backup

```bash
WOOBE_POSTGRES_URL='postgresql://...' \
BACKUP_DIR=./backups \
sh scripts/backup_postgres.sh
```

The script creates a custom-format PostgreSQL dump and SHA-256 sidecar.

When Community uses local Knowledge storage, back up the `woobe_uploads` volume together with PostgreSQL so document metadata and physical files remain consistent.

## Restore drill

Never test a destructive restore against production. Create an isolated database at a compatible PostgreSQL/pgvector version and run:

```bash
RESTORE_FILE=/backups/woobe-YYYYMMDDTHHMMSSZ.dump \
RESTORE_CONFIRM=restore-woobe \
RESTORE_CLEAN=false \
WOOBE_POSTGRES_URL='postgresql://.../woobe_restore' \
sh scripts/restore_postgres.sh
```

Then verify the checksum, Alembic head, Workspace/Project ownership, runtime keys, Agents/Releases, Network/Releases, Knowledge metadata, Sessions/Runs/Traces and cross-tenant authorization. If local Knowledge storage is in use, restore the matching files and verify document access.

## Recovery sequence

Stop or fence writes, choose the latest verified backup, restore to an isolated replacement, validate application/security behavior, update the secret-managed database endpoint, verify `/ready` and authenticated smoke behavior, then re-enable traffic gradually.
