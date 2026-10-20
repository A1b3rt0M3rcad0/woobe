from dataclasses import asdict
import re
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, Request
from fastapi.responses import Response

from modules.artifacts.entrypoint import (
    ArtifactError, ArtifactPage, ArtifactView, BeginUpload, CapabilityDescriptor, ChangeWorkspace, ErrorEnvelope, CreateWorkspace, CreateWorkspaceGrant,
    Environment, ListFiles, ListWorkspaces, MutateFile, ReadFile, ReadWorkspace,
    ResolveWorkspace, RevokeWorkspaceGrant, Scope, UploadCreate, UploadPart, UploadRequest,
    WorkspaceCreate, WorkspacePage, WorkspaceUpdate, WorkspaceView, WriteText, RevisionView, UploadStatusView, build_file_service, build_upload_service,
    create_workspace_composer, create_workspace_grant_composer, get_workspace_composer,
    list_workspaces_composer, resolve_workspace_composer, revoke_workspace_grant_composer,
    update_workspace_composer, ProfileCreate, ProfileDefault, ProfileView, ProfilePage, ProcessingSelection,
    CreateProcessingProfile, ReadProcessingProfile, ListProcessingProfiles, BindProcessingProfile, SelectProcessingProfile,
    create_processing_profile_composer, get_processing_profile_composer, list_processing_profiles_composer,
    bind_processing_profile_composer, select_processing_profile_composer, processing_component_capabilities,
    ProcessingRequest, ProcessingJobView, RequestProcessing, ReadProcessingJob,
    request_processing_composer, get_processing_job_composer, cancel_processing_job_composer,
)
from shared.contracts.object_storage import ObjectStorageError
from woobe_api.http.artifacts.contracts import FileCreate, FileMove, GrantCreate, Identifier, TextUpdate
from woobe_api.http.artifacts.transport import (
    ArtifactDownloadResponse, ArtifactRoute, byte_range, error_response, expected_version, file_payload, idempotency, workspace_payload,
)


router = APIRouter(prefix='/v1', tags=['artifacts'], route_class=ArtifactRoute,
    responses={status: {'model': ErrorEnvelope} for status in (400, 401, 403, 404, 409, 410, 413, 416, 422, 503)})


def context(request: Request, project_id: UUID, environment: Environment):
    return request.state.principal, Scope(str(project_id), environment)


Context = Annotated[tuple, Depends(context)]


@router.post('/artifact-workspaces', status_code=201, response_model=WorkspaceView)
async def create_workspace(request: Request, body: WorkspaceCreate, ctx: Context):
    workspace = await create_workspace_composer()(CreateWorkspace(*ctx, body))
    return workspace_payload(workspace)


@router.get('/artifact-workspaces', response_model=WorkspacePage)
async def list_workspaces(ctx: Context, limit: int = Query(default=50, ge=1, le=200),
                          cursor: str | None = Query(default=None, max_length=4096),
                          external_namespace: str | None = Query(default=None, max_length=255)):
    page = await list_workspaces_composer()(ListWorkspaces(*ctx, limit, cursor, external_namespace))
    return {'schema_version': '1', 'items': [workspace_payload(item) for item in page.items],
            'has_more': page.has_more, 'next_cursor': page.next_cursor, 'truncated': page.truncated}


@router.get('/artifact-workspaces/resolve', response_model=WorkspaceView)
async def resolve_workspace(ctx: Context, external_namespace: str = Query(min_length=1, max_length=255),
                            external_key: str = Query(min_length=1, max_length=255)):
    return workspace_payload(await resolve_workspace_composer()(ResolveWorkspace(*ctx, external_namespace, external_key)))


@router.get('/artifact-workspaces/{artifact_workspace_id}', response_model=WorkspaceView)
async def get_workspace(artifact_workspace_id: Identifier, ctx: Context):
    return workspace_payload(await get_workspace_composer()(ReadWorkspace(*ctx, artifact_workspace_id)))


@router.patch('/artifact-workspaces/{artifact_workspace_id}', response_model=WorkspaceView)
async def update_workspace(artifact_workspace_id: Identifier, request: Request, body: WorkspaceUpdate, ctx: Context):
    expected_version(request, body.expected_version)
    return workspace_payload(await update_workspace_composer()(ChangeWorkspace(*ctx, artifact_workspace_id, body)))


@router.post('/artifact-workspace-grants', status_code=201)
async def grant_workspace(body: GrantCreate, ctx: Context):
    grant = await create_workspace_grant_composer()(CreateWorkspaceGrant(*ctx, body.subject_id,
        body.actions, body.artifact_workspace_id, body.external_namespace, body.expires_at))
    return {'schema_version': '1', **asdict(grant)}


