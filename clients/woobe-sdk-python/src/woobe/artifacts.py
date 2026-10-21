from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Literal, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from woobe.errors import (
    WoobeAuthenticationError,
    WoobeConnectionError,
    WoobeProtocolError,
    WoobeRequestError,
)

if TYPE_CHECKING:
    from woobe._transport.http import RuntimeTransport

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
TModel = TypeVar("TModel", bound=BaseModel)


class ArtifactReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str = Field(min_length=1, max_length=128)
    revision_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_identity(self) -> ArtifactReference:
        if not _IDENTIFIER.fullmatch(self.artifact_id) or not _IDENTIFIER.fullmatch(
            self.revision_id
        ):
            raise ValueError("Artifact references require exact opaque IDs")
        return self


class SourceLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    block_id: str | None = None
    page_index: int | None = None
    page_number: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    page_label: str | None = None


class SourceReference(ArtifactReference):
    model_config = ConfigDict(frozen=True, extra="allow")

    source_sha256: str
    representation_set_id: str | None = None
    document_index_id: str | None = None
    node_id: str | None = None
    locator: SourceLocator | None = None
    excerpt_sha256: str | None = None

    @model_validator(mode="after")
    def validate_hashes(self) -> SourceReference:
        if not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("SourceRef requires a lowercase SHA-256 digest")
        if self.excerpt_sha256 is not None and not _SHA256.fullmatch(self.excerpt_sha256):
            raise ValueError("SourceRef excerpt digest must be lowercase SHA-256")
        return self


class ContentPart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["text", "artifact"]
    text: str | None = None
    ref: ArtifactReference | None = None
    media_type_hint: str | None = None

    @model_validator(mode="after")
    def validate_variant(self) -> ContentPart:
        if self.type == "text" and (self.text is None or self.ref is not None):
            raise ValueError("text content parts require text and cannot include a ref")
        if self.type == "text" and self.media_type_hint is not None:
            raise ValueError("text content parts cannot include a media type hint")
        if self.type == "artifact" and (self.ref is None or self.text is not None):
            raise ValueError("artifact content parts require an exact ref and cannot include text")
        if self.media_type_hint is not None and "/" not in self.media_type_hint:
            raise ValueError("media_type_hint must be a media type")
        return self


ArtifactPartInput = ContentPart
ArtifactRef = ArtifactReference
SourceRef = SourceReference


def text_part(text: str) -> ContentPart:
    return ContentPart(type="text", text=text)


def artifact_part(ref: ArtifactReference, media_type_hint: str | None = None) -> ContentPart:
    return ContentPart(type="artifact", ref=ref, media_type_hint=media_type_hint)


def validate_content_parts(parts: Iterable[ContentPart]) -> list[ContentPart]:
    values = list(parts)
    if not values or len(values) > 32:
        raise ValueError("content_parts must contain between 1 and 32 parts")
    refs = sum(part.type == "artifact" for part in values)
    text_size = sum(len(part.text or "") for part in values)
    if refs > 16 or text_size > 32_000:
        raise ValueError("content_parts exceed the Runtime reference or text budget")
    return values


class ArtifactOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    schema_version: Literal["1"]
    ref: ArtifactReference
    path: str
    content_type: str
    size_bytes: int = Field(ge=0)
    sha256: str
    status: Literal["available"]
    run_id: str | None = None
    node_id: str | None = None
    source_refs: list[SourceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_receipt(self) -> ArtifactOutput:
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError("Artifact output requires a lowercase SHA-256 digest")
        if not self.path or "/" not in self.content_type:
            raise ValueError("Artifact output requires a path and media type")
        return self


class ArtifactTransfer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    operation_id: str
    state: str
    mode: str = ""
    destination_host: str = ""
    input_refs: list[ArtifactReference] = Field(default_factory=list)
    file_hashes: list[dict[str, Any]] = Field(default_factory=list)
    status_code: int | None = None
    tool_id: str | None = None


class ArtifactWorkspace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    project_id: str
    environment: str
    external_namespace: str
    external_key: str
    name: str
    status: str
    version: int
    quota_bytes: int = 0
    used_bytes: int = 0
    reserved_bytes: int = 0
    labels: dict[str, str] = Field(default_factory=dict)


class ArtifactRevision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    artifact_id: str
    content_type: str
    size_bytes: int
    sha256: str
    origin: str = ""
    run_id: str | None = None
    node_id: str | None = None


class Artifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    workspace_id: str
    path: str
    kind: str
    revision_id: str | None = None
    version: int
    deleted: bool = False
    revision: ArtifactRevision | None = None


class ArtifactUpload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    workspace_id: str
    operation_id: str
    expected_size: int
    status: str
    offset: int
    receipt: ArtifactReference | None = None


class ArtifactPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    items: list[Artifact] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str = ""
    truncated: bool = False


class ArtifactWorkspacePage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    items: list[ArtifactWorkspace] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str = ""
    truncated: bool = False


class ArtifactProcessingJob(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    workspace_id: str
    operation_id: str
    source: ArtifactReference
    status: str
    attempt: int = 0
    completed_stages: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    error_code: str | None = None
    retryable: bool = False


class ArtifactSearchHit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    artifact_id: str
    revision_id: str
    path: str
    match_location: str
    snippet: str
    coverage: str
    source: SourceReference


class ArtifactSearchPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    items: list[ArtifactSearchHit] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str = ""
    truncated: bool = False
    mode: str = ""


class SourceRead(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    source: SourceReference
    text: str
    offset: int
    next_offset: int | None = None
    truncated: bool = False
    coverage: str = ""
    page_label: str | None = None


ArtifactSource = SourceReference
ArtifactSourceRead = SourceRead


class ArtifactIndex(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    workspace_id: str
    artifact_id: str
    revision_id: str
    source_sha256: str
    engine: str
    engine_version: str
    status: str
    tree_kind: str
    coverage: str
    root_node_id: str
    node_count: int
    max_depth: int


class ArtifactNodePage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    items: list[dict[str, Any]] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str = ""
    truncated: bool = False


class ProcessingProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    revision: int
    project_id: str
    environment: str
    fingerprint: str
    ready: bool
    diagnostics: list[str] = Field(default_factory=list)
    recipe: dict[str, Any] = Field(default_factory=dict)


class ArtifactDownload:
    """Context-managed exact-revision stream; closing the context releases the response."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.status_code = response.status_code
        self.content_type = response.headers.get("Content-Type", "")
        self.content_range = response.headers.get("Content-Range", "")
        self.etag = response.headers.get("ETag", "")
        self.sha256 = response.headers.get("X-Woobe-Source-Sha256", "")

    async def __aenter__(self) -> ArtifactDownload:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        await self.aclose()

    async def aclose(self) -> None:
        await self._response.aclose()

    async def iter_bytes(self, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        async for chunk in self._response.aiter_bytes(chunk_size=chunk_size):
            yield chunk


class ArtifactsClient:
    """Direct Artifact API client scoped to one Project, Environment and Runtime Key."""

    def __init__(
        self, *, transport: RuntimeTransport, project_id: str, environment: str, runtime_key: str
    ) -> None:
        if not _IDENTIFIER.fullmatch(project_id.strip()):
            raise ValueError("project_id must be a valid opaque identifier")
        if environment not in {"draft", "staging", "production"}:
            raise ValueError("environment must be draft, staging or production")
        if not runtime_key.strip():
            raise ValueError("Runtime Key must not be empty")
        self._transport = transport
        self.project_id = project_id.strip()
        self.environment = environment
        self._runtime_key = runtime_key.strip()

    @staticmethod
    def _id(value: str, name: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError(f"{name} must be a valid opaque identifier")
        return quote(value, safe="")

    @staticmethod
    def _parse(model: type[TModel], data: Any) -> TModel:
        try:
            return model.model_validate(data)
        except ValueError as exc:
            raise WoobeProtocolError(
                "Woobe Artifacts response violates its public contract"
            ) from exc

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = False,
    ) -> Any:
        query = {"project_id": self.project_id, "environment": self.environment, **(params or {})}
        request_headers = {
            "Authorization": f"Bearer {self._runtime_key}",
            "Accept": "application/json",
        }
        if json_body is not None:
            request_headers["Content-Type"] = "application/json"
        request_headers.update(headers or {})
        try:
            if stream:
                request = self._transport._http().build_request(
                    method, path, params=query, headers=request_headers
                )
                response = await self._transport._http().send(
                    request, stream=True, follow_redirects=False
                )
            else:
                response = await self._transport._http().request(
                    method,
                    path,
                    params=query,
                    headers=request_headers,
                    json=json_body,
                    content=content,
                    follow_redirects=False,
                )
        except httpx.RequestError as exc:
            raise WoobeConnectionError(
                "Woobe Artifacts request failed; mutation outcome may be uncertain"
            ) from exc
        if not response.is_success:
            status = response.status_code
            await response.aclose()
            error_type = WoobeAuthenticationError if status in {401, 403} else WoobeRequestError
            raise error_type(f"Woobe Artifacts request failed ({status})", status_code=status)
        if stream:
            return response
        try:
            body = response.json()
        except ValueError as exc:
            raise WoobeProtocolError("Woobe Artifacts response contains invalid JSON") from exc
        finally:
            await response.aclose()
        if not isinstance(body, dict):
            raise WoobeProtocolError("Woobe Artifacts response must be an object")
        return body

    async def capabilities(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/artifact-capabilities")

    async def create_workspace(
        self, *, external_namespace: str, external_key: str, name: str, **options: Any
    ) -> ArtifactWorkspace:
        requested_environment = options.pop("environment", self.environment)
        if requested_environment != self.environment:
            raise ValueError("workspace environment must match this Artifacts client scope")
        if {"project_id", "id", "schema_version"} & options.keys():
            raise ValueError("workspace options cannot override scope or schema identity")
        body = {
            "schema_version": "1",
            "environment": self.environment,
            "external_namespace": external_namespace,
            "external_key": external_key,
            "name": name,
            **options,
        }
        return self._parse(
            ArtifactWorkspace,
            await self._request("POST", "/v1/artifact-workspaces", json_body=body),
        )

    async def list_workspaces(
        self, *, limit: int = 50, cursor: str | None = None, external_namespace: str | None = None
    ) -> dict[str, Any]:
        params = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if external_namespace is not None:
            params["external_namespace"] = external_namespace
        return await self._request("GET", "/v1/artifact-workspaces", params=params)

    async def list_workspace_page(
        self, *, limit: int = 50, cursor: str | None = None, external_namespace: str | None = None
    ) -> ArtifactWorkspacePage:
        return self._parse(
            ArtifactWorkspacePage,
            await self.list_workspaces(
                limit=limit, cursor=cursor, external_namespace=external_namespace
            ),
        )

    async def resolve_workspace(
        self, *, external_namespace: str, external_key: str
    ) -> ArtifactWorkspace:
        data = await self._request(
            "GET",
            "/v1/artifact-workspaces/resolve",
            params={
                "external_namespace": external_namespace,
                "external_key": external_key,
            },
        )
        return self._parse(ArtifactWorkspace, data)

    async def get_workspace(self, workspace_id: str) -> ArtifactWorkspace:
        workspace_id = self._id(workspace_id, "workspace_id")
        data = await self._request("GET", f"/v1/artifact-workspaces/{workspace_id}")
        return self._parse(ArtifactWorkspace, data)

    async def update_workspace(
        self, workspace_id: str, *, expected_version: int, **changes: Any
    ) -> ArtifactWorkspace:
        workspace_id = self._id(workspace_id, "workspace_id")
        if expected_version < 1 or "expected_version" in changes:
            raise ValueError("workspace updates require one positive expected_version")
        if not set(changes).issubset({"name", "status", "labels"}):
            raise ValueError("workspace updates support only name, status and labels")
        body = {"expected_version": expected_version, **changes}
        return self._parse(
            ArtifactWorkspace,
            await self._request(
                "PATCH",
                f"/v1/artifact-workspaces/{workspace_id}",
                json_body=body,
            ),
        )

    async def list_artifacts(
        self, workspace_id: str, *, directory: str = "", limit: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        workspace_id = self._id(workspace_id, "workspace_id")
        params: dict[str, Any] = {"directory": directory, "limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        return await self._request(
            "GET", f"/v1/artifact-workspaces/{workspace_id}/artifacts", params=params
        )

    async def list_artifact_page(
        self, workspace_id: str, *, directory: str = "", limit: int = 50, cursor: str | None = None
    ) -> ArtifactPage:
        return self._parse(
            ArtifactPage,
            await self.list_artifacts(
                workspace_id, directory=directory, limit=limit, cursor=cursor
            ),
        )

    async def get_artifact(self, workspace_id: str, artifact_id: str) -> Artifact:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(artifact_id, "artifact_id")
        data = await self._request(
            "GET", f"/v1/artifact-workspaces/{workspace_id}/artifacts/{artifact_id}"
        )
        return self._parse(Artifact, data)

    async def create_text(
        self, workspace_id: str, *, operation_id: str, path: str, text: str
    ) -> ArtifactUpload:
        workspace_id = self._id(workspace_id, "workspace_id")
        operation_id = self._id(operation_id, "operation_id")
        data = await self._request(
            "POST",
            f"/v1/artifact-workspaces/{workspace_id}/artifacts",
            json_body={
                "schema_version": "1",
                "operation_id": operation_id,
                "kind": "text",
                "path": path,
                "text": text,
            },
            headers={"Idempotency-Key": operation_id},
        )
        return self._parse(ArtifactUpload, data)

    async def update_text(
        self,
        workspace_id: str,
        artifact_id: str,
        *,
        operation_id: str,
        revision_id: str,
        path: str,
        text: str,
    ) -> ArtifactUpload:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(artifact_id, "artifact_id")
        operation_id = self._id(operation_id, "operation_id")
        revision_id = self._id(revision_id, "revision_id")
        data = await self._request(
            "PUT",
            f"/v1/artifact-workspaces/{workspace_id}/artifacts/{artifact_id}/content",
            json_body={
                "operation_id": operation_id,
                "expected_revision": revision_id,
                "path": path,
                "text": text,
            },
            headers={"Idempotency-Key": operation_id},
        )
        return self._parse(ArtifactUpload, data)

    async def make_directory(self, workspace_id: str, *, operation_id: str, path: str) -> Artifact:
        workspace_id = self._id(workspace_id, "workspace_id")
        operation_id = self._id(operation_id, "operation_id")
        data = await self._request(
            "POST",
            f"/v1/artifact-workspaces/{workspace_id}/artifacts",
            json_body={
                "schema_version": "1",
                "operation_id": operation_id,
                "kind": "directory",
                "path": path,
            },
            headers={"Idempotency-Key": operation_id},
        )
        return self._parse(Artifact, data)

    async def get_revision(self, workspace_id: str, ref: ArtifactReference) -> ArtifactRevision:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(ref.artifact_id, "artifact_id")
        revision_id = self._id(ref.revision_id, "revision_id")
        data = await self._request(
            "GET",
            f"/v1/artifacts/{artifact_id}/revisions/{revision_id}",
            params={"artifact_workspace_id": workspace_id},
        )
        return self._parse(ArtifactRevision, data)

    async def move_artifact(
        self,
        workspace_id: str,
        artifact_id: str,
        *,
        operation_id: str,
        path: str,
        expected_version: int,
    ) -> Artifact:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(artifact_id, "artifact_id")
        operation_id = self._id(operation_id, "operation_id")
        data = await self._request(
            "PATCH",
            f"/v1/artifact-workspaces/{workspace_id}/artifacts/{artifact_id}",
            json_body={
                "operation_id": operation_id,
                "path": path,
                "expected_version": expected_version,
            },
            headers={"Idempotency-Key": operation_id},
        )
        return self._parse(Artifact, data)

    async def delete_artifact(
        self, workspace_id: str, artifact_id: str, *, operation_id: str, expected_version: int
    ) -> Artifact:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(artifact_id, "artifact_id")
        operation_id = self._id(operation_id, "operation_id")
        data = await self._request(
            "DELETE",
            f"/v1/artifact-workspaces/{workspace_id}/artifacts/{artifact_id}",
            params={"expected_version": expected_version},
            headers={"Idempotency-Key": operation_id},
        )
        return self._parse(Artifact, data)

    async def _upload_action(
        self, workspace_id: str, upload_id: str, action: str, method: str = "POST"
    ) -> ArtifactUpload:
        workspace_id = self._id(workspace_id, "workspace_id")
        upload_id = self._id(upload_id, "upload_id")
        data = await self._request(
            method, f"/v1/artifact-workspaces/{workspace_id}/uploads/{upload_id}{action}"
        )
        return self._parse(ArtifactUpload, data)

    async def upload_status(self, workspace_id: str, upload_id: str) -> ArtifactUpload:
        workspace_id = self._id(workspace_id, "workspace_id")
        upload_id = self._id(upload_id, "upload_id")
        data = await self._request(
            "GET", f"/v1/artifact-workspaces/{workspace_id}/uploads/{upload_id}"
        )
        return self._parse(ArtifactUpload, data)

    async def begin_upload(
        self,
        workspace_id: str,
        *,
        operation_id: str,
        path: str,
        size_bytes: int,
        sha256: str,
        content_type: str,
        artifact_id: str | None = None,
        expected_revision: str | None = None,
    ) -> ArtifactUpload:
        workspace_id = self._id(workspace_id, "workspace_id")
        operation_id = self._id(operation_id, "operation_id")
        if size_bytes < 0 or not _SHA256.fullmatch(sha256):
            raise ValueError("upload requires a nonnegative size and lowercase SHA-256")
        body: dict[str, Any] = {
            "schema_version": "1",
            "operation_id": operation_id,
            "path": path,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "content_type": content_type,
        }
        if artifact_id is not None:
            body["artifact_id"] = self._id(artifact_id, "artifact_id")
        if expected_revision is not None:
            body["expected_revision"] = self._id(expected_revision, "expected_revision")
        if (artifact_id is None) != (expected_revision is None):
            raise ValueError("artifact_id and expected_revision must be supplied together")
        data = await self._request(
            "POST",
            f"/v1/artifact-workspaces/{workspace_id}/uploads",
            json_body=body,
            headers={"Idempotency-Key": operation_id},
        )
        return self._parse(ArtifactUpload, data)

    async def upload_part(
        self, workspace_id: str, upload_id: str, *, offset: int, content: bytes
    ) -> ArtifactUpload:
        workspace_id = self._id(workspace_id, "workspace_id")
        upload_id = self._id(upload_id, "upload_id")
        if offset < 0 or not content or len(content) > 8 * 1024 * 1024:
            raise ValueError("upload parts require a nonnegative offset and 1..8 MiB of bytes")
        data = await self._request(
            "PUT",
            f"/v1/artifact-workspaces/{workspace_id}/uploads/{upload_id}/parts",
            params={"offset": offset},
            headers={"Content-Type": "application/octet-stream"},
            content=content,
        )
        return self._parse(ArtifactUpload, data)

    async def abort_upload(self, workspace_id: str, upload_id: str) -> ArtifactUpload:
        return await self._upload_action(workspace_id, upload_id, "", "DELETE")

    async def upload_file(
        self,
        workspace_id: str,
        source: BinaryIO,
        *,
        operation_id: str,
        path: str,
        size_bytes: int,
        sha256: str,
        content_type: str,
        part_size: int | None = None,
    ) -> ArtifactUpload:
        """Upload bounded parts from a source with declared size and digest.

        Uncertain acknowledgements are never replayed automatically.
        """
        if size_bytes < 0 or not _SHA256.fullmatch(sha256):
            raise ValueError("upload requires a nonnegative size and lowercase SHA-256")
        if part_size is not None and not 1 <= part_size <= 8 * 1024 * 1024:
            raise ValueError("part_size must be between 1 byte and 8 MiB")
        caps = await self.capabilities()
        limit = int(caps.get("max_upload_part_bytes", 0))
        max_size = int(caps.get("max_upload_bytes", 0))
        max_parts = int(caps.get("max_upload_parts", 0))
        if not 0 < limit <= 8 * 1024 * 1024 or size_bytes > max_size:
            raise ValueError("upload exceeds or lacks the server's advertised bounds")
        chunk_size = min(part_size or limit, limit)
        count = (size_bytes + chunk_size - 1) // chunk_size
        if count > max_parts:
            raise ValueError("upload exceeds the server's advertised part count")
        workspace_id = self._id(workspace_id, "workspace_id")
        operation_id = self._id(operation_id, "operation_id")
        upload = await self.begin_upload(
            workspace_id,
            operation_id=operation_id,
            path=path,
            size_bytes=size_bytes,
            sha256=sha256,
            content_type=content_type,
        )
        digest = hashlib.sha256()
        offset = 0
        part_count = 0
        try:
            while offset < size_bytes:
                chunk = source.read(min(chunk_size, size_bytes - offset))
                if not chunk:
                    raise ValueError("upload source ended before its declared size")
                if len(chunk) > chunk_size or offset + len(chunk) > size_bytes:
                    raise ValueError("upload source returned more bytes than requested")
                part_count += 1
                if part_count > max_parts:
                    raise ValueError("upload source requires more parts than the server permits")
                digest.update(chunk)
                await self.upload_part(workspace_id, upload.id, offset=offset, content=chunk)
                offset += len(chunk)
            if source.read(1):
                raise ValueError("upload source contains more bytes than its declared size")
            if digest.hexdigest() != sha256:
                raise ValueError("upload source SHA-256 does not match the declared digest")
            return await self._upload_action(workspace_id, upload.id, "/finalize")
        except WoobeConnectionError as exc:
            raise ArtifactUploadUncertainError(upload.id) from exc
        except BaseException:
            try:
                await asyncio.shield(self.abort_upload(workspace_id, upload.id))
            except Exception:
                pass
            raise

    async def search(
        self,
        workspace_id: str,
        query: str,
        *,
        mode: str = "",
        cursor: str | None = None,
        limit: int = 50,
    ) -> ArtifactSearchPage:
        workspace_id = self._id(workspace_id, "workspace_id")
        params: dict[str, Any] = {"query": query, "limit": limit}
        if mode:
            params["mode"] = mode
        if cursor:
            params["cursor"] = cursor
        return self._parse(
            ArtifactSearchPage,
            await self._request(
                "GET", f"/v1/artifact-workspaces/{workspace_id}/search", params=params
            ),
        )

    async def read_source(
        self, workspace_id: str, source: SourceReference, *, offset: int = 0, max_chars: int = 8192
    ) -> SourceRead:
        workspace_id = self._id(workspace_id, "workspace_id")
        if offset < 0 or not 1 <= max_chars <= 65_536:
            raise ValueError("source read bounds are invalid")
        data = await self._request(
            "POST",
            "/v1/artifact-sources/read",
            params={"artifact_workspace_id": workspace_id},
            json_body={
                "source": source.model_dump(exclude_none=True),
                "offset": offset,
                "max_chars": max_chars,
            },
        )
        return self._parse(SourceRead, data)

    async def request_processing(
        self,
        workspace_id: str,
        artifact_id: str,
        *,
        operation_id: str,
        revision_id: str,
        profile_id: str | None = None,
        profile_revision: int | None = None,
    ) -> ArtifactProcessingJob:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(artifact_id, "artifact_id")
        operation_id = self._id(operation_id, "operation_id")
        revision_id = self._id(revision_id, "revision_id")
        if (profile_id is None) != (profile_revision is None):
            raise ValueError("profile_id and profile_revision must be supplied together")
        if profile_id is not None:
            profile_id = self._id(profile_id, "profile_id")
            if profile_revision is None or profile_revision < 1:
                raise ValueError("profile_revision must be positive")
        body = {
            "schema_version": "1",
            "operation_id": operation_id,
            "revision_id": revision_id,
            "profile_id": profile_id,
            "profile_revision": profile_revision,
        }
        data = await self._request(
            "POST",
            f"/v1/artifacts/{artifact_id}/processing",
            params={"artifact_workspace_id": workspace_id},
            json_body=body,
            headers={"Idempotency-Key": operation_id},
        )
        return self._parse(ArtifactProcessingJob, data)

    async def processing_job(
        self, workspace_id: str, artifact_id: str, job_id: str
    ) -> ArtifactProcessingJob:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(artifact_id, "artifact_id")
        job_id = self._id(job_id, "job_id")
        data = await self._request(
            "GET",
            f"/v1/artifacts/{artifact_id}/processing/{job_id}",
            params={"artifact_workspace_id": workspace_id},
        )
        return self._parse(ArtifactProcessingJob, data)

    async def cancel_processing(
        self, workspace_id: str, artifact_id: str, job_id: str
    ) -> ArtifactProcessingJob:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(artifact_id, "artifact_id")
        job_id = self._id(job_id, "job_id")
        data = await self._request(
            "POST",
            f"/v1/artifacts/{artifact_id}/processing/{job_id}/cancel",
            params={"artifact_workspace_id": workspace_id},
        )
        return self._parse(ArtifactProcessingJob, data)

    async def create_processing_profile(
        self, *, profile_id: str, revision: int, recipe: dict[str, Any]
    ) -> ProcessingProfile:
        profile_id = self._id(profile_id, "profile_id")
        if revision < 1:
            raise ValueError("profile revision must be positive")
        data = await self._request(
            "POST",
            "/v1/artifact-processing-profiles",
            json_body={
                "schema_version": "1",
                "id": profile_id,
                "revision": revision,
                "recipe": recipe,
            },
        )
        return self._parse(ProcessingProfile, data)

    async def list_processing_profiles(
        self, *, limit: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._request("GET", "/v1/artifact-processing-profiles", params=params)

    async def get_processing_profile(self, profile_id: str, revision: int) -> ProcessingProfile:
        profile_id = self._id(profile_id, "profile_id")
        if revision < 1:
            raise ValueError("profile revision must be positive")
        data = await self._request(
            "GET", f"/v1/artifact-processing-profiles/{profile_id}/revisions/{revision}"
        )
        return self._parse(ProcessingProfile, data)

    async def bind_processing_profile(
        self,
        workspace_id: str,
        *,
        expected_version: int,
        profile_id: str | None = None,
        revision: int | None = None,
    ) -> ArtifactWorkspace:
        workspace_id = self._id(workspace_id, "workspace_id")
        if expected_version < 1:
            raise ValueError("expected_version must be positive")
        if (profile_id is None) != (revision is None):
            raise ValueError("profile_id and revision must be supplied together")
        if profile_id is not None:
            profile_id = self._id(profile_id, "profile_id")
            if revision is None or revision < 1:
                raise ValueError("profile revision must be positive")
        body = {
            "expected_version": expected_version,
            "profile_id": profile_id,
            "profile_revision": revision,
        }
        data = await self._request(
            "PUT", f"/v1/artifact-workspaces/{workspace_id}/processing-profile", json_body=body
        )
        return self._parse(ArtifactWorkspace, data)

    async def document_index(self, workspace_id: str, index_id: str) -> ArtifactIndex:
        workspace_id = self._id(workspace_id, "workspace_id")
        index_id = self._id(index_id, "index_id")
        return self._parse(
            ArtifactIndex,
            await self._request(
                "GET",
                f"/v1/document-indexes/{index_id}",
                params={"artifact_workspace_id": workspace_id},
            ),
        )

    async def list_document_nodes(
        self,
        workspace_id: str,
        index_id: str,
        *,
        parent_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ArtifactNodePage:
        workspace_id = self._id(workspace_id, "workspace_id")
        index_id = self._id(index_id, "index_id")
        params: dict[str, Any] = {"artifact_workspace_id": workspace_id, "limit": limit}
        if parent_id:
            params["parent_id"] = self._id(parent_id, "parent_id")
        if cursor:
            params["cursor"] = cursor
        return self._parse(
            ArtifactNodePage,
            await self._request("GET", f"/v1/document-indexes/{index_id}/nodes", params=params),
        )

    async def download(
        self, workspace_id: str, ref: ArtifactReference, *, range_header: str | None = None
    ) -> ArtifactDownload:
        workspace_id = self._id(workspace_id, "workspace_id")
        artifact_id = self._id(ref.artifact_id, "artifact_id")
        revision_id = self._id(ref.revision_id, "revision_id")
        headers = {"Accept": "application/octet-stream"}
        if range_header:
            headers["Range"] = range_header
        response = await self._request(
            "GET",
            f"/v1/artifacts/{artifact_id}/revisions/{revision_id}/content",
            params={"artifact_workspace_id": workspace_id},
            headers=headers,
            stream=True,
        )
        return ArtifactDownload(response)

    async def upload_path(
        self, workspace_id: str, path: str | Path, **metadata: Any
    ) -> ArtifactUpload:
        with Path(path).open("rb") as source:
            return await self.upload_file(workspace_id, source, **metadata)


class ArtifactUploadUncertainError(WoobeConnectionError):
    """An upload-part ACK was lost; use ``upload_id`` with upload_status to reconcile."""

    def __init__(self, upload_id: str) -> None:
        self.upload_id = upload_id
        super().__init__(
            "Artifact upload outcome is uncertain; inspect its status before sending more parts"
        )
