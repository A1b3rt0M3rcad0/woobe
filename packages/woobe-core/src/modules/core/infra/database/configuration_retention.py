"""Bounded cleanup; never delete a version referenced by a live Run lease."""
from sqlalchemy import select, delete, func, cast, String, exists
from modules.core.infra.database.configuration_models import ConfigurationLeaseModel as Lease, ConfigurationValueVersionModel as Version
from modules.core.infra.database.configuration_store import now


async def purge_configuration_retention(session, *, limit=500):
    instant = now()
    lease_ids = select(Lease.id).where(Lease.expires_at <= instant).order_by(Lease.expires_at).limit(limit).with_for_update(skip_locked=True)
    removed_leases = await session.execute(delete(Lease).where(Lease.id.in_(lease_ids)))
    pinned = exists(select(Lease.id).where(Lease.project_id == Version.project_id, Lease.expires_at > instant,
        Lease.pins.contains(func.jsonb_build_array(func.jsonb_build_object(
            "key_id", cast(Version.key_id, String), "version", cast(Version.value_version, String))))))
    version_ids = select(Version.id).where(Version.expires_at <= instant, ~pinned).order_by(Version.expires_at).limit(limit).with_for_update(skip_locked=True)
    removed_versions = await session.execute(delete(Version).where(Version.id.in_(version_ids)))
    return {"expired_leases": removed_leases.rowcount, "expired_versions": removed_versions.rowcount}