@router.delete('/artifact-workspace-grants/{grant_id}')
async def revoke_grant(grant_id: Identifier, ctx: Context):
    await revoke_workspace_grant_composer()(RevokeWorkspaceGrant(*ctx, grant_id))
    return {'schema_version': '1', 'revoked': True}


@router.get('/artifact-workspaces/{artifact_workspace_id}/artifacts', response_model=ArtifactPage)
async def list_files(artifact_workspace_id: Identifier, ctx: Context,
                     directory: str = Query(default='', max_length=1024),
                     limit: int = Query(default=50, ge=1, le=200),
                     cursor: str | None = Query(default=None, max_length=4096)):
    page = await build_file_service().list(ListFiles(*ctx, artifact_workspace_id, directory, limit, cursor))
    return {'schema_version': '1', 'items': [asdict(item) for item in page.items],
            'has_more': page.has_more, 'next_cursor': page.next_cursor, 'truncated': page.truncated}


@router.post('/artifact-workspaces/{artifact_workspace_id}/artifacts', status_code=201, response_model=ArtifactView | UploadStatusView)
async def create_file(artifact_workspace_id: Identifier, request: Request, body: FileCreate, ctx: Context):
    idempotency(request, body.operation_id)
    service = build_file_service()
    if body.kind == 'directory':
        result = await service.mutate(MutateFile(*ctx, artifact_workspace_id, body.operation_id, 'mkdir', path=body.path))
        return {'schema_version': '1', **asdict(result)}
    return {'schema_version': '1', **asdict(await service.write_text(WriteText(*ctx, artifact_workspace_id,
        body.operation_id, body.path, body.text)))}


@router.get('/artifact-workspaces/{artifact_workspace_id}/artifacts/{artifact_id}', response_model=ArtifactView)
async def get_file(artifact_workspace_id: Identifier, artifact_id: Identifier, ctx: Context):
    return file_payload(await build_file_service().resolve(ReadFile(*ctx, artifact_workspace_id, artifact_id)))


@router.patch('/artifact-workspaces/{artifact_workspace_id}/artifacts/{artifact_id}', response_model=ArtifactView)
async def move_file(artifact_workspace_id: Identifier, artifact_id: Identifier, request: Request, body: FileMove, ctx: Context):
    idempotency(request, body.operation_id)
    expected_version(request, body.expected_version)
    result = await build_file_service().mutate(MutateFile(*ctx, artifact_workspace_id,
        body.operation_id, 'move', artifact_id, body.expected_version, body.path))
    return {'schema_version': '1', **asdict(result)}


@router.put('/artifact-workspaces/{artifact_workspace_id}/artifacts/{artifact_id}/content', response_model=UploadStatusView)
async def write_text(artifact_workspace_id: Identifier, artifact_id: Identifier, request: Request, body: TextUpdate, ctx: Context):
    idempotency(request, body.operation_id)
    result = await build_file_service().write_text(WriteText(*ctx, artifact_workspace_id,
        body.operation_id, body.path, body.text, artifact_id, body.expected_revision))
    return {'schema_version': '1', **asdict(result)}


@router.delete('/artifact-workspaces/{artifact_workspace_id}/artifacts/{artifact_id}', response_model=ArtifactView)
async def delete_file(artifact_workspace_id: Identifier, artifact_id: Identifier, request: Request, ctx: Context,
                      expected: int = Query(alias='expected_version', ge=1),
                      operation_id: Identifier = Header(alias='Idempotency-Key')):
    expected_version(request, expected)
    result = await build_file_service().mutate(MutateFile(*ctx, artifact_workspace_id,
        operation_id, 'delete', artifact_id, expected))
    return {'schema_version': '1', **asdict(result)}


@router.post('/artifact-workspaces/{artifact_workspace_id}/uploads', status_code=201, response_model=UploadStatusView)
async def begin_upload(artifact_workspace_id: Identifier, request: Request, body: UploadCreate, ctx: Context):
    idempotency(request, body.operation_id)
    return {'schema_version': '1', **asdict(await build_upload_service().begin(BeginUpload(*ctx, artifact_workspace_id, body)))}


@router.get('/artifact-workspaces/{artifact_workspace_id}/uploads/{upload_id}', response_model=UploadStatusView)
async def upload_status(artifact_workspace_id: Identifier, upload_id: Identifier, ctx: Context):
    return {'schema_version': '1', **asdict(await build_upload_service().status(UploadRequest(*ctx, artifact_workspace_id, upload_id)))}


