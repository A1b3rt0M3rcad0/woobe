import hashlib
import json
from dataclasses import asdict
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from modules.artifacts.application.contracts.api import SourceReference
from modules.artifacts.domain.models import ArtifactError, Locator, Scope, SourceManifest, SourceRef, opaque_id
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.models import ArtifactRunSourceManifestModel, ArtifactRunSourceModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


def source_ref_json(source: SourceRef | SourceReference) -> dict:
    value = asdict(source) if isinstance(source, SourceRef) else source
    return SourceReference.model_validate(value).model_dump(mode='json')


def source_ref_fingerprint(value: dict) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def source_ref_entity(value: dict) -> SourceRef:
    data = SourceReference.model_validate(value).model_dump(mode='python')
    if data['locator'] is not None:
        data['locator'] = Locator(**data['locator'])
    return SourceRef(**data)


class RunSourceRepository:
    """Durable, idempotent journal containing only sources actually read by a Run."""

    def __init__(self, uow: ArtifactsUnitOfWork):
        self._uow = uow
        self._catalog = CatalogRepository(uow)

    async def record(self, scope: Scope, workspace_id: str, run_id: str,
                     catalog_version: int, source: SourceRef) -> SourceManifest:
        opaque_id(run_id)
        workspace = await self._catalog.workspace_row(scope, workspace_id, lock=True)
        if type(catalog_version) is not int or not 0 <= catalog_version <= workspace.catalog_version:
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Run catalog snapshot is unavailable')

        manifest_id = str(uuid4())
        await self._uow.session.execute(insert(ArtifactRunSourceManifestModel).values(
            id=manifest_id, project_id=UUID(scope.project_id), environment=scope.environment.value,
            workspace_id=workspace_id, run_id=run_id, catalog_version=catalog_version,
        ).on_conflict_do_nothing(constraint='uq_artifact_run_source_manifest'))
        manifest = (await self._uow.session.execute(select(ArtifactRunSourceManifestModel).where(
            ArtifactRunSourceManifestModel.project_id == UUID(scope.project_id),
            ArtifactRunSourceManifestModel.environment == scope.environment.value,
            ArtifactRunSourceManifestModel.workspace_id == workspace_id,
            ArtifactRunSourceManifestModel.run_id == run_id,
        ).with_for_update())).scalar_one()
        if manifest.catalog_version != catalog_version:
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Run source manifest is pinned to another catalog snapshot')

        value = source_ref_json(source)
        fingerprint = source_ref_fingerprint(value)
        await self._uow.session.execute(insert(ArtifactRunSourceModel).values(
            id=str(uuid4()), manifest_id=manifest.id, source_fingerprint=fingerprint, source_ref=value,
        ).on_conflict_do_nothing(constraint='uq_artifact_run_source_fingerprint'))
        rows = (await self._uow.session.execute(select(ArtifactRunSourceModel.source_ref).where(
            ArtifactRunSourceModel.manifest_id == manifest.id).order_by(ArtifactRunSourceModel.id))).scalars()
        sources = tuple(source_ref_entity(item) for item in rows)
        return SourceManifest(workspace_id=workspace_id, catalog_version=catalog_version, sources=sources)

    async def get(self, scope: Scope, workspace_id: str, run_id: str) -> SourceManifest | None:
        opaque_id(run_id)
        statement = select(ArtifactRunSourceManifestModel).where(
            ArtifactRunSourceManifestModel.project_id == UUID(scope.project_id),
            ArtifactRunSourceManifestModel.environment == scope.environment.value,
            ArtifactRunSourceManifestModel.workspace_id == workspace_id,
            ArtifactRunSourceManifestModel.run_id == run_id,
        )
        manifest = (await self._uow.session.execute(statement)).scalar_one_or_none()
        if manifest is None:
            return None
        rows = (await self._uow.session.execute(select(ArtifactRunSourceModel.source_ref).where(
            ArtifactRunSourceModel.manifest_id == manifest.id).order_by(ArtifactRunSourceModel.id))).scalars()
        sources = tuple(source_ref_entity(item) for item in rows)
        return SourceManifest(workspace_id=workspace_id, catalog_version=manifest.catalog_version, sources=sources)
