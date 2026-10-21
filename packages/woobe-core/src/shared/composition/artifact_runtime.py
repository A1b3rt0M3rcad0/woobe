"""Composition bridge for runtime Artifact Workspace resolution."""

from modules.artifacts.composition.runtime_binding import (
    validate_runtime_artifact_references,
    resolve_runtime_artifact_workspace_binding,
)


def runtime_artifact_workspace_binding_resolver():
    return resolve_runtime_artifact_workspace_binding


def runtime_artifact_reference_validator():
    return validate_runtime_artifact_references


def configure_runtime_artifact_tools(
    *, principal, binding, run_id, node_id=None, budget=None, event_recorder=None,
    event_recorder_provider=None, image_generation_spec=None,
):
    """Build the internal tool inventory for one accepted Agent/Network Run."""
    from shared.composition.artifact_agent_tools import build_runtime_artifact_tools

    return build_runtime_artifact_tools(
        principal=principal,
        binding=binding,
        run_id=str(run_id),
        node_id=str(node_id) if node_id is not None else None,
        budget=budget,
        event_recorder=event_recorder,
        event_recorder_provider=event_recorder_provider,
        image_generation_spec=image_generation_spec,
    )


def configure_runtime_artifact_transfer_resolver(*, principal, binding, run_id, node_id=None):
    """Bind exact Artifact byte streams to the Run's current transfer grant."""
    from modules.artifacts.application.runtime_scope import RunArtifactContext
    from modules.artifacts.composition.files import build_file_service
    from shared.contracts.artifact_transfer import ArtifactTransferSource

    scope = RunArtifactContext(
        principal,
        binding,
        str(run_id),
        output_node_ids=frozenset({str(node_id)}) if node_id is not None else frozenset(),
    )
    files = build_file_service()

    async def resolve(artifact_id: str, revision_id: str) -> ArtifactTransferSource:
        request = scope.transfer_file(artifact_id, revision_id)
        snapshot, content = await files.open_content(request)
        revision = snapshot.revision
        if revision is None:
            await content.aclose()
            from modules.artifacts.domain.models import ArtifactError

            raise ArtifactError("SOURCE_UNAVAILABLE", "Artifact content is unavailable")
        return ArtifactTransferSource(
            artifact_id=snapshot.artifact.id,
            revision_id=revision.id,
            path=snapshot.artifact.path,
            content_type=revision.content_type,
            size_bytes=revision.size_bytes,
            sha256=revision.sha256,
            content=content,
        )

    return resolve


def configure_runtime_artifact_transfer_url_resolver(*, principal, binding, run_id, node_id=None):
    """Issue an exact-revision S3 URL with a one-minute expiry after current auth."""
    from modules.artifacts.application.runtime_scope import RunArtifactContext
    from modules.artifacts.composition.files import build_file_service
    from shared.contracts.artifact_transfer import ArtifactTransferSource

    scope = RunArtifactContext(
        principal,
        binding,
        str(run_id),
        output_node_ids=frozenset({str(node_id)}) if node_id is not None else frozenset(),
    )
    files = build_file_service()

    async def resolve(artifact_id: str, revision_id: str, _recipient_host: str):
        request = scope.transfer_file(artifact_id, revision_id)
        snapshot, url = await files.create_temporary_url(request, expires_seconds=60)
        revision = snapshot.revision
        return ArtifactTransferSource(
            artifact_id=snapshot.artifact.id,
            revision_id=revision.id,
            path=snapshot.artifact.path,
            content_type=revision.content_type,
            size_bytes=revision.size_bytes,
            sha256=revision.sha256,
            temporary_url=url,
            expires_in_seconds=60,
        )

    return resolve


def configure_runtime_artifact_vision_input_resolver(*, principal, binding, run_id, node_id=None):
    """Read one authorized, integrity-checked image revision into bounded ephemeral bytes."""
    from modules.artifacts.application.runtime_scope import RunArtifactContext
    from modules.artifacts.composition.files import build_file_service
    from modules.artifacts.composition.run_sources import record_run_source
    from modules.artifacts.domain.models import SourceRef

    scope = RunArtifactContext(
        principal,
        binding,
        str(run_id),
        output_node_ids=frozenset({str(node_id)}) if node_id is not None else frozenset(),
    )
    files = build_file_service()

    async def resolve(artifact_id: str, revision_id: str):
        snapshot, content = await files.read_visual_bytes(
            scope.read_file(artifact_id, revision_id),
        )
        revision = snapshot.revision
        await record_run_source(
            scope.binding.scope,
            scope.binding.workspace_id,
            str(run_id),
            scope.binding.catalog_version,
            SourceRef(
                artifact_id=snapshot.artifact.id,
                revision_id=revision.id,
                source_sha256=revision.sha256,
            ),
        )
        return {
            "artifact_id": snapshot.artifact.id,
            "revision_id": revision.id,
            "content_type": revision.content_type.split(";", 1)[0].strip().lower(),
            "size_bytes": len(content),
            "sha256": revision.sha256,
            "content": content,
        }

    return resolve


