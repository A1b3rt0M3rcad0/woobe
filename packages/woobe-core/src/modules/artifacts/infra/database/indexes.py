from collections import Counter
import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, select

from modules.artifacts.application.contracts.api import SourceReference
from modules.artifacts.application.contracts.indexes import DocumentIndexView, DocumentNodeView, ReadIndex
from modules.artifacts.application.document_codec import serialized_identity
from modules.artifacts.application.services.structural_index import merge_ranges
from modules.artifacts.domain.models import ArtifactError, ArtifactRef, DocumentIndex, DocumentNode
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.index_models import ArtifactDocumentIndexModel as IndexRoot, ArtifactDocumentNodeModel as Node
from modules.artifacts.infra.database.models import ArtifactEventModel, ProcessingJobModel
from modules.artifacts.infra.database.representation_models import (
    ArtifactRepresentationEntryModel as Entry, ArtifactRepresentationSetModel as Generation,
    ArtifactSourceBlockModel as Block, ArtifactStoredObjectModel as StoredObject,
)


def index_identity(job_id):
    return str(uuid5(NAMESPACE_URL, 'woobe:document-index:v1:' + job_id))


def index_view(row):
    return DocumentIndexView(**{name: getattr(row, name) for name in (
        'id', 'workspace_id', 'artifact_id', 'revision_id', 'representation_set_id', 'source_sha256',
        'recipe_fingerprint', 'processing_fingerprint', 'engine', 'engine_version', 'tree_kind', 'coverage',
        'root_node_id', 'node_count', 'source_block_count', 'max_depth', 'manifest_sha256', 'created_at')})


def index_plan(row):
    return {'document_index_id': row.id, 'representation_set_id': row.representation_set_id,
            'index_manifest_sha256': row.manifest_sha256}


