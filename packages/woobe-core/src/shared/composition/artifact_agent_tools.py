"""Run-scoped Agent Tools backed by the governed Artifact application services."""

from __future__ import annotations

import json
import hashlib
from typing import Any, Callable, Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

from modules.artifacts.application.contracts.api import SourceReference
from modules.artifacts.application.contracts.files import WriteText
from modules.artifacts.application.contracts.indexes import ListIndexNodes, ReadIndex
from modules.artifacts.application.contracts.jobs import ProcessingRequest, RequestProcessing
from modules.artifacts.application.contracts.representations import SourceReadDefinition
from modules.artifacts.application.runtime_scope import RunArtifactContext
from modules.artifacts.domain.models import Action, ArtifactError
from modules.agent.domain.model_spec import ModelSpec
from modules.agent.infra.models.image_generation import image_generation_constraints


_TOOL_NAMESPACE = UUID("d0b14746-1c90-52a8-8c42-f4d8ef87553a")


class _ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _ListArgs(_ToolArguments):
    directory: str = ""
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = None


class _InspectArgs(_ToolArguments):
    artifact_id: str
    revision_id: str


class _SearchArgs(_ToolArguments):
    query: str = Field(min_length=1, max_length=256)
    mode: str = "text"
    limit: int = Field(default=10, ge=1, le=20)
    cursor: str | None = None


class _OutlineArgs(_ToolArguments):
    document_index_id: str
    parent_id: str | None = None
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = None


class _ReadArgs(_ToolArguments):
    source: SourceReference
    offset: int = Field(default=0, ge=0)
    max_chars: int = Field(default=4096, ge=1, le=8192)


class _WriteArgs(_ToolArguments):
    path: str = Field(min_length=1, max_length=1024)
    text: str = Field(max_length=32768)
    artifact_id: str | None = None
    expected_revision: str | None = None


class _ProcessArgs(_ToolArguments):
    artifact_id: str
    revision_id: str
    profile_id: str | None = None
    profile_revision: int | None = Field(default=None, ge=1)


class _GenerateImageArgs(_ToolArguments):
    prompt: str = Field(min_length=1, max_length=8192)
    path: str = Field(default="generated/image", min_length=1, max_length=1024)
    size: str | None = Field(default=None, max_length=16)
    count: int = Field(default=1, ge=1, le=4)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value):
        from modules.artifacts.domain.models import logical_path

        return logical_path(value)


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()


def _definition(name: str, description: str, model: type[BaseModel]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": _schema(model),
        },
    }


def _json(value: Any) -> Any:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    if isinstance(value, tuple):
        return [_json(item) for item in value]
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    return value