def configure_runtime_artifact_output_ingestor(
    *, principal, binding, run_id, node_id=None, event_recorder_provider=None,
):
    """Persist bounded external Tool outputs under the accepted Run's write grant."""
    import hashlib

    from modules.artifacts.application.runtime_scope import RunArtifactContext
    from modules.artifacts.composition.files import build_file_service

    scope = RunArtifactContext(
        principal,
        binding,
        str(run_id),
        output_node_ids=frozenset({str(node_id)}) if node_id is not None else frozenset(),
    )
    files = build_file_service()

    async def ingest(
        *, operation_id, path, content, content_type, producer_id,
        external_operation_ref=None, source_refs=(),
    ):
        request = scope.write_external_output(
            operation_id=operation_id,
            path=path,
            content=content,
            content_type=content_type,
            producer_id=producer_id,
            external_operation_ref=external_operation_ref,
            source_refs=source_refs,
        )
        view = await files.write_external_output(request)
        reference = view.receipt
        if reference is None:
            from modules.artifacts.domain.models import ArtifactError

            raise ArtifactError("EXTERNAL_OPERATION_UNCERTAIN", "External Artifact output was not committed")
        output = {
            "artifact_id": reference.artifact_id,
            "revision_id": reference.revision_id,
            "path": path,
            "content_type": content_type,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "source_refs": list(source_refs),
        }
        recorder = event_recorder_provider() if event_recorder_provider else None
        if recorder is not None:
            await recorder.emit(
                "artifact.available",
                {
                    **output,
                    "run_id": str(run_id),
                    "node_id": str(node_id) if node_id is not None else None,
                    "producer_id": producer_id,
                    "status": "available",
                },
                durable=True,
            )
        return output

    return ingest


