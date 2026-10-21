from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID, uuid5

from modules.agent.application.interfaces.http_tool_contract import CompiledHttpToolContract
from shared.contracts.artifact_reference import ArtifactReference
from shared.contracts.artifact_transfer import ArtifactTransferSource


_OPERATION_NAMESPACE = UUID("5b036915-82c7-5ce3-b84a-b7af0feec56c")


@dataclass(frozen=True)
class PreparedArtifactTransfer:
    body: str | AsyncIterator[bytes]
    headers: dict[str, str]
    operation_id: str
    destination_host: str
    mode: str
    input_refs: tuple[dict[str, str], ...]
    file_hashes: tuple[dict[str, str | int], ...]
    render_inputs: dict[str, str]

    def receipt(self, state: str, *, status_code: int | None = None) -> dict:
        value = {
            "operation_id": self.operation_id,
            "state": state,
            "mode": self.mode,
            "destination_host": self.destination_host,
            "input_refs": list(self.input_refs),
            "file_hashes": list(self.file_hashes),
        }
        if status_code is not None:
            value["status_code"] = status_code
        return value


def _source_stream(source: ArtifactTransferSource) -> AsyncIterator[bytes]:
    async def stream():
        if source.content is None:
            raise ValueError("Artifact transfer source has no byte stream")
        digest = hashlib.sha256()
        size = 0
        try:
            async for chunk in source.content:
                if not isinstance(chunk, bytes):
                    raise ValueError("Artifact storage returned a non-byte transfer chunk")
                size += len(chunk)
                if size > source.size_bytes:
                    raise ValueError("Artifact storage exceeded the verified revision size")
                digest.update(chunk)
                if chunk:
                    yield chunk
            if size != source.size_bytes or digest.hexdigest() != source.sha256:
                raise ValueError("Artifact transfer bytes do not match the revision receipt")
        finally:
            close = getattr(source.content, "aclose", None)
            if callable(close):
                await close()

    return stream()


def _multipart_prefix(boundary: str, part_name: str, source: ArtifactTransferSource) -> bytes:
    raw_filename = source.path.rsplit("/", 1)[-1]
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", raw_filename)[:255] or "artifact"
    media_type = source.content_type
    if any(char in media_type for char in "\r\n\x00"):
        raise ValueError("Artifact media type is invalid for HTTP transfer")
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{part_name}"; filename="{filename}"\r\n'
        f"Content-Type: {media_type}\r\n\r\n"
    ).encode("utf-8")


async def _multipart_body(
    boundary: str,
    parts: tuple[tuple[str, ArtifactTransferSource], ...],
) -> AsyncIterator[bytes]:
    try:
        for part_name, source in parts:
            yield _multipart_prefix(boundary, part_name, source)
            async for chunk in _source_stream(source):
                yield chunk
            yield b"\r\n"
        yield f"--{boundary}--\r\n".encode("ascii")
    finally:
        for _part_name, source in parts:
            close = getattr(source.content, "aclose", None)
            if callable(close):
                await close()