def _operation_id(run_id: str, name: str, args: BaseModel) -> str:
    canonical = json.dumps(args.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return str(uuid5(_TOOL_NAMESPACE, f"{run_id}:{name}:{canonical}"))


def build_runtime_artifact_tools(
    *, principal: Any, binding: Any, run_id: str, node_id: str | None = None,
    budget: dict[str, Any] | None = None, event_recorder: Any | None = None,
    event_recorder_provider: Callable[[], Any | None] | None = None,
    image_generation_spec: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[UUID, Any]]:
    """Build only the tools allowed by this accepted Run's effective binding."""
    from modules.artifacts.composition.composers.get_document_index import get_document_index_composer
    from modules.artifacts.composition.composers.get_file import get_file_composer
    from modules.artifacts.composition.composers.list_document_nodes import list_document_nodes_composer
    from modules.artifacts.composition.composers.list_files import list_files_composer
    from modules.artifacts.composition.composers.request_processing import request_processing_composer
    from modules.artifacts.composition.composers.search_documents import search_documents_composer
    from modules.artifacts.composition.files import build_file_service
    from modules.artifacts.composition.representations import build_representation_service

    run_id = str(run_id)
    output_nodes = frozenset({str(node_id)}) if node_id else frozenset()
    scope = RunArtifactContext(principal, binding, run_id, output_node_ids=output_nodes)
    actions = frozenset(Action(action) for action in binding.actions)
    definitions: list[dict[str, Any]] = []
    names: dict[str, str] = {}
    handlers: dict[UUID, Any] = {}
    budget = budget if budget is not None else {"calls": 0, "read_bytes": 0}
    read_cache: dict[str, dict[str, Any]] = {}

    def charge_call() -> None:
        if budget.get("calls", 0) >= 24:
            raise ArtifactError(
                "ARTIFACT_LIMIT_EXCEEDED",
                "Document exploration reached the per-Run Tool call budget; continue in a new Run",
            )
        budget["calls"] = budget.get("calls", 0) + 1

    def register(name: str, description: str, model: type[BaseModel], handler):
        identity = uuid5(_TOOL_NAMESPACE, name)
        definitions.append(_definition(name, description, model))
        names[name] = str(identity)
        handlers[identity] = handler

    if Action.READ in actions:
        list_files = list_files_composer()
        get_file = get_file_composer()
        get_index = get_document_index_composer()
        list_nodes = list_document_nodes_composer()
        representations = build_representation_service()

        async def list_handler(raw):
            charge_call()
            args = _ListArgs.model_validate(raw)
            page = await list_files(scope.list_files(
                directory=args.directory, limit=args.limit, cursor=args.cursor,
            ))
            return {"success": True, "output": {
                "items": [{"artifact_id": item.id, "revision_id": item.revision_id,
                           "path": item.path, "kind": item.kind, "version": item.version}
                          for item in page.items],
                "has_more": page.has_more, "next_cursor": page.next_cursor,
            }}

        async def inspect_handler(raw):
            charge_call()
            args = _InspectArgs.model_validate(raw)
            snapshot = await get_file(scope.read_file(args.artifact_id, args.revision_id))
            revision = snapshot.revision
            return {"success": True, "output": {
                "artifact_id": snapshot.artifact.id,
                "revision_id": revision.id if revision else None,
                "path": snapshot.artifact.path,
                "kind": snapshot.artifact.kind,
                "content_type": revision.content_type if revision else None,
                "size_bytes": revision.size_bytes if revision else 0,
                "sha256": revision.sha256 if revision else None,
            }}

        async def outline_handler(raw):
            charge_call()
            args = _OutlineArgs.model_validate(raw)
            request = ReadIndex(principal, binding.scope, binding.workspace_id,
                                args.document_index_id)
            index = await get_index(request)
            page = await list_nodes(ListIndexNodes(
                principal, binding.scope, binding.workspace_id, args.document_index_id,
                parent_id=args.parent_id, limit=args.limit, cursor=args.cursor,
            ))
            return {"success": True, "output": {
                "index": {"id": index.id, "artifact_id": index.artifact_id,
                          "revision_id": index.revision_id, "coverage": index.coverage,
                          "tree_kind": index.tree_kind, "root_node_id": index.root_node_id},
                "items": [_json(item) for item in page.items],
                "has_more": page.has_more, "next_cursor": page.next_cursor,
            }}

        async def read_handler(raw):
            args = _ReadArgs.model_validate(raw)
            charge_call()
            cache_key = json.dumps({
                "source": args.source.model_dump(mode="json"),
                "offset": args.offset,
                "max_chars": args.max_chars,
            }, sort_keys=True, separators=(",", ":"))
            if cache_key in read_cache:
                return read_cache[cache_key]
            remaining = 65_536 - int(budget.get("read_bytes", 0))
            bounded_chars = min(args.max_chars, remaining // 4)
            if bounded_chars < 1:
                raise ArtifactError(
                    "ARTIFACT_LIMIT_EXCEEDED",
                    "Document reading reached the per-Run 64 KiB budget; continue in a new Run",
                )
            result = await representations.read_source(scope.read_source(SourceReadDefinition(
                source=args.source, offset=args.offset, max_chars=bounded_chars,
            )))
            output = _json(result)
            text = output.get("text", "") if isinstance(output, dict) else ""
            budget["read_bytes"] = budget.get("read_bytes", 0) + len(text.encode("utf-8"))
            response = {"success": True, "output": output}
            read_cache[cache_key] = response
            return response

        register("woobe_artifact_list", "List files in the Run's bound Artifact Workspace.", _ListArgs, list_handler)
        register("woobe_artifact_inspect", "Inspect metadata for an exact Artifact revision.", _InspectArgs, inspect_handler)
        register("woobe_artifact_outline", "Read a page from an exact document index outline.", _OutlineArgs, outline_handler)
        register("woobe_artifact_read", "Read a bounded source excerpt with its exact citation.", _ReadArgs, read_handler)

    if Action.SEARCH in actions:
        search = search_documents_composer()

        async def search_handler(raw):
            charge_call()
            args = _SearchArgs.model_validate(raw)
            if args.mode not in {"text", "literal"}:
                raise ValueError("Search mode must be text or literal")
            page = await search(scope.search(
                args.query, mode=args.mode, limit=args.limit, cursor=args.cursor,
            ))
            return {"success": True, "output": _json(page)}

        register("woobe_artifact_search", "Search indexed document text in the bound Workspace.", _SearchArgs, search_handler)

    if Action.WRITE in actions:
        file_service = build_file_service()

        async def write_handler(raw):
            charge_call()
            args = _WriteArgs.model_validate(raw)
            if (args.artifact_id is None) != (args.expected_revision is None):
                raise ValueError("Updating a file requires both artifact_id and expected_revision")
            receipt = await file_service.write_text(WriteText(
                principal, binding.scope, binding.workspace_id,
                operation_id=_operation_id(run_id, "woobe_artifact_write", args),
                path=args.path, text=args.text, artifact_id=args.artifact_id,
                expected_revision=args.expected_revision, origin="agent", run_id=run_id,
                node_id=str(node_id) if node_id else None,
            ))
            reference = receipt.receipt
            content = args.text.encode("utf-8")
            output = {
                "artifact_id": reference.artifact_id,
                "revision_id": reference.revision_id,
                "path": args.path,
                "content_type": "text/plain; charset=utf-8",
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            recorder = event_recorder_provider() if event_recorder_provider else event_recorder
            if recorder is not None:
                await recorder.emit(
                    "artifact.available",
                    {
                        **output,
                        "run_id": run_id,
                        "node_id": str(node_id) if node_id else None,
                        "status": "available",
                    },
                    durable=True,
                )
            return {"success": True, "output": {
                **output,
            }}

        register("woobe_artifact_write", "Write bounded UTF-8 text using an idempotent Run receipt.", _WriteArgs, write_handler)

        if image_generation_spec is not None:
            spec = ModelSpec.from_dict(image_generation_spec)
            constraints = image_generation_constraints(spec)
            allowed_sizes = Literal.__getitem__(constraints.sizes) | None
            image_args = create_model(
                "_BoundedGenerateImageArgs",
                __base__=_GenerateImageArgs,
                size=(allowed_sizes, Field(default=None)),
                count=(int, Field(default=1, ge=1, le=constraints.max_images)),
            )

            async def generate_image_handler(raw):
                charge_call()
                args = image_args.model_validate(raw)
                from modules.agent.application.interfaces.execution_context import current_execution

                context = current_execution.get()
                invoker = getattr(context, "image_generation_invoker", None) if context else None
                if not callable(invoker):
                    raise ArtifactError("MODEL_BINDING_UNAVAILABLE", "Image generation operation is unavailable")
                return await invoker(
                    prompt=args.prompt,
                    path=args.path,
                    size=args.size,
                    count=args.count,
                    operation_id=_operation_id(run_id, "woobe_artifact_generate_image", args),
                    producer_id=names["woobe_artifact_generate_image"],
                )

            register(
                "woobe_artifact_generate_image",
                "Generate one or more images using the Run's declared image.generate ModelSpec and save them in the bound Workspace.",
                image_args,
                generate_image_handler,
            )

    if Action.PROCESS in actions:
        request_processing = request_processing_composer()

        async def process_handler(raw):
            charge_call()
            args = _ProcessArgs.model_validate(raw)
            if (args.profile_id is None) != (args.profile_revision is None):
                raise ValueError("Processing profile identity and revision must be supplied together")
            request = RequestProcessing(
                principal, binding.scope, binding.workspace_id, args.artifact_id,
                ProcessingRequest(
                    operation_id=_operation_id(run_id, "woobe_artifact_process", args),
                    revision_id=args.revision_id,
                    profile_id=args.profile_id,
                    profile_revision=args.profile_revision,
                ),
            )
            job = await request_processing(request)
            return {"success": True, "output": {"job_id": job.id, "status": job.status}}

        register("woobe_artifact_process", "Queue processing for an exact authorized revision; returns without polling.", _ProcessArgs, process_handler)

    return definitions, names, handlers
