import json
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from modules.artifacts.application.contracts.representations import RepresentationSetView
from modules.artifacts.domain.models import ArtifactError, ArtifactRef, RepresentationSet
from modules.artifacts.application.document_codec import serialized_identity
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.models import ArtifactEventModel, ProcessingJobModel
from modules.artifacts.infra.database.representation_models import (
    ArtifactRepresentationEntryModel as Entry,
    ArtifactRepresentationHeadModel as Head,
    ArtifactRepresentationSetModel as Generation,
    ArtifactSourceBlockModel as Block,
    ArtifactSourceSegmentModel as Segment,
    ArtifactStoredObjectModel as StoredObject,
)


def generation_identity(job_id):
    return str(uuid5(NAMESPACE_URL, 'woobe:representation-set:v1:' + job_id))


def object_identity(workspace_id, key):
    return str(uuid5(NAMESPACE_URL, 'woobe:processing-object:v1:' + workspace_id + ':' + key))


def generation_view(row):
    return RepresentationSetView(id=row.id, workspace_id=row.workspace_id, artifact_id=row.artifact_id,
        revision_id=row.revision_id, source_sha256=row.source_sha256, recipe_fingerprint=row.recipe_fingerprint,
        processing_fingerprint=row.processing_fingerprint, manifest_sha256=row.manifest_sha256,
        generation_number=row.generation_number, coverage=row.coverage, entry_count=row.entry_count,
        block_count=row.block_count, page_count=row.page_count, diagnostics=tuple(row.diagnostics),
        created_at=row.created_at, profile_id=row.profile_id, profile_revision=row.profile_revision)


def domain_generation(row):
    return RepresentationSet(row.id, row.workspace_id, ArtifactRef(row.artifact_id, row.revision_id),
        row.source_sha256, row.recipe_fingerprint, row.processing_fingerprint, row.generation_number,
        row.status, row.coverage, row.manifest_sha256, row.profile_id, row.profile_revision)