def configure_runtime_artifact_image_generator(
    *, provider, model, model_spec, credential, destination, run_id,
    output_ingestor, event_recorder_provider=None, provider_transport=None,
):
    """Bind one declared image.generate operation to exact Run output receipts."""
    import posixpath
    import asyncio
    from uuid import UUID, uuid5

    from modules.agent.domain.model_spec import ModelOperations, ModelSpec
    from modules.agent.infra.models.image_generation import (
        GeneratedImage,
        ImageGenerationModelRuntime,
        image_generation_constraints,
        image_generation_request,
    )
    from modules.agent.infra.models.operation_strategies import build_model_operation_strategy_registry
    from modules.artifacts.composition.run_sources import get_run_source_manifest
    from modules.artifacts.domain.models import ArtifactError, logical_path
    from shared.contracts.artifact_reference import ArtifactReference

    spec = ModelSpec.from_dict(model_spec)
    constraints = image_generation_constraints(spec)
    if spec.provider != str(provider) or spec.model_id != model:
        raise ValueError("Image generation ModelSpec does not match the accepted Agent model")
    strategy = build_model_operation_strategy_registry().resolve(ModelOperations.IMAGE_GENERATE)
    runtime = ImageGenerationModelRuntime(
        spec=spec,
        provider=str(provider),
        model=model,
        credential=credential,
        destination=destination,
        transport=provider_transport,
    )
    attempted: set[str] = set()
    completed: dict[str, dict] = {}
    generated_images = 0
    operation_namespace = UUID("6f5bba23-7692-5c21-9f8d-bac4de306c70")

    async def emit(event_type, payload):
        recorder = event_recorder_provider() if event_recorder_provider else None
        if recorder is not None:
            await recorder.emit(event_type, payload, durable=True)

    async def emit_uncertain(operation_id, producer_id):
        task = asyncio.create_task(emit("artifact.external_operation.uncertain", {
            "operation_id": operation_id,
            "tool_id": producer_id,
            "operation": "image.generate",
            "provider": str(provider),
            "error_code": "EXTERNAL_OPERATION_UNCERTAIN",
        }))
        cancellation = None
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError as error:
                cancellation = error
        if cancellation is not None:
            raise cancellation
        task.result()

    async def generate(*, prompt, path, size, count, operation_id, producer_id):
        nonlocal generated_images
        if operation_id in completed:
            return completed[operation_id]
        if operation_id in attempted:
            raise ArtifactError(
                "EXTERNAL_OPERATION_UNCERTAIN",
                "Image generation was already dispatched and cannot be repeated safely",
            )
        path = logical_path(path)
        extension = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[constraints.output_format]
        base, actual_extension = posixpath.splitext(path)
        if actual_extension and actual_extension.lower() not in ({".jpg", ".jpeg"} if extension == ".jpg" else {extension}):
            raise ValueError("Image path extension differs from its declared media type")
        path_base = base if actual_extension else path
        request = image_generation_request(
            prompt, size=size, count=count, operation_id=operation_id,
        )
        runtime.validate_request(request)
        if generated_images + count > 4:
            raise ArtifactError(
                "ARTIFACT_LIMIT_EXCEEDED",
                "Image generation reached the per-Run output limit",
            )
        generated_images += count
        attempted.add(operation_id)
        await emit("artifact.external_operation.pending", {
            "operation_id": operation_id,
            "tool_id": producer_id,
            "operation": "image.generate",
            "provider": str(provider),
        })
        try:
            result = await strategy.invoke(runtime, request)
            images = result.outputs_for("image")
            if len(images) != count or any(not isinstance(item.value, GeneratedImage) for item in images):
                raise ValueError("Image generation returned an invalid multimodal result")
            operation_ref = result.metadata.get("provider_request_id")
            manifest = await get_run_source_manifest(
                scope.binding.scope, scope.binding.workspace_id, str(run_id),
            )
            source_refs = []
            for source in manifest.sources if manifest is not None else ():
                reference = ArtifactReference.model_validate({
                    "artifact_id": source.artifact_id,
                    "revision_id": source.revision_id,
                })
                source_refs.append(reference.model_dump(mode="json"))
            outputs = []
            for image in images:
                value = image.value
                current_path = (
                    f"{path_base}{extension}"
                    if count == 1
                    else f"{path_base}-{value.index + 1}{extension}"
                )
                receipt = await output_ingestor(
                    operation_id=str(uuid5(operation_namespace, f"{operation_id}:{value.index}")),
                    path=current_path,
                    content=value.content,
                    content_type=value.content_type,
                    producer_id=producer_id,
                    external_operation_ref=value.external_operation_ref,
                    source_refs=source_refs,
                )
                outputs.append({
                    "ref": {
                        "artifact_id": receipt["artifact_id"],
                        "revision_id": receipt["revision_id"],
                    },
                    **receipt,
                    "run_id": str(run_id),
                })
            usage = None
            if result.usage is not None:
                cost_usd = result.usage.cost_usd
                usage = {
                    **dict(result.usage.metrics),
                    "cost_usd": cost_usd,
                    "cost_status": (
                        "reported" if cost_usd is not None else "unknown"
                    ),
                }
            await emit("artifact.external_operation.completed", {
                "operation_id": operation_id,
                "tool_id": producer_id,
                "operation": "image.generate",
                "provider": str(provider),
                "external_operation_ref": operation_ref,
                "output_refs": [item["ref"] for item in outputs],
                "usage": usage,
            })
            response = {"success": True, "output": {"output_artifacts": outputs, "usage": usage}}
            completed[operation_id] = response
            return response
        except asyncio.CancelledError:
            try:
                await emit_uncertain(operation_id, producer_id)
            except Exception:
                pass
            raise
        except ArtifactError:
            try:
                await emit_uncertain(operation_id, producer_id)
            except Exception:
                pass
            raise
        except Exception as error:
            try:
                await emit_uncertain(operation_id, producer_id)
            except Exception:
                pass
            raise ArtifactError(
                "EXTERNAL_OPERATION_UNCERTAIN",
                "Image generation outcome is uncertain; the operation was not retried",
            ) from error

    # A local import avoids retaining the raw Run binding in serialized state.
    from modules.artifacts.application.runtime_scope import RunArtifactContext

    context = __import__("modules.agent.application.interfaces.execution_context", fromlist=["current_execution"]).current_execution.get()
    binding = getattr(context, "artifact_workspace_binding", None) if context else None
    if binding is None:
        raise ArtifactError("ARTIFACT_ACCESS_DENIED", "Image output has no accepted Workspace")
    scope = RunArtifactContext(
        getattr(context, "runtime_principal", None),
        binding,
        str(run_id),
    )
    if not callable(output_ingestor):
        raise ArtifactError("ARTIFACT_ACCESS_DENIED", "Image output publication is not authorized")
    return generate