@router.put('/artifact-workspaces/{artifact_workspace_id}/uploads/{upload_id}/parts', response_model=UploadStatusView)
async def upload_part(artifact_workspace_id: Identifier, upload_id: Identifier, request: Request, ctx: Context,
                      offset: int = Query(ge=0)):
    # Global middleware and Runtime Key checks retain their configured body
    # limits. This bounded proxy never buffers a whole large file.
    limit = min(request.app.state.settings.request_max_bytes,
                request.app.state.settings.runtime_max_request_bytes, 8 * 1024 * 1024)
    await build_upload_service().admit(UploadRequest(*ctx, artifact_workspace_id, upload_id))
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > limit:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Upload part exceeds the advertised proxy part limit')
        content.extend(chunk)
    result = await build_upload_service().append(UploadPart(*ctx, artifact_workspace_id, upload_id, offset, bytes(content)))
    return {'schema_version': '1', **asdict(result)}


@router.post('/artifact-workspaces/{artifact_workspace_id}/uploads/{upload_id}/finalize', response_model=UploadStatusView)
async def finalize_upload(artifact_workspace_id: Identifier, upload_id: Identifier, ctx: Context):
    return {'schema_version': '1', **asdict(await build_upload_service().finalize(UploadRequest(*ctx, artifact_workspace_id, upload_id)))}


@router.delete('/artifact-workspaces/{artifact_workspace_id}/uploads/{upload_id}', response_model=UploadStatusView)
async def abort_upload(artifact_workspace_id: Identifier, upload_id: Identifier, ctx: Context):
    return {'schema_version': '1', **asdict(await build_upload_service().abort(UploadRequest(*ctx, artifact_workspace_id, upload_id)))}


@router.get('/artifacts/{artifact_id}/revisions/{revision_id}', response_model=RevisionView)
async def get_revision(artifact_id: Identifier, revision_id: Identifier, artifact_workspace_id: Identifier, ctx: Context):
    return file_payload(await build_file_service().resolve(ReadFile(*ctx, artifact_workspace_id, artifact_id, revision_id)))['revision']


@router.get('/artifacts/{artifact_id}/revisions/{revision_id}/content', response_class=Response,
    responses={status: {'content': {'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}
               for status in (200, 206)})
async def download(artifact_id: Identifier, revision_id: Identifier, artifact_workspace_id: Identifier, request: Request, ctx: Context):
    service = build_file_service()
    command = ReadFile(*ctx, artifact_workspace_id, artifact_id, revision_id)
    snapshot = await service.resolve(command)
    size, digest = snapshot.revision.size_bytes, snapshot.revision.sha256
    range_header = request.headers.get('range')
    if request.headers.get('if-range') not in {None, f'"{digest}"'}:
        range_header = None
    start, stop = 0, size
    if range_header:
        try:
            start, stop = byte_range(range_header, size)
        except ArtifactError as error:
            response = error_response(error)
            response.headers['Content-Range'] = f'bytes */{size}'
            return response
    snapshot, stream = await service.open_content(command, start=start, end=stop)
    try:
        first = await anext(stream, b'')
    except ObjectStorageError as error:
        raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Artifact content is unavailable', retryable=True) from error

    async def content():
        try:
            yield first
            async for chunk in stream:
                yield chunk
        finally:
            await stream.aclose()

    filename = snapshot.artifact.path.rsplit('/', 1)[-1]
    fallback = re.sub(r'[^A-Za-z0-9._-]', '_', filename)[:150] or 'artifact'
    headers = {'Cache-Control': 'private, no-store', 'Accept-Ranges': 'bytes',
        'Content-Length': str(stop - start), 'ETag': f'"{digest}"', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename, safe="")}',
        'X-Woobe-Source-Sha256': digest}
    if range_header:
        headers['Content-Range'] = f'bytes {start}-{stop - 1}/{size}'
    return ArtifactDownloadResponse(content(), owned_stream=stream, status_code=206 if range_header else 200,
                             media_type=snapshot.revision.content_type, headers=headers)