class DocumentIndexRepository:
    def __init__(self, uow):
        self._uow, self._catalog = uow, CatalogRepository(uow)

    async def prepare(self, request):
        lease = request.lease
        job = await self._uow.session.get(ProcessingJobModel, lease.id)
        generation = await self._uow.session.get(Generation, request.representation_set_id)
        if (job is None or lease.recipe.mode != 'extract_index' or generation is None
            or (generation.workspace_id, generation.artifact_id, generation.revision_id, generation.processing_fingerprint) != (
                job.workspace_id, job.artifact_id, job.revision_id, job.processing_fingerprint)
            or not generation.sealed or generation.status not in {'building', 'ready'}
            or (generation.status == 'building' and generation.job_id != job.id)):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Document index source generation is unavailable')
        selected = lease.recipe.indexer
        engines = [selected.name]
        if lease.recipe.parameters.indexer_fallback == 'structural':
            engines.append('structural')
        reusable = (await self._uow.session.execute(select(IndexRoot).where(
            IndexRoot.workspace_id == job.workspace_id, IndexRoot.representation_set_id == generation.id,
            IndexRoot.processing_fingerprint == job.processing_fingerprint,
            IndexRoot.engine.in_(engines), IndexRoot.status == 'ready').order_by(
                IndexRoot.engine != selected.name, IndexRoot.id).limit(1))).scalar_one_or_none()
        if reusable is not None:
            return {**index_plan(reusable), 'reused': True, 'sealed': True}
        identity = index_identity(lease.id)
        row = await self._uow.session.get(IndexRoot, identity, with_for_update=True)
        if row is None:
            row = IndexRoot(id=identity, project_id=job.project_id, environment=job.environment,
                workspace_id=job.workspace_id, artifact_id=job.artifact_id, revision_id=job.revision_id,
                representation_set_id=generation.id, job_id=job.id, source_sha256=generation.source_sha256,
                recipe_fingerprint=job.recipe_fingerprint, processing_fingerprint=job.processing_fingerprint,
                engine=selected.name, engine_version=selected.version, build_fencing_token=lease.fencing_token)
            self._uow.session.add(row)
            await self._uow.session.flush()
        if row.status != 'building':
            raise ArtifactError('REPRESENTATION_NOT_READY', 'Document index cannot be rebuilt')
        if row.sealed:
            return {**index_plan(row), 'reused': False, 'sealed': True}
        if row.build_fencing_token != lease.fencing_token:
            await self._uow.session.execute(delete(Node).where(Node.document_index_id == row.id))
            row.build_fencing_token = lease.fencing_token
        canonical = (await self._uow.session.execute(select(StoredObject).join(Entry,
            Entry.object_id == StoredObject.id).where(Entry.representation_set_id == generation.id,
            Entry.role == 'structure', StoredObject.state.in_(['stored', 'referenced'])))).scalar_one_or_none()
        if canonical is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Canonical structure receipt is unavailable')
        return {**index_plan(row), 'reused': False, 'sealed': False, 'canonical': {
            'key': canonical.object_key, 'sha256': canonical.sha256, 'size_bytes': canonical.size_bytes,
            'version_id': canonical.storage_version_id}}

    async def _building(self, request):
        row = await self._uow.session.get(IndexRoot, request.index_id, with_for_update=True)
        if row is None or (row.workspace_id, row.job_id, row.representation_set_id) != (
                request.lease.workspace_id, request.lease.id, request.representation_set_id):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Document index generation is unavailable')
        if row.status != 'building' or row.sealed or row.build_fencing_token != request.lease.fencing_token:
            raise ArtifactError('ARTIFACT_REVISION_CONFLICT', 'Document index metadata is sealed or owned by another attempt')
        return row

    async def metadata(self, request):
        row = await self._building(request)
        items = request.value.get('nodes') if isinstance(request.value, dict) else None
        if not isinstance(items, list) or not 1 <= len(items) <= 1000 or len(json.dumps(items).encode()) > 4_194_304:
            raise ValueError('Document index metadata batch exceeds its bounds')
        for item in items:
            if (item.get('workspace_id'), item.get('representation_set_id'), item.get('document_index_id')) != (
                    row.workspace_id, row.representation_set_id, row.id):
                raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Document node metadata crosses its index scope')
            existing = await self._uow.session.get(Node, item['id'])
            if existing is not None:
                if any(getattr(existing, name) != value for name, value in item.items()):
                    raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Document node metadata replay differs')
            else:
                self._uow.session.add(Node(**item))
        await self._uow.session.flush()
        return {'accepted': len(items)}

    async def seal(self, request):
        row = await self._building(request)
        value = request.value
        selected = request.lease.recipe.indexer
        actual_engine = value.get('engine', row.engine)
        actual_version = value.get('engine_version', row.engine_version)
        selected_engine = (actual_engine, actual_version) == (selected.name, selected.version)
        authorized_fallback = (actual_engine, actual_version) == ('structural', '1')
        if not selected_engine and not (authorized_fallback
                and request.lease.recipe.parameters.indexer_fallback == 'structural'):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index engine differs from its explicit recipe')
        row.engine, row.engine_version = actual_engine, actual_version
        generation = await self._uow.session.get(Generation, row.representation_set_id)
        members = (await self._uow.session.execute(select(Node).where(Node.document_index_id == row.id).order_by(Node.id))).scalars().all()
        metadata = [{column.name: getattr(member, column.name) for column in Node.__table__.columns
                     if column.name != 'created_at'} for member in members]
        _, digest = serialized_identity(metadata, 536_870_912)
        if digest != value['metadata_fingerprint'] or len(members) != value['node_count']:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document node manifest is inconsistent')
        try:
            nodes = tuple(DocumentNode(member.id, member.title, (member.block_id,) if member.block_id else (),
                member.parent_id, kind=member.kind, ordinal=member.ordinal,
                source_ranges=tuple(tuple(interval) for interval in member.source_ranges),
                block_sha256=member.block_sha256, page_index=member.page_index, depth=member.depth) for member in members)
            tree = DocumentIndex(row.id, row.representation_set_id, row.engine, row.engine_version, nodes,
                                 value['tree_kind'], generation.block_count, generation.coverage)
        except ValueError as error:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index tree metadata is invalid') from error
        actual_blocks = (await self._uow.session.execute(select(Block.block_id, Block.ordinal, Block.sha256, Block.source_locator, Block.kind).where(
            Block.representation_set_id == generation.id))).all()
        source = {block.block_id: block for block in actual_blocks}
        if {node.block_id for node in members if node.block_id} != set(source):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index does not own every canonical source block')
        counts = Counter(member.parent_id for member in members if member.parent_id is not None)
        ranges = {member.id: [] for member in members}
        for member in members:
            if counts[member.id] != member.children_count:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document node child count differs')
            if member.kind in {'root', 'page'}:
                if member.block_id is not None or (member.kind == 'page' and (
                    member.page_index is None or not 0 <= member.page_index < generation.page_count)):
                    raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Structural container has invalid source identity')
            elif row.engine == 'pageindex-flash' and member.kind == 'section' and member.block_id is None:
                if member.page_index is None or not 0 <= member.page_index < generation.page_count or member.block_sha256 is not None:
                    raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'PageIndex section container has invalid source identity')
            else:
                block = source.get(member.block_id)
                if block is None or block.sha256 != member.block_sha256 or block.source_locator.get('page_index') != member.page_index:
                    raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document node source checksum or page differs')
                if row.engine == 'structural' and (member.kind == 'section') != (block.kind == 'heading'):
                    raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Native structural sections require real canonical headings')
                ranges[member.id] = [(block.ordinal, block.ordinal + 1)]
        for node in sorted(nodes, key=lambda item: item.depth, reverse=True):
            expected = merge_ranges(ranges[node.id])
            if expected != node.source_ranges:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document node subtree source ranges differ')
            if node.parent_id is not None:
                ranges[node.parent_id].extend(expected)
        if tree.tree_kind == 'pages' and {node.page_index for node in nodes if node.kind == 'page'} != set(range(generation.page_count)):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Physical page fallback is incomplete')
        maximum_depth = max(node.depth for node in nodes)
        if maximum_depth != value['max_depth']:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index maximum depth differs')
        root_node = next(node for node in tree.nodes if node.parent_id is None)
        obj = await self._uow.session.get(StoredObject, value['manifest_object_id'])
        if (obj is None or (obj.workspace_id, obj.job_id, obj.role, obj.sha256) != (
            row.workspace_id, row.job_id, 'document_index', value['manifest_sha256']) or obj.state not in {'stored', 'referenced'}):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index manifest receipt is unavailable')
        row.root_node_id, row.node_count, row.source_block_count = root_node.id, len(nodes), generation.block_count
        row.tree_kind, row.coverage, row.max_depth = tree.tree_kind, generation.coverage, maximum_depth
        row.manifest_object_id, row.manifest_sha256 = obj.id, obj.sha256
        row.metadata_fingerprint, row.sealed = digest, True
        await self._uow.session.flush()
        return index_plan(row)

    async def commit_ready(self, lease, publication, result):
        row = await self._uow.session.get(IndexRoot, publication.get('document_index_id'), with_for_update=True)
        job = await self._uow.session.get(ProcessingJobModel, lease.id)
        if row is None or job is None or (row.workspace_id, row.artifact_id, row.revision_id,
            row.representation_set_id, row.processing_fingerprint) != (job.workspace_id, job.artifact_id,
            job.revision_id, publication['representation_set_id'], job.processing_fingerprint):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Document index publication source differs')
        if (not row.sealed or row.manifest_sha256 != publication['index_manifest_sha256']
            or result.get('document_index_id') != row.id or result.get('mode') != 'extract_index'):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index publication manifest differs')
        if row.status == 'building':
            if row.job_id != job.id:
                raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Unpublished index belongs to another job')
            row.status, row.publication_fencing_token = 'ready', lease.fencing_token
            await self._uow.session.flush()
            obj = await self._uow.session.get(StoredObject, row.manifest_object_id)
            obj.state = 'referenced'
            self._uow.session.add(ArtifactEventModel(id=row.id, workspace_id=row.workspace_id,
                operation_id=row.id, kind='artifact.document_index.ready', payload={
                    'document_index_id': row.id, 'representation_set_id': row.representation_set_id,
                    'artifact_id': row.artifact_id, 'revision_id': row.revision_id,
                    'source_sha256': row.source_sha256, 'manifest_sha256': row.manifest_sha256}))
        elif row.status != 'ready':
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Document index is no longer readable')
        return index_view(row)

    async def _readable(self, request):
        await self._catalog.workspace_row(request.scope, request.workspace_id)
        row = await self._uow.session.get(IndexRoot, request.index_id)
        if row is None or row.workspace_id != request.workspace_id or row.status != 'ready':
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Exact document index is unavailable')
        source = await self._catalog.revision(request.scope, request.workspace_id, ArtifactRef(row.artifact_id, row.revision_id))
        generation = await self._uow.session.get(Generation, row.representation_set_id)
        if source.sha256 != row.source_sha256 or generation is None or generation.status != 'ready':
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Document index source generation is unavailable')
        return row

    async def read(self, request):
        return index_view(await self._readable(request))

    async def latest_for_revision(self, request):
        await self._catalog.workspace_row(request.scope, request.workspace_id)
        row = (await self._uow.session.execute(select(IndexRoot).where(
            IndexRoot.project_id == request.scope.project_id,
            IndexRoot.environment == request.scope.environment.value,
            IndexRoot.workspace_id == request.workspace_id,
            IndexRoot.artifact_id == request.artifact_id,
            IndexRoot.revision_id == request.revision_id,
            IndexRoot.status == 'ready',
        ).order_by(IndexRoot.created_at.desc(), IndexRoot.id.desc()).limit(1))).scalar_one_or_none()
        if row is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'No ready document index exists for this revision')
        return index_view(await self._readable(ReadIndex(request.principal, request.scope,
            request.workspace_id, row.id)))

    async def _node_view(self, index, node):
        source, has_text, inferred, extraction_method = None, False, False, None
        if node.block_id:
            block = (await self._uow.session.execute(select(Block).where(
                Block.representation_set_id == index.representation_set_id, Block.block_id == node.block_id))).scalar_one()
            has_text = block.char_length > 0
            inferred, extraction_method = block.inferred, block.extraction_method
            source = SourceReference(artifact_id=index.artifact_id, revision_id=index.revision_id,
                source_sha256=index.source_sha256, representation_set_id=index.representation_set_id,
                document_index_id=index.id, node_id=node.id,
                locator={**block.source_locator, 'block_id': block.block_id}, excerpt_sha256=block.sha256)
        return DocumentNodeView(id=node.id, document_index_id=index.id, representation_set_id=index.representation_set_id,
            parent_id=node.parent_id, title=node.title, kind=node.kind, ordinal=node.ordinal, depth=node.depth,
            children_count=node.children_count, source_ranges=tuple(tuple(interval) for interval in node.source_ranges),
            source=source, has_own_text=has_text, inferred=inferred, extraction_method=extraction_method)

    async def node(self, request):
        index = await self._readable(request)
        node = await self._uow.session.get(Node, request.node_id)
        if node is None or node.document_index_id != index.id:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Exact index node is unavailable')
        return await self._node_view(index, node)

    async def nodes(self, request, after):
        index = await self._readable(request)
        if request.parent_id is not None:
            parent = await self._uow.session.get(Node, request.parent_id)
            if parent is None or parent.document_index_id != index.id:
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Exact index parent is unavailable')
        statement = select(Node).where(Node.document_index_id == index.id)
        if not request.title_query:
            statement = statement.where(Node.parent_id == request.parent_id)
        if request.title_query:
            pattern = '%' + request.title_query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            statement = statement.where(Node.title.ilike(pattern, escape='\\'))
        if after is not None:
            statement = statement.where(Node.ordinal > after)
        nodes = (await self._uow.session.execute(statement.order_by(Node.ordinal).limit(request.limit + 1))).scalars().all()
        return tuple([await self._node_view(index, node) for node in nodes])
