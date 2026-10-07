"""Durable, scoped export receipts backed by captured native owner definitions."""

import asyncio
import yaml
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
import tempfile
from uuid import UUID, uuid4

from modules.package.domain.bundle import MAX_ARCHIVE_BYTES
from modules.package.application.semantic_definition import semantic_digests
from modules.package.domain.errors import PackageError
from modules.package.infra.bundles import snapshot_directory
from modules.package.infra.models import PackageExportModel
from modules.package.infra.operation_repository import as_utc
from modules.package.infra.receipts import authorize_phase
from shared.infra.admin_idempotency import principal_identity


class PackageExportRepository:
    def __init__(
        self,
        sessions,
        storage,
        agents,
        networks,
        environment,
        *,
        projection_factory,
        reference_collector,
        lifetime_seconds=86400,
        registry=None,
    ):
        self.sessions, self.storage, self.agents, self.networks = (
            sessions,
            storage,
            agents,
            networks,
        )
        self.environment, self.projection_factory, self.reference_collector = (
            environment,
            projection_factory,
            reference_collector,
        )
        self.lifetime_seconds = lifetime_seconds
        self.registry = registry

    async def authorize(self, project_id, principal, source):
        async with self.sessions.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            identifiers = {
                "agent_id" if source["kind"] == "Agent" else "network_id": source[
                    "target_id"
                ]
            }
            await authorize_phase(
                session,
                principal,
                project_id,
                source["kind"].lower() + ":read",
                path_params=identifiers,
            )
            for permission, paths in source.get("dependency_permissions", []):
                await authorize_phase(
                    session, principal, project_id, permission, path_params=paths
                )

    def _store(self, projection, key):
        with tempfile.TemporaryDirectory(prefix="woobe-export-") as directory:
            root = Path(directory)
            for path, content in projection.files.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with target.open("xb") as output:
                    output.write(content)
            with (
                snapshot_directory(root) as bundle,
                tempfile.TemporaryFile() as archive,
            ):
                bundle.archive(archive, include_lock=True)
                archive.seek(0)
                stored = self.storage.put(key, archive)
                return bundle.artifact_digest, bundle.inventory, stored

    async def create(self, *, project_id, principal, request):
        selector = {
            "source": request.source,
            "snapshot_id": UUID(request.snapshot_id) if request.snapshot_id else None,
        }
        if request.release_version is not None:
            selector["release_version"] = request.release_version
        if request.kind == "Agent":
            captured = (
                await self.agents.capture(
                    project_id=project_id,
                    principal=principal,
                    sources=[{"agent_id": UUID(request.target_id), **selector}],
                )
            )[0]
            agents = [captured]
        else:
            captured = await self.networks.capture(
                project_id=project_id,
                principal=principal,
                network_id=UUID(request.target_id),
                **selector,
            )
            agents = captured["agents"]
        keys = set()
        for agent in agents:
            for tool in agent["tools"]:
                environment, _ = self.reference_collector(
                    [tool["config"], tool["permissions"]]
                )
                keys.update(environment)
        kinds = await self.environment.capture(
            project_id=project_id, principal=principal, keys=keys
        )
        projection = self.projection_factory(
            knowledge_mode=request.knowledge,
            environment_kinds=kinds,
            development=request.development,
        ).finish(
            kind=request.kind,
            captured=captured,
            name=request.name,
            version=request.version,
        )
        documents = [document for _, document in projection.document_reads]
        if documents:
            contents = await self.agents.read_documents(
                project_id=project_id, principal=principal, documents=documents
            )
            for (path, _), content in zip(
                projection.document_reads, contents, strict=True
            ):
                projection.add_bytes(path, content)
        if request.development and self.registry is not None:
            async with self.sessions.begin() as session:
                for key, binding in projection.native_bindings.items():
                    evidence = await self.registry.inspect(
                        session,
                        project_id=project_id,
                        principal=principal,
                        kind=binding["kind"],
                        resource_id=binding["resource_id"],
                    )
                    binding["revision"] = evidence["revision"]
                    binding["identifiers"] = {field: evidence[field] for field in ("skill_id", "collection_id") if evidence.get(field)}
                    if evidence.get("owner_agent_id"):
                        binding["owner_agent_id"] = evidence["owner_agent_id"]
                    if binding["kind"] == "Tool":
                        native = evidence["portable_tool"]
                        exported = projection.documents[key]
                        binding["native_matches"] = exported["metadata"][
                            "name"
                        ] == native["name"] and all(
                            native[field] == value
                            for field, value in exported["spec"].items()
                        )
        identifier = uuid4()
        storage_key = f"projects/{project_id}/exports/{identifier}.tar.gz"
        source = {
            "kind": request.kind,
            "target_id": request.target_id,
            "captured": captured["source"],
            "resource_bindings": projection.native_bindings
            if request.development
            else {},
            "credential_bindings": projection.credential_aliases
            if request.development
            else {},
            "knowledge": request.knowledge,
            "environment": request.source,
            "package_name": projection.package_name,
            "package_version": projection.package_version,
            "self_contained": request.knowledge == "portable"
            or not any(agent["knowledge"] for agent in agents),
        }
        permissions = []
        for agent in agents:
            permissions.append(
                ("agent:read", {"agent_id": agent["source"]["agent_id"]})
            )
            for credential_identifier in agent["credentials"]:
                permissions.append(
                    ("provider:read", {"provider_credential_id": credential_identifier})
                )
            for tool in agent["tools"]:
                permissions.append(("tool:read", {"tool_id": tool["id"]}))
            for skill in agent["skills"]:
                permissions.append(("skill:read", {"skill_id": skill["skill_id"]}))
            if knowledge := agent["knowledge"]:
                permissions.append(
                    (
                        "knowledge:read",
                        {"vector_snapshot_id": str(knowledge["vector"]["id"])},
                    )
                )
                permissions.extend(
                    ("knowledge:read", {"document_id": str(document["id"])})
                    for document in knowledge["documents"]
                )
        if keys:
            permissions.append(("project:environment:read", {}))
        source["dependency_permissions"] = permissions
        # All source SQL snapshots are closed before documents/archive/storage IO.
        await self.authorize(project_id, principal, source)
        digest, inventory, stored = await asyncio.to_thread(
            self._store, projection, storage_key
        )
        if request.development:
            # The closed bundle supplies a canonical dependency-first order and
            # verified file hashes. These signatures qualify frozen reuse later.
            source["semantic_digests"] = await asyncio.to_thread(
                self._semantic_evidence, projection, inventory
            )
        record = PackageExportModel(
            id=identifier,
            project_id=project_id,
            actor=principal_identity(principal),
            source=source,
            artifact_digest=digest,
            transport_digest=stored["transport_digest"],
            storage_key=storage_key,
            size_bytes=stored["size_bytes"],
            inventory=inventory,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.lifetime_seconds),
        )
        await self.authorize(project_id, principal, source)
        async with self.sessions.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            session.add(record)
            await session.flush()
        return self.receipt(record)

    @staticmethod
    def _semantic_evidence(projection, inventory):
        from modules.package.domain.bundle import resolve_graph

        manifest = yaml.safe_load(projection.files["woobe.yaml"])
        graph = resolve_graph(
            manifest,
            {key + ".yaml": value for key, value in projection.documents.items()},
        )
        return semantic_digests(
            graph.components,
            graph.order,
            graph.paths,
            inventory,
            {
                alias: resource_id
                for resource_id, alias in projection.credential_aliases.items()
            },
        )

    @staticmethod
    def receipt(record):
        return {
            "package_schema_version": "1.0",
            "export_id": str(record.id),
            "project_id": str(record.project_id),
            "artifact_digest": record.artifact_digest,
            "transport_digest": record.transport_digest,
            "size_bytes": record.size_bytes,
            "inventory": record.inventory,
            "closure_complete": True,
            "self_contained": record.source["self_contained"],
            "knowledge": record.source["knowledge"],
            "expires_at": record.expires_at.isoformat(),
            "source": {
                "environment": record.source.get("environment"),
                **record.source["captured"],
            },
            "resource_bindings": record.source.get("resource_bindings", {}),
            "credential_bindings": {
                alias: resource_id
                for resource_id, alias in record.source.get(
                    "credential_bindings", {}
                ).items()
            },
            "name": record.source.get("package_name"),
            "version": record.source.get("package_version"),
        }

    async def capture_artifact(self, *, project_id, principal, export_id):
        async with self.sessions.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            record = await session.get(PackageExportModel, export_id)
            if (
                record is None
                or record.project_id != project_id
                or record.actor != principal_identity(principal)
            ):
                raise PackageError("PACKAGE_EXPORT_NOT_FOUND", "Export is unavailable")
            if as_utc(record.expires_at) <= datetime.now(UTC):
                raise PackageError("PACKAGE_EXPORT_EXPIRED", "Export has expired")
        await self.authorize(project_id, principal, record.source)

        # Capture and authenticate the complete compressed stream before sending headers.
        def read():
            with self.storage.open(record.storage_key) as stream:
                content = stream.read(MAX_ARCHIVE_BYTES + 1)
            if (
                len(content) != record.size_bytes
                or len(content) > MAX_ARCHIVE_BYTES
                or sha256(content).hexdigest() != record.transport_digest
            ):
                raise PackageError(
                    "PACKAGE_ARTIFACT_CHANGED",
                    "Export failed its transport integrity check",
                )
            return content

        return self.receipt(record), await asyncio.to_thread(read)
