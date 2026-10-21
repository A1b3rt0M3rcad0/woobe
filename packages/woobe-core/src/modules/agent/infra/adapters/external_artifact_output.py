"""Validate and persist only explicitly bound external Tool outputs."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from uuid import UUID, uuid5

from modules.agent.application.dtos.tools_dtos import ToolArtifactOutputBinding
from shared.contracts.artifact_reference import ArtifactReference


_OUTPUT_NAMESPACE = UUID("16318c4f-4063-5844-88f2-f08fd5a4a47c")


class ExternalOutputError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ExternalOperationPending(ExternalOutputError):
    def __init__(self, operation_ref: str, status: str):
        super().__init__("EXTERNAL_OPERATION_PENDING", "External Tool operation is still pending")
        self.operation_ref = operation_ref
        self.status = status


def json_pointer(value, pointer: str):
    current = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if "~" in re.sub(r"~[01]", "", raw):
            raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External output JSON pointer is malformed")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External output does not match its configured schema")
    return current


def remove_json_pointer(value, pointer: str):
    if not pointer:
        return value
    try:
        tokens = [item.replace("~1", "/").replace("~0", "~") for item in pointer[1:].split("/")]
        current = value
        for token in tokens[:-1]:
            current = current[int(token)] if isinstance(current, list) else current[token]
        if isinstance(current, dict):
            current.pop(tokens[-1], None)
        elif isinstance(current, list) and tokens[-1].isdigit() and int(tokens[-1]) < len(current):
            current.pop(int(tokens[-1]))
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return value


def exact_source_refs(config: dict, input_data: dict, transfer=None) -> list[dict[str, str]]:
    refs: dict[tuple[str, str], dict[str, str]] = {}
    for item in getattr(transfer, "input_refs", ()):
        reference = ArtifactReference.model_validate(item)
        refs[(reference.artifact_id, reference.revision_id)] = reference.model_dump(mode="json")
    for binding in config.get("file_bindings") or []:
        name = str(binding.get("input_name") or "")
        try:
            reference = ArtifactReference.model_validate(input_data.get(name))
        except (TypeError, ValueError):
            continue
        refs[(reference.artifact_id, reference.revision_id)] = reference.model_dump(mode="json")
    return list(refs.values())


def _decode_binding(raw: dict, *, allowed_modes: set[str]) -> ToolArtifactOutputBinding:
    try:
        binding = ToolArtifactOutputBinding.model_validate(raw)
    except (TypeError, ValueError) as error:
        raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Artifact output binding is invalid") from error
    if binding.mode not in allowed_modes:
        raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Artifact output mode is incompatible with this Tool")
    return binding


def _payload_for_binding(binding: ToolArtifactOutputBinding, source, *, default_content_type=None):
    body = source.get("body") if isinstance(source, dict) else None
    data = None
    content_type = default_content_type
    expected_digest = None
    operation_ref = None
    success = True
    if binding.success_pointer:
        # Check the provider's application status before requiring its success
        # payload fields. Error responses commonly omit those fields entirely.
        success = json_pointer(body, binding.success_pointer) is True
    if not success:
        raise ExternalOutputError("EXTERNAL_TOOL_APPLICATION_ERROR", "External Tool reported an application error")
    if binding.operation_ref_pointer:
        operation_ref = json_pointer(body, binding.operation_ref_pointer)
        if not isinstance(operation_ref, str) or not operation_ref or len(operation_ref) > 512 or any(
            ord(char) < 32 or ord(char) == 127 for char in operation_ref
        ):
            raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool operation reference is invalid")
    if binding.status_pointer:
        status = json_pointer(body, binding.status_pointer)
        if not isinstance(status, str):
            raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool operation status is invalid")
        if status.strip().lower() in binding.pending_statuses:
            raise ExternalOperationPending(operation_ref, status.strip().lower())
    if binding.mode == "response_body":
        data = source.get("response_content") if isinstance(source, dict) else None
    elif binding.mode == "json_base64":
        if not isinstance(body, (dict, list)):
            raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool did not return the configured JSON output")
        encoded = json_pointer(body, binding.data_pointer)
        if not isinstance(encoded, str) or len(encoded) > ((binding.max_bytes + 2) // 3) * 4 + 16:
            raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool base64 output is invalid or too large")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as error:
            raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool base64 output is invalid") from error
        if binding.content_type_pointer:
            content_type = json_pointer(body, binding.content_type_pointer)
        if binding.sha256_pointer:
            expected_digest = json_pointer(body, binding.sha256_pointer)
    if not isinstance(data, bytes):
        raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool output bytes are unavailable")
    if len(data) > binding.max_bytes:
        raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool output exceeds its configured byte limit")
    if not isinstance(content_type, str):
        raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool output media type is missing")
    content_type = content_type.split(";", 1)[0].strip().lower()
    if content_type not in set(binding.content_types):
        raise ExternalOutputError("EXTERNAL_OUTPUT_INVALID", "External Tool output media type is not allowed")
    digest = hashlib.sha256(data).hexdigest()
    if expected_digest is not None and expected_digest != digest:
        raise ExternalOutputError("UPLOAD_INTEGRITY_MISMATCH", "External Tool output hash does not match its receipt")
    return data, content_type, digest, operation_ref


async def persist_external_output(
    *,
    binding: ToolArtifactOutputBinding,
    source,
    default_content_type,
    ingestor,
    run_id: str,
    tool_id: str,
    source_refs: list[dict[str, str]],
):
    data, content_type, digest, remote_ref = _payload_for_binding(
        binding,
        source,
        default_content_type=default_content_type,
    )
    identity = {
        "run_id": run_id,
        "tool_id": tool_id,
        "binding": binding.name,
        "remote_ref": remote_ref,
        "path": binding.path,
    }
    # A provider operation has one durable publication identity across repeated
    # ready responses. If the provider changes bytes for the same operation,
    # upload fingerprint validation reports an idempotency conflict instead of
    # silently creating a second Artifact revision.
    if remote_ref is None:
        identity["sha256"] = digest
    operation_id = str(uuid5(
        _OUTPUT_NAMESPACE,
        hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    ))
    try:
        output = await ingestor(
            operation_id=operation_id,
            path=binding.path,
            content=data,
            content_type=content_type,
            producer_id=tool_id,
            external_operation_ref=remote_ref,
            source_refs=source_refs,
        )
    except Exception as error:
        raise ExternalOutputError(
            "EXTERNAL_OPERATION_UNCERTAIN",
            "External Tool output could not be durably published",
        ) from error
    if not isinstance(output, dict):
        raise ExternalOutputError("EXTERNAL_OPERATION_UNCERTAIN", "External Tool output receipt is unavailable")
    output["source_refs"] = source_refs
    return output


def scrub_bound_output(result, bindings: list[ToolArtifactOutputBinding]):
    if not isinstance(result.output, dict):
        result.output = {}
    for binding in bindings:
        if binding.mode == "json_base64" and isinstance(result.output.get("body"), (dict, list)):
            result.output["body"] = remove_json_pointer(result.output["body"], binding.data_pointer)
    result.response_content = None
    result.response_content_type = None
    return result


async def ingest_http_outputs(result, *, config, input_data, transfer, context, tool_id):
    raw_bindings = config.get("output_bindings") or []
    if not raw_bindings:
        result.response_content = None
        result.response_content_type = None
        return result
    if not result.success:
        result.response_content = None
        result.response_content_type = None
        return result
    ingestor = getattr(context, "external_output_ingestor", None) if context else None
    if not callable(ingestor):
        raise ExternalOutputError("ARTIFACT_ACCESS_DENIED", "Artifact output publication is not authorized for this Run")
    if context is None or context.run_id is None or context.terminal_persisted:
        raise ExternalOutputError(
            "EXTERNAL_OPERATION_UNCERTAIN",
            "External Tool result arrived after its Run stopped accepting output",
        )
    bindings = [_decode_binding(item, allowed_modes={"response_body", "json_base64"}) for item in raw_bindings]
    output = result.output if isinstance(result.output, dict) else {}
    source = {
        "body": output.get("body"),
        "response_content": result.response_content,
    }
    content_type = result.response_content_type
    if not isinstance(content_type, str):
        headers = output.get("headers") if isinstance(output.get("headers"), dict) else {}
        content_type = next((value for key, value in headers.items() if str(key).lower() == "content-type"), None)
    sources = exact_source_refs(config, input_data, transfer)
    pending = []
    for binding in bindings:
        if binding.status_pointer:
            try:
                _payload_for_binding(
                    binding, source,
                    default_content_type=content_type,
                )
            except ExternalOperationPending as operation:
                pending.append({
                    "binding": binding.name,
                    "operation_ref": operation.operation_ref,
                    "status": operation.status,
                })
    if pending:
        result = scrub_bound_output(result, bindings)
        result.output["external_operations"] = pending
        result.output["body"] = {"external_operations": pending}
        recorder = getattr(context, "run_event_recorder", None) if context else None
        if recorder is not None:
            for operation in pending:
                operation_id = str(uuid5(
                    _OUTPUT_NAMESPACE,
                    hashlib.sha256(json.dumps({
                        "run_id": str(context.run_id) if context.run_id else "",
                        "tool_id": tool_id,
                        "binding": operation["binding"],
                        "remote_ref": operation["operation_ref"],
                        "path": next(item.path for item in bindings if item.name == operation["binding"]),
                    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                ))
                try:
                    await recorder.emit(
                        "artifact.external_operation.pending",
                        {
                            "operation_id": operation_id,
                            "external_operation_ref": operation["operation_ref"],
                            "status": operation["status"],
                            "tool_id": tool_id,
                            "binding": operation["binding"],
                        },
                        durable=True,
                    )
                except Exception as error:
                    raise ExternalOutputError(
                        "EXTERNAL_OPERATION_UNCERTAIN",
                        "Pending External Tool operation could not be durably recorded",
                    ) from error
        return result
    published = []
    for binding in bindings:
        published.append(await persist_external_output(
            binding=binding,
            source=source,
            default_content_type=content_type,
            ingestor=ingestor,
            run_id=str(context.run_id) if context and context.run_id else "",
            tool_id=tool_id,
            source_refs=sources,
        ))
    result = scrub_bound_output(result, bindings)
    result.output["output_artifacts"] = published
    result.output["body"] = {"artifact_outputs": [item["artifact_id"] for item in published]}
    return result