class RepresentationRepository:
    def __init__(self, uow):
        self._uow, self._catalog = uow, CatalogRepository(uow)

    async def lock_scope(self, scope, workspace_id):
        await self._catalog.workspace_row(scope, workspace_id, lock=True)

    async def _job(self, lease):
        row = await self._uow.session.get(ProcessingJobModel, lease.id)
        if row is None or (str(row.project_id), row.environment, row.workspace_id) != (
            lease.scope.project_id, lease.scope.environment.value, lease.workspace_id):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Processing publication scope is unavailable')
        return row

    async def reserve(self, request):
        lease = request.lease
        workspace = await self._catalog.workspace_row(lease.scope, lease.workspace_id, lock=True)
        prefix = (f'projects/{lease.scope.project_id}/environments/{lease.scope.environment.value}/'
                  f'artifact-workspaces/{lease.workspace_id}/processing/{lease.id}/attempts/{lease.fencing_token}/')
        if not request.key.startswith(prefix):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Processing output key is outside the owned attempt')
        identity = object_identity(lease.workspace_id, request.key)
        row = await self._uow.session.get(StoredObject, identity)
        expected = (request.size_bytes, request.sha256, request.content_type, request.role)
        if row is not None:
            if (row.size_bytes, row.sha256, row.content_type, row.role) != expected or row.state in {'gc_pending', 'purged'}:
                raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Processing output declaration already differs')
            return {'id': row.id, 'state': row.state}
        if workspace.used_bytes + workspace.reserved_bytes + request.size_bytes > workspace.quota_bytes:
            raise ArtifactError('QUOTA_EXCEEDED', 'Processing output exceeds the Workspace byte quota')
        workspace.reserved_bytes += request.size_bytes
        row = StoredObject(id=identity, project_id=UUID(lease.scope.project_id), environment=lease.scope.environment.value,
            workspace_id=workspace.id, job_id=lease.id, fencing_token=lease.fencing_token,
            object_key=request.key, role=request.role, size_bytes=request.size_bytes,
            sha256=request.sha256, content_type=request.content_type, state='reserved', accounting_bucket='reserved')
        self._uow.session.add(row)
        await self._uow.session.flush()
        return {'id': row.id, 'state': row.state}

    async def record(self, request):
        declaration, receipt = request.declaration, request.receipt
        lease = declaration.lease
        workspace = await self._catalog.workspace_row(lease.scope, lease.workspace_id, lock=True)
        row = await self._uow.session.get(StoredObject, object_identity(workspace.id, declaration.key), with_for_update=True)
        if row is None or row.job_id != lease.id or row.fencing_token != lease.fencing_token:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Processing output acknowledgement has no admitted intent')
        expected = (row.object_key, row.size_bytes, row.sha256, row.content_type)
        if (receipt.key, receipt.size_bytes, receipt.sha256, receipt.content_type) != expected:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Processing output acknowledgement failed integrity verification')
        if row.state in {'gc_pending', 'purged'}:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Processing output is no longer publishable')
        if row.state == 'reserved':
            workspace.reserved_bytes -= row.size_bytes
            workspace.used_bytes += row.size_bytes
            row.state, row.accounting_bucket = 'stored', 'used'
            row.storage_version_id = receipt.version_id
        elif row.storage_version_id != receipt.version_id:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Immutable processing output backend version changed')
        return {'id': row.id, 'state': row.state}

    async def prepare(self, request, source):
        lease = request.lease
        job = await self._job(lease)
        reusable = (await self._uow.session.execute(select(Generation).where(
            Generation.workspace_id == lease.workspace_id, Generation.artifact_id == source.artifact_id,
            Generation.revision_id == source.id, Generation.processing_fingerprint == job.processing_fingerprint,
            Generation.status == 'ready', Generation.source_sha256 == source.sha256,
        ).order_by(Generation.generation_number.desc(), Generation.id).limit(1))).scalar_one_or_none()
        if reusable is not None:
            return {'representation_set_id': reusable.id, 'reused': True,
                'coverage': reusable.coverage, 'block_count': reusable.block_count,
                'page_count': reusable.page_count, 'diagnostics': reusable.diagnostics[:32],
                'manifest_sha256': reusable.manifest_sha256}
        identity = generation_identity(lease.id)
        row = await self._uow.session.get(Generation, identity)
        if row is None:
            row = Generation(id=identity, project_id=job.project_id, environment=job.environment,
                workspace_id=job.workspace_id, artifact_id=job.artifact_id, revision_id=job.revision_id,
                job_id=job.id, generation_number=job.generation_number, build_fencing_token=lease.fencing_token,
                source_sha256=source.sha256, recipe_fingerprint=job.recipe_fingerprint,
                processing_fingerprint=job.processing_fingerprint, profile_id=job.profile_id,
                profile_revision=job.profile_revision, status='building', coverage='unsupported', sealed=False,
                entry_count=0, block_count=0, segment_count=0, page_count=0, diagnostics=[], pages=[])
            self._uow.session.add(row)
            await self._uow.session.flush()
        if row.status != 'building':
            raise ArtifactError('REPRESENTATION_NOT_READY', 'Representation generation cannot be rebuilt')
        if row.sealed:
            return {'representation_set_id': row.id, 'reused': False, 'sealed': True,
                'coverage': row.coverage, 'block_count': row.block_count, 'page_count': row.page_count,
                'diagnostics': row.diagnostics[:32], 'manifest_sha256': row.manifest_sha256}
        if row.build_fencing_token != lease.fencing_token:
            await self._uow.session.execute(delete(Segment).where(Segment.representation_set_id == row.id))
            await self._uow.session.execute(delete(Block).where(Block.representation_set_id == row.id))
            await self._uow.session.execute(delete(Entry).where(Entry.representation_set_id == row.id))
            row.build_fencing_token = lease.fencing_token
        return {'representation_set_id': row.id, 'reused': False, 'sealed': False}

    async def _building(self, request):
        row = await self._uow.session.get(Generation, request.representation_set_id, with_for_update=True)
        if row is None or row.workspace_id != request.lease.workspace_id or row.job_id != request.lease.id:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Representation generation is unavailable')
        if row.status != 'building' or row.sealed or row.build_fencing_token != request.lease.fencing_token:
            raise ArtifactError('ARTIFACT_REVISION_CONFLICT', 'Representation metadata is sealed or owned by another attempt')
        return row

    async def metadata(self, request):
        row = await self._building(request)
        value = request.value
        if not isinstance(value, dict) or value.get('kind') not in {'entries', 'blocks', 'segments'}:
            raise ValueError('Invalid representation metadata batch')
        items = value.get('items')
        if not isinstance(items, list) or not 1 <= len(items) <= 1000 or len(json.dumps(items).encode()) > 4_194_304:
            raise ValueError('Representation metadata batch exceeds its bounds')
        table = {'entries': Entry, 'blocks': Block, 'segments': Segment}[value['kind']]
        for item in items:
            if item.get('workspace_id') != row.workspace_id or item.get('representation_set_id') != row.id:
                raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Representation metadata crosses its generation scope')
            existing = await self._uow.session.get(table, item['id'])
            if existing is not None:
                if any(getattr(existing, name) != member for name, member in item.items()):
                    raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Representation metadata batch replay differs')
            else:
                self._uow.session.add(table(**item))
        await self._uow.session.flush()
        return {'accepted': len(items)}

    async def seal(self, request):
        row = await self._building(request)
        value = request.value
        counts = [(Entry, 'entry_count'), (Block, 'block_count'), (Segment, 'segment_count')]
        for model, name in counts:
            count = await self._uow.session.scalar(select(func.count()).select_from(model).where(model.representation_set_id == row.id))
            if count != value[name]:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation metadata manifest is incomplete')
        metadata = {}
        for model, kind in ((Entry, 'entries'), (Block, 'blocks'), (Segment, 'segments')):
            members = (await self._uow.session.execute(select(model).where(
                model.representation_set_id == row.id).order_by(model.id))).scalars().all()
            metadata[kind] = [{column.name: getattr(member, column.name) for column in model.__table__.columns
                              if column.name != 'created_at'} for member in members]
        _, digest = serialized_identity(metadata, 2_147_483_648)
        if digest != value['metadata_fingerprint']:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation metadata fingerprint differs')
        object_ids = {entry['object_id'] for entry in metadata['entries']} | {value['manifest_object_id']}
        objects = (await self._uow.session.execute(select(StoredObject).where(
            StoredObject.workspace_id == row.workspace_id, StoredObject.id.in_(object_ids)))).scalars().all()
        by_object = {obj.id: obj for obj in objects}
        if (set(by_object) != object_ids or any(obj.job_id != row.job_id or obj.state not in {'stored', 'referenced'}
                                              for obj in objects)):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation object receipts are incomplete')
        manifest = by_object[value['manifest_object_id']]
        if manifest.role != 'manifest' or manifest.sha256 != value['manifest_sha256']:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation manifest receipt differs')
        roles = {entry['role'] for entry in metadata['entries']}
        if not {'structure', 'markdown', 'outline', 'source_map'} <= roles:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation is missing a required role')
        assets = {entry['asset_id'] for entry in metadata['entries'] if entry['role'] == 'figure'}
        segment_map = {}
        for segment in metadata['segments']:
            segment_map.setdefault(segment['block_id'], []).append(segment)
        for block in metadata['blocks']:
            if not set(block['asset_ids']) <= assets or (block['kind'] == 'figure' and not block['asset_ids']):
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Figure has no complete asset publication')
            obj = by_object.get(block['object_id'])
            if obj is None or obj.role != 'block_text' or block['byte_end'] > obj.size_bytes:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source block text receipt is unavailable')
            char_offset, byte_offset = 0, block['byte_start']
            for segment in sorted(segment_map.get(block['block_id'], []), key=lambda item: item['char_start']):
                if segment['char_start'] != char_offset or segment['byte_start'] != byte_offset:
                    raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source text segments have a gap or overlap')
                char_offset, byte_offset = segment['char_end'], segment['byte_end']
            if char_offset != block['char_length'] or byte_offset != block['byte_end']:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source text segments do not cover their block')
        row.manifest_object_id, row.manifest_sha256 = value['manifest_object_id'], value['manifest_sha256']
        row.metadata_fingerprint = value['metadata_fingerprint']
        row.entry_count, row.block_count, row.segment_count = value['entry_count'], value['block_count'], value['segment_count']
        row.page_count, row.coverage = value['page_count'], value['coverage']
        row.pages, row.diagnostics, row.sealed = value['pages'], value['diagnostics'], True
        await self._uow.session.flush()
        return {'representation_set_id': row.id, 'manifest_sha256': row.manifest_sha256,
            'coverage': row.coverage, 'block_count': row.block_count, 'page_count': row.page_count,
            'diagnostics': row.diagnostics[:32], 'reused': False}

    async def commit_ready(self, lease, publication, result):
        row = await self._uow.session.get(Generation, publication['representation_set_id'], with_for_update=True)
        job = await self._job(lease)
        if row is None or (row.workspace_id, row.artifact_id, row.revision_id, row.processing_fingerprint) != (
            job.workspace_id, job.artifact_id, job.revision_id, job.processing_fingerprint):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Representation publication scope is unavailable')
        if result.get('processing_performed') is not True:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation publication requires a processed result')
        if (result.get('source_sha256'), result.get('mode'), result.get('coverage'),
            result.get('block_count'), result.get('page_count')) != (row.source_sha256, job.recipe['mode'],
                row.coverage, row.block_count, row.page_count):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Processing result does not match its immutable representation metadata')
        if row.manifest_sha256 != publication['manifest_sha256'] or not row.sealed:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation publication does not match its sealed manifest')
        if row.status == 'building':
            if row.job_id != lease.id:
                raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Unpublished representation belongs to another job')
            row.status, row.publication_fencing_token = 'ready', lease.fencing_token
            await self._uow.session.flush()
            object_ids = select(Entry.object_id).where(Entry.representation_set_id == row.id)
            objects = (await self._uow.session.execute(select(StoredObject).where(
                StoredObject.workspace_id == row.workspace_id,
                (StoredObject.id.in_(object_ids)) | (StoredObject.id == row.manifest_object_id),
            ))).scalars()
            for obj in objects:
                obj.state = 'referenced'
            self._uow.session.add(ArtifactEventModel(id=row.id, workspace_id=row.workspace_id,
                operation_id=row.id, kind='artifact.representations.ready', payload={
                    'representation_set_id': row.id, 'artifact_id': row.artifact_id,
                    'revision_id': row.revision_id, 'source_sha256': row.source_sha256,
                    'processing_fingerprint': row.processing_fingerprint, 'manifest_sha256': row.manifest_sha256}))
        elif row.status != 'ready':
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Representation generation is no longer readable')
        if result['representation_set_id'] != row.id:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Processing receipt does not identify its published generation')
        statement = insert(Head).values(workspace_id=row.workspace_id, artifact_id=row.artifact_id,
            revision_id=row.revision_id, representation_set_id=row.id, request_number=job.generation_number)
        await self._uow.session.execute(statement.on_conflict_do_update(
            index_elements=['workspace_id', 'revision_id'],
            set_={'representation_set_id': row.id, 'request_number': job.generation_number},
            where=Head.request_number <= job.generation_number))
        return generation_view(row)

    async def resolve(self, request):
        workspace = await self._catalog.workspace_row(request.scope, request.workspace_id)
        artifact = await self._catalog.artifact_row(request.scope, request.workspace_id, request.artifact_id)
        revision_id = request.revision_id or artifact.revision_id
        source = await self._catalog.revision(request.scope, request.workspace_id, ArtifactRef(artifact.id, revision_id))
        generation_id = request.representation_set_id
        if generation_id is None:
            head = await self._uow.session.get(Head, (workspace.id, source.id))
            generation_id = head.representation_set_id if head else None
        generation = await self._uow.session.get(Generation, generation_id) if generation_id else None
        if generation is None or (generation.workspace_id, generation.artifact_id, generation.revision_id,
                generation.source_sha256, generation.status) != (workspace.id, artifact.id, source.id, source.sha256, 'ready'):
            raise ArtifactError('REPRESENTATION_NOT_READY', 'Exact representation generation is unavailable')
        return workspace, source, generation

    async def read(self, request):
        from modules.artifacts.application.contracts.representations import RepresentationSnapshot
        from modules.artifacts.domain.models import ArtifactRepresentation
        workspace, _, generation = await self.resolve(request)
        representation = None
        if request.entry_id:
            row = await self._uow.session.get(Entry, request.entry_id)
            if row is None or row.representation_set_id != generation.id or not row.visible:
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Representation entry is unavailable')
            obj = await self._uow.session.get(StoredObject, row.object_id)
            if obj is None or obj.state != 'referenced':
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Representation content is unavailable')
            representation = ArtifactRepresentation(row.id, generation.id, obj.object_key, row.role,
                obj.sha256, obj.size_bytes, obj.content_type, row.path, row.visible, row.asset_id, obj.id, obj.storage_version_id)
        return RepresentationSnapshot(domain_generation(generation), representation, workspace.storage_profile, generation_view(generation))

    async def entries(self, request, after):
        from modules.artifacts.application.contracts.representations import RepresentationEntryView
        _, _, generation = await self.resolve(request)
        statement = select(Entry, StoredObject).join(StoredObject, StoredObject.id == Entry.object_id).where(
            Entry.representation_set_id == generation.id, Entry.visible.is_(True), StoredObject.state == 'referenced')
        if request.directory:
            statement = statement.where(Entry.path.startswith(request.directory + '/', autoescape=True))
        if after:
            statement = statement.where(Entry.id > after)
        rows = (await self._uow.session.execute(statement.order_by(Entry.id).limit(request.limit + 1))).all()
        return generation.id, tuple(RepresentationEntryView(id=entry.id, representation_set_id=generation.id,
            path=entry.path, kind=entry.role, size_bytes=obj.size_bytes, sha256=obj.sha256,
            content_type=obj.content_type, asset_id=entry.asset_id) for entry, obj in rows)

    async def source(self, request):
        from modules.artifacts.application.contracts.representations import ReadRepresentation
        ref = request.definition.source
        lookup = ReadRepresentation(request.principal, request.scope, request.workspace_id,
            ref.artifact_id, ref.revision_id, ref.representation_set_id)
        workspace, source, generation = await self.resolve(lookup)
        if ref.representation_set_id is None or source.sha256 != ref.source_sha256 or ref.document_index_id or ref.node_id:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Source reference requires its exact published generation')
        locator = ref.locator
        if locator is None or locator.block_id is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Source reference requires an exact block')
        block = (await self._uow.session.execute(select(Block).where(
            Block.representation_set_id == generation.id, Block.block_id == locator.block_id))).scalar_one_or_none()
        if block is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Source block is unavailable')
        supplied = locator.model_dump(mode='json')
        original = block.source_locator
        canonical = supplied['char_space'] == 'canonical_block_text'
        for name in ('page_index', 'page_number', 'bbox', 'image_bbox', 'line_start', 'line_end', 'byte_start', 'byte_end',
                     'source_encoding', 'text_normalization'):
            if supplied.get(name) is not None and supplied.get(name) != original.get(name):
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Source locator does not match its published block')
        start, end = 0, block.char_length
        if canonical and locator.char_start is not None:
            start, end = locator.char_start, locator.char_end
        elif locator.char_start is not None and (locator.char_space, locator.char_start, locator.char_end) != (
                original['char_space'], original['char_start'], original['char_end']):
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Original character interval does not identify this block')
        if not 0 <= start <= end <= block.char_length:
            raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Source character interval exceeds the block')
        if request.definition.offset > end - start:
            raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Source offset exceeds the requested interval')
        low = start + request.definition.offset
        high = min(end, low + request.definition.max_chars)
        segments = (await self._uow.session.execute(select(Segment).where(
            Segment.representation_set_id == generation.id, Segment.block_id == block.block_id,
            Segment.char_end > low, Segment.char_start < high).order_by(Segment.char_start))).scalars().all()
        obj = await self._uow.session.get(StoredObject, block.object_id)
        if obj is None or obj.state != 'referenced':
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Source text content is unavailable')
        if ref.excerpt_sha256 is not None and ref.excerpt_sha256 != block.sha256:
            # Subset checksums are verified by the bounded reader after I/O.
            if end - start > 65_536:
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Excerpt checksum requires a bounded exact interval')
        return {'storage_profile': workspace.storage_profile, 'key': obj.object_key,
            'version_id': obj.storage_version_id, 'size_bytes': obj.size_bytes, 'sha256': obj.sha256,
            'block_sha256': block.sha256, 'block_char_length': block.char_length, 'block_id': block.block_id,
            'segments': [{name: getattr(segment, name) for name in ('char_start', 'char_end', 'byte_start', 'byte_end', 'sha256')} for segment in segments],
            'low': low, 'high': high, 'start': start, 'end': end, 'coverage': generation.coverage,
            'source': ref.model_dump(mode='json')}
