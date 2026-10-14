"""Bounded administrative plans; owner adapters alone read and cut over sources."""
from collections import Counter
from copy import deepcopy
from uuid import UUID

from sqlalchemy import select, func

from modules.core.domain.project_configuration import canonical_destination
from modules.core.infra.database.configuration_fleet import assert_configuration_bridge
from modules.core.infra.database.configuration_models import ConfigurationMigrationModel, ConfigurationProcessModel
from modules.core.infra.database.configuration_store import ConfigurationStore
from shared.contracts.project_configuration import ConfigurationError


class ConfigurationMigrationService:
    def __init__(self, session, *, encryption_key, inventory, cutover, assert_quiescent=None):
        self.session = session
        self.inventory = inventory
        self.cutover = cutover
        self.assert_quiescent = assert_quiescent
        self.store = ConfigurationStore(session, encryption_key=encryption_key)

    async def fleet(self, *, project_id, limit=100, offset=0):
        if not 1 <= limit <= 200 or offset < 0:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        rows = (await self.session.scalars(select(ConfigurationProcessModel).where(
            ConfigurationProcessModel.expires_at > func.clock_timestamp()).order_by(
                ConfigurationProcessModel.process_identity).limit(limit + 1).offset(offset))).all()
        return {"items": [{"identity": row.process_identity, "capabilities": row.capabilities,
                "expires_at": row.expires_at.isoformat()} for row in rows[:limit]],
            "offset": offset, "limit": limit, "has_more": len(rows) > limit,
            "requires_operator_inventory": True}

    async def preview(self, *, project_id, source_kind="provider_credential", after_id=None, limit=100):
        if source_kind not in {"provider_credential", "secret", "tool"} or not 1 <= limit <= 200:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        result = await self.inventory(self.session, project_id=project_id, after_id=after_id, limit=limit,
            **({"source_kind": source_kind} if source_kind != "provider_credential" else {}))
        for item in result["items"]:
            try:
                for value in item["destinations"]:
                    canonical_destination(value)
            except ConfigurationError as error:
                item.update(state="blocked", code=error.code, destinations=[])
                item.pop("closure", None)
        result["scope"] = {"secret": "secrets", "tool": "tools", "provider_credential": "provider_credentials"}[source_kind]
        result["counts"] = dict(Counter(item["state"] for item in result["items"]))
        return result

    async def create(self, *, project_id, migration_id, actor, source_kind="provider_credential", after_id=None, limit=100):
        await self.store.lock_project(project_id)
        existing = await self.session.scalar(select(ConfigurationMigrationModel).where(ConfigurationMigrationModel.id == migration_id))
        request = {"after_id": str(after_id) if after_id else None, "limit": limit,
            **({"source_kind": source_kind} if source_kind != "provider_credential" else {})}
        if existing is not None:
            if existing.project_id != project_id or existing.plan["request"] != request or existing.actor != actor:
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            return self.report(existing)
        preview = await self.preview(project_id=project_id, source_kind=source_kind, after_id=after_id, limit=limit)
        row = ConfigurationMigrationModel(id=migration_id, project_id=project_id, actor=actor,
            state="eligible" if preview["items"] else "completed", revision=1,
            plan={"request": request, **preview}, progress={"items": deepcopy(preview["items"])})
        self.session.add(row)
        await self.session.flush()
        await self.store.audit(project_id, "migration.planned", actor, migration_id=str(migration_id), count=len(preview["items"]))
        return self.report(row)

    @staticmethod
    def report(row, *, offset=0, limit=50):
        items = row.progress["items"]
        return {"id": str(row.id), "state": row.state, "revision": row.revision,
            "scope": row.plan["scope"], "next_after": row.plan["next_after"],
            "items": items[offset:offset + limit], "total": len(items), "offset": offset, "limit": limit,
            "counts": dict(Counter(item["state"] for item in items))}

    async def load(self, *, project_id, migration_id):
        row = await self.session.scalar(select(ConfigurationMigrationModel).where(
            ConfigurationMigrationModel.id == migration_id, ConfigurationMigrationModel.project_id == project_id).with_for_update())
        if row is None:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        return row

    async def status(self, *, project_id, migration_id, offset=0, limit=50):
        if offset < 0 or not 1 <= limit <= 200:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        return self.report(await self.load(project_id=project_id, migration_id=migration_id), offset=offset, limit=limit)

    async def advance(self, *, project_id, migration_id, actor, expected_revision, required_processes,
                      old_processes_drained, limit=10, pause=False):
        if not 1 <= limit <= 20 or type(pause) is not bool or type(old_processes_drained) is not bool:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        # Same order as acceptance and job creation: Project before source/job.
        await self.store.lock_project(project_id)
        row = await self.load(project_id=project_id, migration_id=migration_id)
        request = {"revision": expected_revision, "processes": sorted(required_processes),
            "drained": old_processes_drained, "limit": limit, "pause": pause, "actor": actor}
        # A lost response can be recovered without reapplying an accepted batch.
        if row.progress.get("last_request") == request:
            return self.report(row)
        if row.revision != expected_revision:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT")
        progress = deepcopy(row.progress)
        if pause:
            row.state = "paused"
        else:
            if not old_processes_drained:
                raise ConfigurationError("CONFIG_BRIDGE_REQUIRED")
            await assert_configuration_bridge(self.session, required_processes=required_processes)
            if self.assert_quiescent is not None:
                await self.assert_quiescent(self.session, project_id=project_id)
            pending = [item for item in progress["items"] if item["state"] == "eligible"][:limit]
            for item in pending:
                try:
                    async with self.session.begin_nested():
                        source = ({"secret_id": UUID(item["id"]), "expected_closure": item["closure"]}
                            if item["kind"] == "secret" else {"credential_id": UUID(item["id"]), "destinations": item["destinations"]})
                        if item["kind"] == "tool":
                            source = {"tool_id": UUID(item["id"]), "destinations": item["destinations"]}
                        result = await self.cutover(self.session, project_id=project_id, **source,
                            expected_revision=item["revision"], required_processes=required_processes, actor=actor)
                    material = result.get("material", "unchanged")
                    item.update(state="completed" if result.get("state") == "completed" or material in {"present", "unchanged"} else "cutover", material=material)
                except ConfigurationError as error:
                    item.update(state="blocked", code=error.code)
            states = {item["state"] for item in progress["items"]}
            row.state = "eligible" if "eligible" in states else "blocked" if states & {"blocked", "cutover"} else "completed"
        progress["last_request"] = request
        row.progress = progress
        row.revision += 1
        await self.session.flush()
        await self.store.audit(project_id, "migration.advanced", actor, migration_id=str(row.id), state=row.state, revision=row.revision)
        return self.report(row)
