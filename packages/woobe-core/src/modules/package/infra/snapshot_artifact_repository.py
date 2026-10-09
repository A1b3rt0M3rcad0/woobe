"""Package owns retained artifacts; lifecycle owners receive verified evidence."""

import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from modules.package.application.asac_definition import (
    DEFINITION_SCOPE,
    portable_definition,
    provider_definition_digests,
)
from modules.package.domain.errors import PackageError
from modules.package.infra.models import PackageSnapshotArtifactModel
from modules.package.infra.receipts import authorize_phase


def snapshot_evidence(row):
    return {
        "artifact_id": str(row.id),
        "artifact_digest": "sha256:" + row.artifact_digest,
        "definition_digest": row.definition_digest,
        "definition_digest_scope": DEFINITION_SCOPE,
        "component_digests": row.component_digests,
        "provider_digests": provider_definition_digests(row.manifest),
        "manifest": row.manifest,
        "inventory": row.inventory,
        "size_bytes": row.size_bytes,
    }


class PackageSnapshotArtifactRepository:
    def __init__(self, sessions, artifacts, exports):
        self.sessions, self.artifacts, self.exports = sessions, artifacts, exports

    @property
    def authors(self):
        from modules.package.infra.author_artifact_repository import PackageAuthorArtifactRepository
        return PackageAuthorArtifactRepository(self.sessions, self.artifacts.storage)

    def _verify(self, upload):
        with self.artifacts.capture_record(upload) as bundle:
            digest, components = portable_definition(bundle)
            return digest, components

    async def retain_upload(self, *, project_id, principal, upload_id, artifact_digest):
        upload = await self.artifacts.get_record(
            project_id=project_id, principal=principal, upload_id=UUID(str(upload_id))
        )
        if artifact_digest != "sha256:" + upload.artifact_digest:
            raise PackageError(
                "ASAC_ARTIFACT_MISMATCH",
                "Upload differs from the expected closed object",
            )
        definition, components = await asyncio.to_thread(self._verify, upload)
        async with self.sessions.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            values = dict(
                project_id=project_id,
                artifact_digest=upload.artifact_digest,
                definition_digest=definition,
                component_digests=components,
                storage_key=upload.storage_key,
                manifest=upload.manifest,
                inventory=upload.inventory,
                size_bytes=upload.size_bytes,
            )
            await session.execute(
                insert(PackageSnapshotArtifactModel)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["project_id", "artifact_digest"]
                )
            )
            row = await session.scalar(
                select(PackageSnapshotArtifactModel).where(
                    PackageSnapshotArtifactModel.project_id == project_id,
                    PackageSnapshotArtifactModel.artifact_digest
                    == upload.artifact_digest,
                )
            )
            if row.inventory != upload.inventory or row.definition_digest != definition:
                raise PackageError(
                    "ASAC_ARTIFACT_MISMATCH",
                    "Retained digest has different verified bytes",
                )
            return snapshot_evidence(row)

    async def retain_export(self, *, project_id, principal, export_id):
        import io
        from modules.package.infra.bundles import receive_archive

        receipt, content = await self.exports.capture_artifact(
            project_id=project_id, principal=principal, export_id=UUID(str(export_id))
        )

        def verify():
            with receive_archive(io.BytesIO(content), locked=True) as bundle:
                digest, components = portable_definition(bundle)
                return digest, components, bundle.graph.manifest, bundle.inventory

        definition, components, manifest, inventory = await asyncio.to_thread(verify)
        # The retained row points to the immutable export object already verified
        # against its transport digest; origin remains a separate observation.
        async with self.sessions.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            from modules.package.infra.models import PackageExportModel

            exported = await session.get(PackageExportModel, UUID(str(export_id)))
            values = dict(
                project_id=project_id,
                artifact_digest=receipt["artifact_digest"],
                definition_digest=definition,
                component_digests=components,
                storage_key=exported.storage_key,
                manifest=manifest,
                inventory=inventory,
                size_bytes=receipt["size_bytes"],
            )
            await session.execute(
                insert(PackageSnapshotArtifactModel)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=["project_id", "artifact_digest"]
                )
            )
            row = await session.scalar(
                select(PackageSnapshotArtifactModel).where(
                    PackageSnapshotArtifactModel.project_id == project_id,
                    PackageSnapshotArtifactModel.artifact_digest
                    == receipt["artifact_digest"],
                )
            )
            if row.inventory != inventory or row.definition_digest != definition:
                raise PackageError(
                    "ASAC_ARTIFACT_MISMATCH",
                    "Export conflicts with a retained closed object",
                )
            return {
                **snapshot_evidence(row),
                "source": receipt["source"],
                "kind": exported.source["kind"],
                "resource_id": exported.source["target_id"],
            }

    async def get(self, *, project_id, principal, artifact_id):
        async with self.sessions.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            row = await session.get(
                PackageSnapshotArtifactModel, UUID(str(artifact_id))
            )
            if row is None or row.project_id != project_id:
                raise PackageError(
                    "ASAC_ARTIFACT_UNAVAILABLE",
                    "Retained object is unavailable in this Project",
                )
            return snapshot_evidence(row)

    async def capture(self, *, project_id, principal, artifact_id):
        async with self.sessions.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            row = await session.get(
                PackageSnapshotArtifactModel, UUID(str(artifact_id))
            )
            if row is None or row.project_id != project_id:
                raise PackageError(
                    "ASAC_ARTIFACT_UNAVAILABLE",
                    "Retained object is unavailable in this Project",
                )
        # Inventory revalidation is mandatory even after metadata lookup succeeds.
        return await asyncio.to_thread(self.artifacts.capture_record, row)

    async def editor_source(self, *, project_id, principal, artifact_id):
        from modules.package.infra.editor_artifacts import editor_files
        bundle=await self.capture(project_id=project_id,principal=principal,artifact_id=artifact_id)
        def read():
            with bundle:
                return editor_files(bundle)
        return await asyncio.to_thread(read)

    async def retain_edits(self, *, project_id, principal, artifact_id, files):
        from modules.package.infra.editor_artifacts import edited_archive
        bundle=await self.capture(project_id=project_id,principal=principal,artifact_id=artifact_id)
        archive=await asyncio.to_thread(edited_archive,bundle,files)
        try:
            upload=await self.artifacts.upload(project_id=project_id,principal=principal,stream=archive,locked=True)
        finally:
            archive.close()
        return await self.retain_upload(project_id=project_id,principal=principal,
            upload_id=upload['upload_id'],artifact_digest='sha256:'+upload['artifact_digest'])

    async def editor_bindings(self, *, project_id,principal,export_id,artifact_id,resource_uid,component_uids):
        from uuid import uuid5
        from modules.package.infra.models import PackageExportModel, PackageResourceBindingModel
        evidence=await self.get(project_id=project_id,principal=principal,artifact_id=artifact_id)
        async with self.sessions.begin() as session:
            source=await session.get(PackageExportModel,UUID(str(export_id)))
            if source is None or source.project_id!=project_id:
                raise PackageError('ASAC_EDITOR_ORIGIN_UNAVAILABLE','Original owner capture is unavailable')
            await self.exports.authorize(project_id,principal,source.source)
            registry=uuid5(UUID(resource_uid),'web-registry')
            native=source.source.get('resource_bindings',{})
            # Only captured native root identities can be associated. This
            # reserves a registry mapping, never a synchronized definition/base.
            for key,uid in component_uids.items():
                binding=native.get(key,{})
                if binding.get('kind') not in {'Agent','Network'}:
                    continue
                identifier=UUID(binding['resource_id'])
                await session.execute(insert(PackageResourceBindingModel).values(
                    project_id=project_id,registry_id=registry,resource_uid=UUID(uid),
                    resource_id=identifier,kind=binding['kind']).on_conflict_do_nothing(
                        index_elements=['project_id','registry_id','resource_uid']))
                row=await session.scalar(select(PackageResourceBindingModel).where(
                    PackageResourceBindingModel.project_id==project_id,
                    PackageResourceBindingModel.registry_id==registry,
                    PackageResourceBindingModel.resource_uid==UUID(uid)))
                if row is not None and (row.resource_id!=identifier or row.kind!=binding['kind']):
                    raise PackageError('ASAC_EDITOR_IDENTITY_CONFLICT','Web registry has another native binding')
            credentials={alias:identifier for identifier,alias in source.source.get('credential_bindings',{}).items()}
        spec={};requirements=evidence['manifest']['spec'].get('requires',{})
        for group in ('credentials','project_environment','secrets','knowledge'):
            values={}
            for item in requirements.get(group,[]):
                alias=item.get('key') if group=='project_environment' else item.get('ref')
                if group=='credentials':
                    if alias not in credentials:
                        raise PackageError('ASAC_EDITOR_BINDING_UNAVAILABLE','An explicit Provider binding is required')
                    values[alias]={'credential_id':credentials[alias]}
                elif group=='knowledge':
                    raise PackageError('ASAC_EDITOR_BINDING_UNAVAILABLE','Open a portable Knowledge closure before Web Stage')
                else:
                    values[alias]={'existing_key':alias}
            spec[group]=values
        return {'registry_id':str(registry),'bindings':{'format':'woobe-package','schema_version':'1.0',
            'kind':'ImportBindings','metadata':{'name':'Web Candidate'},'spec':spec}}

    async def transfer(self, *, project_id, principal, artifact_id):
        """Revalidate a retained closure and produce a bounded deterministic transfer."""
        import io
        from hashlib import sha256
        from modules.package.domain.bundle import MAX_ARCHIVE_BYTES

        class BoundedArchive(io.BytesIO):
            def write(self, value):
                if self.tell() + len(value) > MAX_ARCHIVE_BYTES:
                    raise PackageError(
                        "ASAC_ARTIFACT_LIMIT", "Retained transfer exceeds 128 MiB"
                    )
                return super().write(value)

        try:
            bundle = await self.capture(
                project_id=project_id, principal=principal, artifact_id=artifact_id
            )
        except FileNotFoundError:
            raise PackageError(
                "ASAC_OBJECT_UNAVAILABLE",
                "Retained metadata exists but its executable object is unavailable",
            ) from None

        def encode():
            with bundle, BoundedArchive() as archive:
                definition, _ = portable_definition(bundle)
                bundle.archive(archive, include_lock=True)
                content = archive.getvalue()
                return {
                    "artifact_digest": "sha256:" + bundle.artifact_digest,
                    "definition_digest": definition,
                    "inventory": bundle.inventory,
                    "transport_digest": sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }, content

        return await asyncio.to_thread(encode)