@router.get('/artifact-capabilities', response_model=CapabilityDescriptor)
async def capabilities(request: Request, ctx: Context):
    # Authorize through a real Workspace listing decision; no private storage
    # probe or configuration values are exposed by discovery.
    await list_workspaces_composer()(ListWorkspaces(*ctx, limit=1))
    settings = request.app.state.settings
    components = processing_component_capabilities()
    ready = [item for item in components if item['ready']]
    return CapabilityDescriptor.model_validate({'schema_version': '1',
        'processors': [item['name'] for item in ready if item['role'] == 'processor'],
        'indexers': [item['name'] for item in ready if item['role'] == 'indexer'],
        'media_types': sorted({kind for item in ready if item['role'] == 'processor' for kind in item['media_types']}), 'transfer_modes': ['proxy', 'resumable-offset'],
        'max_upload_bytes': settings.upload_max_mb * 1024 * 1024, 'max_read_bytes': 262144,
        'max_request_bytes': min(settings.request_max_bytes, settings.runtime_max_request_bytes),
        'max_upload_part_bytes': min(settings.request_max_bytes, settings.runtime_max_request_bytes, 8 * 1024 * 1024),
        'max_upload_parts': 4096, 'max_inline_bytes': 262144, 'max_page_size': 200,
        'downloads': ['proxy-range'], 'signed_upload_urls': False, 'storage_readiness': 'not_probed'})


@router.post('/artifact-processing-profiles', status_code=201, response_model=ProfileView)
async def create_processing_profile(body: ProfileCreate, ctx: Context):
    return await create_processing_profile_composer()(CreateProcessingProfile(*ctx, body))


@router.get('/artifact-processing-profiles', response_model=ProfilePage)
async def list_processing_profiles(ctx: Context, limit: int = Query(default=50, ge=1, le=200),
                                   cursor: str | None = Query(default=None, max_length=4096)):
    page = await list_processing_profiles_composer()(ListProcessingProfiles(*ctx, limit, cursor))
    return {'schema_version': '1', 'items': page.items, 'has_more': page.has_more,
            'next_cursor': page.next_cursor, 'truncated': page.truncated}


@router.get('/artifact-processing-profiles/{profile_id}/revisions/{profile_revision}', response_model=ProfileView)
async def get_processing_profile(profile_id: Identifier, profile_revision: Annotated[int, Path(ge=1, le=9_223_372_036_854_775_807)], ctx: Context):
    return await get_processing_profile_composer()(ReadProcessingProfile(*ctx, profile_id, profile_revision))


@router.put('/artifact-workspaces/{artifact_workspace_id}/processing-profile', response_model=WorkspaceView)
async def bind_processing_profile(artifact_workspace_id: Identifier, body: ProfileDefault, request: Request, ctx: Context):
    expected_version(request, body.expected_version)
    return workspace_payload(await bind_processing_profile_composer()(BindProcessingProfile(*ctx, artifact_workspace_id, body)))


@router.get('/artifact-workspaces/{artifact_workspace_id}/processing-profile', response_model=ProcessingSelection)
async def select_processing_profile(artifact_workspace_id: Identifier, ctx: Context,
                                    profile_id: Identifier | None = None,
                                    profile_revision: int | None = Query(default=None, ge=1, le=9_223_372_036_854_775_807)):
    return await select_processing_profile_composer()(SelectProcessingProfile(*ctx, artifact_workspace_id, profile_id, profile_revision))


@router.get('/artifact-processing-capabilities')
async def processing_capabilities(ctx: Context):
    await list_processing_profiles_composer()(ListProcessingProfiles(*ctx, limit=1))
    return {'schema_version': '1', 'components': processing_component_capabilities(), 'store_only': True}


@router.post('/artifacts/{artifact_id}/processing', status_code=202, response_model=ProcessingJobView)
async def request_processing(artifact_id: Identifier, artifact_workspace_id: Identifier,
                             body: ProcessingRequest, request: Request, ctx: Context):
    idempotency(request, body.operation_id)
    return await request_processing_composer()(RequestProcessing(*ctx, artifact_workspace_id, artifact_id, body))


@router.get('/artifacts/{artifact_id}/processing/{job_id}', response_model=ProcessingJobView)
async def processing_job(artifact_id: Identifier, job_id: Identifier, artifact_workspace_id: Identifier, ctx: Context):
    return await get_processing_job_composer()(ReadProcessingJob(*ctx, artifact_workspace_id, job_id, artifact_id))


@router.post('/artifacts/{artifact_id}/processing/{job_id}/cancel', status_code=202, response_model=ProcessingJobView)
async def cancel_processing_job(artifact_id: Identifier, job_id: Identifier, artifact_workspace_id: Identifier, ctx: Context):
    return await cancel_processing_job_composer()(ReadProcessingJob(*ctx, artifact_workspace_id, job_id, artifact_id))
