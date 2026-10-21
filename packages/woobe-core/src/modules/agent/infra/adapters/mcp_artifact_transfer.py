from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID, uuid5

from shared.contracts.artifact_reference import ArtifactReference
from shared.contracts.artifact_transfer import ArtifactTransferSource


_OPERATION_NAMESPACE = UUID("8a6debe2-8a89-5dcb-b551-53a6e713702d")


@dataclass(frozen=True)
class PreparedMcpTransfer:
    operation_id: str
    arguments: dict
    mode: str
    destination_host: str
    input_refs: tuple[dict[str, str], ...]
    file_hashes: tuple[dict[str, str | int], ...]
    temporary_urls: tuple[str, ...] = ()

    def receipt(self, state: str) -> dict:
        return {
            "operation_id": self.operation_id,
            "state": state,
            "mode": f"mcp_{self.mode}",
            "destination_host": self.destination_host,
            "input_refs": list(self.input_refs),
            "file_hashes": list(self.file_hashes),
        }


async def _read_source(source: ArtifactTransferSource, *, max_bytes: int) -> bytes:
    if source.content is None or source.size_bytes > max_bytes:
        raise ValueError("MCP Artifact transfer exceeds its negotiated byte limit")
    content = bytearray()
    digest = hashlib.sha256()
    try:
        async for chunk in source.content:
            if not isinstance(chunk, bytes) or len(content) + len(chunk) > max_bytes:
                raise ValueError("MCP Artifact transfer exceeds its negotiated byte limit")
            content.extend(chunk)
            digest.update(chunk)
    finally:
        close = getattr(source.content, "aclose", None)
        if callable(close):
            await close()
    if len(content) != source.size_bytes or digest.hexdigest() != source.sha256:
        raise ValueError("MCP Artifact bytes do not match the exact revision receipt")
    return bytes(content)


async def prepare_mcp_artifact_transfer(
    config: dict,
    arguments: dict,
    *,
    server_url: str,
    transfer_resolver,
    url_resolver,
    run_id: str,
    tool_id: str,
) -> PreparedMcpTransfer | None:
    bindings = config.get("file_bindings") or []
    if not bindings:
        return None
    host = urlparse(server_url).hostname
    if not host:
        raise ValueError("MCP Artifact transfer requires a bound HTTP server")
    mode = str(bindings[0].get("mode") or "")
    if any(binding.get("mode") != mode for binding in bindings):
        raise ValueError("One MCP Tool call cannot mix Artifact transfer modes")
    resolver = url_resolver if mode == "url" else transfer_resolver
    if not callable(resolver):
        raise PermissionError("MCP Artifact transfer is not authorized for this Run")

    output = dict(arguments)
    refs: list[dict[str, str]] = []
    hashes: list[dict[str, str | int]] = []
    temporary_urls: list[str] = []
    identity_inputs = []
    for binding in bindings:
        name = str(binding["input_name"])
        reference = ArtifactReference.model_validate(arguments.get(name))
        if mode == "url":
            source = await resolver(reference.artifact_id, reference.revision_id, host)
        else:
            source = await resolver(reference.artifact_id, reference.revision_id)
        if source.artifact_id != reference.artifact_id or source.revision_id != reference.revision_id:
            close = getattr(source.content, "aclose", None)
            if callable(close):
                await close()
            raise PermissionError("MCP Artifact transfer resolved a different revision")
        media_type = source.content_type.split(";", 1)[0].strip().lower()
        if media_type not in set(binding.get("content_types") or ()):
            close = getattr(source.content, "aclose", None)
            if callable(close):
                await close()
            raise ValueError("MCP Artifact media type is not allowed by the negotiated binding")
        if source.size_bytes > int(binding.get("max_bytes", 4 * 1024 * 1024)):
            close = getattr(source.content, "aclose", None)
            if callable(close):
                await close()
            raise ValueError("MCP Artifact exceeds the configured transfer limit")
        refs.append({"artifact_id": source.artifact_id, "revision_id": source.revision_id})
        hashes.append({"sha256": source.sha256, "size_bytes": source.size_bytes})
        identity_inputs.append({"ref": refs[-1], "sha256": source.sha256, "size": source.size_bytes})
        if mode == "base64":
            content = await _read_source(source, max_bytes=int(binding["max_bytes"]))
            output[name] = base64.b64encode(content).decode("ascii")
        else:
            signed_url = source.temporary_url or ""
            parsed = urlparse(signed_url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.fragment
                or type(source.expires_in_seconds) is not int
                or not 1 <= source.expires_in_seconds <= 60
                or len(signed_url) > 4096
            ):
                close = getattr(source.content, "aclose", None)
                if callable(close):
                    await close()
                raise ValueError("MCP temporary Artifact URL must be HTTPS and expire within 60 seconds")
            from modules.agent.infra.adapters.tool_executor import _validated_public_addresses

            if _validated_public_addresses(signed_url) is None:
                close = getattr(source.content, "aclose", None)
                if callable(close):
                    await close()
                raise ValueError("MCP temporary Artifact URL must be public and recipient-accessible")
            output[name] = signed_url
            temporary_urls.append(signed_url)

    identity = {
        "run_id": run_id,
        "tool_id": tool_id,
        "destination_host": host.lower(),
        "mode": mode,
        "files": identity_inputs,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return PreparedMcpTransfer(
        operation_id=str(uuid5(_OPERATION_NAMESPACE, digest)),
        arguments=output,
        mode=mode,
        destination_host=host.lower(),
        input_refs=tuple(refs),
        file_hashes=tuple(hashes),
        temporary_urls=tuple(temporary_urls),
    )


def scrub_mcp_temporary_urls(value, transfer: PreparedMcpTransfer):
    if isinstance(value, str):
        for url in transfer.temporary_urls:
            value = value.replace(url, "[REDACTED TEMPORARY ARTIFACT URL]")
        return value
    if isinstance(value, list):
        return [scrub_mcp_temporary_urls(item, transfer) for item in value]
    if isinstance(value, dict):
        return {key: scrub_mcp_temporary_urls(item, transfer) for key, item in value.items()}
    return value
