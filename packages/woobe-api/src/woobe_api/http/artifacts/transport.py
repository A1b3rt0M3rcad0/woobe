from dataclasses import asdict
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute

from modules.artifacts.entrypoint import ArtifactError
from shared.contracts.errors import AuthenticationError, AuthorizationError, NotFoundError


STATUS = {
    'ARTIFACT_ACCESS_DENIED': 403, 'SOURCE_UNAVAILABLE': 404,
    'UPLOAD_EXPIRED': 410, 'ARTIFACT_INVALID_RANGE': 416,
    'ARTIFACT_INVALID_CURSOR': 400, 'ARTIFACT_LIMIT_EXCEEDED': 413,
    'PROCESSOR_UNAVAILABLE': 503,
    'UPLOAD_INTEGRITY_MISMATCH': 422, 'ARTIFACT_STORAGE_UNAVAILABLE': 503,
}


def error_response(error):
    return JSONResponse(status_code=STATUS.get(str(error.code), 409),
        content={'schema_version': '1', 'code': str(error.code), 'message': str(error),
                 'correlation_id': uuid4().hex, 'retryable': error.retryable},
        headers={'Cache-Control': 'private, no-store'})


class ArtifactRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                response = await original(request)
                response.headers['Cache-Control'] = 'private, no-store'
                return response
            except ArtifactError as error:
                return error_response(error)
            except (AuthenticationError, AuthorizationError, NotFoundError) as error:
                code = 'SOURCE_UNAVAILABLE' if isinstance(error, NotFoundError) else 'ARTIFACT_ACCESS_DENIED'
                response = error_response(ArtifactError(code, 'Artifact access is denied'))
                response.status_code = 401 if isinstance(error, AuthenticationError) else 404 if isinstance(error, NotFoundError) else 403
                if response.status_code == 401:
                    response.headers['WWW-Authenticate'] = 'Bearer'
                return response
            except (ValueError, RequestValidationError):
                return JSONResponse(status_code=422, content={'schema_version': '1',
                    'code': 'UPLOAD_INTEGRITY_MISMATCH', 'message': 'Invalid artifact operation input',
                    'correlation_id': uuid4().hex, 'retryable': False},
                    headers={'Cache-Control': 'private, no-store'})
        return handler


def workspace_payload(workspace):
    values = asdict(workspace)
    values.update(values.pop('scope'))
    values['labels'] = dict(workspace.labels)
    return {'schema_version': '1', **values}


def file_payload(snapshot):
    revision = asdict(snapshot.revision) if snapshot.revision is not None else None
    if revision is not None:
        revision.pop('object_key')
        revision.pop('storage_version_id')
    return {'schema_version': '1', **asdict(snapshot.artifact), 'revision': revision}


def idempotency(request, operation):
    supplied = request.headers.get('idempotency-key')
    if supplied is not None and supplied != operation:
        raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Idempotency header and operation ID disagree')


def expected_version(request, version):
    header = request.headers.get('if-match')
    if header is not None and header != f'"{version}"':
        raise ArtifactError('ARTIFACT_REVISION_CONFLICT', 'If-Match and expected version disagree')


def byte_range(value, size):
    if not value.startswith('bytes=') or ',' in value:
        raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Only a single byte range is supported')
    try:
        left, right = value[6:].split('-', 1)
        if left:
            if not left.isascii() or not left.isdecimal() or (right and (not right.isascii() or not right.isdecimal())):
                raise ValueError
            start, stop = int(left), min(int(right) + 1, size) if right else size
        else:
            if not right.isascii() or not right.isdecimal() or int(right) <= 0:
                raise ValueError
            start, stop = max(0, size - int(right)), size
        if not 0 <= start < stop <= size:
            raise ValueError
        return start, stop
    except ValueError as error:
        raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Invalid artifact byte range') from error


class ArtifactDownloadResponse(StreamingResponse):
    def __init__(self, content, *, owned_stream, **kwargs):
        super().__init__(content, **kwargs)
        self._owned_stream = owned_stream

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self._owned_stream.aclose()