async def prepare_http_artifact_transfer(
    contract: CompiledHttpToolContract,
    input_data: dict,
    *,
    url: str,
    headers: dict[str, str],
    body: str | None,
    transfer_resolver,
    url_resolver=None,
    run_id: str,
    tool_id: str,
) -> PreparedArtifactTransfer | None:
    bindings = contract.config.get("file_bindings") or []
    if not bindings:
        return None
    mode = str(bindings[0].get("mode") or "")
    if any(str(binding.get("mode")) != mode for binding in bindings):
        raise ValueError("One HTTP request cannot mix Artifact transfer modes")
    if mode != "url" and body is not None:
        raise ValueError("Artifact transfer cannot be combined with a configured HTTP body")
    resolver = url_resolver if mode == "url" else transfer_resolver
    if not callable(resolver):
        raise PermissionError("Artifact transfer is not authorized for this Run")

    parts: list[tuple[str, ArtifactTransferSource]] = []
    refs: list[dict[str, str]] = []
    file_hashes: list[dict[str, str | int]] = []
    idempotency_headers: set[str] = set()
    total_size = 0
    render_inputs: dict[str, str] = {}
    for binding in bindings:
        name = str(binding["input_name"])
        reference = ArtifactReference.model_validate(input_data.get(name))
        if mode == "url":
            if not callable(url_resolver):
                raise PermissionError("Temporary Artifact URLs are unavailable for this storage profile")
            source = await resolver(
                reference.artifact_id,
                reference.revision_id,
                urlparse(url).hostname,
            )
        else:
            source = await resolver(reference.artifact_id, reference.revision_id)
        try:
            if source.artifact_id != reference.artifact_id or source.revision_id != reference.revision_id:
                raise PermissionError("Artifact transfer resolved a different revision")
            if source.size_bytes > int(binding["max_bytes"]):
                raise ValueError("Artifact exceeds the HTTP Tool transfer size limit")
            media_type = source.content_type.split(";", 1)[0].strip().lower()
            if media_type not in set(binding["content_types"]):
                raise ValueError("Artifact media type is not allowed by this HTTP Tool binding")
            if mode == "url":
                parsed_url = urlparse(source.temporary_url or "")
                if (
                    parsed_url.scheme != "https"
                    or not parsed_url.hostname
                    or parsed_url.username is not None
                    or parsed_url.password is not None
                    or parsed_url.fragment
                    or type(source.expires_in_seconds) is not int
                    or not 1 <= source.expires_in_seconds <= 60
                    or len(source.temporary_url) > 4096
                ):
                    raise ValueError("Temporary Artifact URL must be HTTPS and expire within 60 seconds")
                from modules.agent.infra.adapters.tool_executor import _validated_public_addresses

                if _validated_public_addresses(source.temporary_url) is None:
                    raise ValueError("Temporary Artifact URL must resolve to a public recipient-accessible host")
                render_inputs[name] = source.temporary_url
        except BaseException:
            close = getattr(source.content, "aclose", None)
            if callable(close):
                await close()
            for _prior_name, prior_source in parts:
                close = getattr(prior_source.content, "aclose", None)
                if callable(close):
                    await close()
            raise
        total_size += source.size_bytes
        parts.append((str(binding["part_name"]), source))
        refs.append({"artifact_id": source.artifact_id, "revision_id": source.revision_id})
        file_hashes.append({"sha256": source.sha256, "size_bytes": source.size_bytes})
        if binding.get("idempotency_header"):
            idempotency_headers.add(str(binding["idempotency_header"]))

    if total_size > 50 * 1024 * 1024:
        raise ValueError("Combined Artifact transfer exceeds the 50 MiB Run limit")
    if len(idempotency_headers) > 1:
        raise ValueError("All Artifact bindings in one request must use the same idempotency header")

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Artifact transfer requires an approved HTTPS destination")

    identity = {
        "run_id": run_id,
        "tool_id": tool_id,
        "contract_hash": contract.contract_hash,
        "destination": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        "input_refs": refs,
        "file_hashes": file_hashes,
        "mode": mode,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    operation_id = str(uuid5(_OPERATION_NAMESPACE, digest))

    if mode == "url":
        transfer_body = body or ""
    elif mode == "bytes":
        source = parts[0][1]
        transfer_body = _source_stream(source)
        headers["Content-Type"] = source.content_type
        headers["Content-Length"] = str(source.size_bytes)
    else:
        boundary = "woobe-" + hashlib.sha256(operation_id.encode()).hexdigest()[:32]
        transfer_body = _multipart_body(boundary, tuple(parts))
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        content_length = sum(
            len(_multipart_prefix(boundary, part_name, source)) + source.size_bytes + 2
            for part_name, source in parts
        ) + len(f"--{boundary}--\r\n".encode("ascii"))
        headers["Content-Length"] = str(content_length)
    if idempotency_headers:
        header = next(iter(idempotency_headers))
        headers[header] = operation_id

    return PreparedArtifactTransfer(
        body=transfer_body,
        headers=headers,
        operation_id=operation_id,
        destination_host=parsed.hostname.lower(),
        mode=mode,
        input_refs=tuple(refs),
        file_hashes=tuple(file_hashes),
        render_inputs=render_inputs,
    )


def scrub_temporary_urls(value, transfer: PreparedArtifactTransfer):
    """Keep short-lived storage capabilities out of model/tool result history."""
    if not transfer.render_inputs:
        return value
    replacements = tuple(transfer.render_inputs.values())
    if isinstance(value, str):
        for url in replacements:
            value = value.replace(url, "[REDACTED TEMPORARY ARTIFACT URL]")
        return value
    if isinstance(value, list):
        return [scrub_temporary_urls(item, transfer) for item in value]
    if isinstance(value, dict):
        return {
            key: scrub_temporary_urls(item, transfer)
            for key, item in value.items()
        }
    return value
