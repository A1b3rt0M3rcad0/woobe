import base64
import hashlib
from io import BytesIO
from types import SimpleNamespace

import httpx
from PIL import Image
import pytest

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.model_spec import (
    ModelCapability,
    ModelCapabilityNames,
    ModelInteractionSpec,
    ModelModalities,
    ModelOperations,
    ModelSpec,
    ModelTypes,
)
from modules.artifacts.domain.models import Action, Environment, RuntimeArtifactBinding, Scope
from modules.artifacts.domain.models import ArtifactError
from shared.composition.artifact_agent_tools import build_runtime_artifact_tools
from shared.composition.artifact_runtime import configure_runtime_artifact_image_generator


_png = BytesIO()
Image.new("RGB", (2, 2), color=(100, 80, 20)).save(_png, format="PNG")
PNG = _png.getvalue()


def _spec():
    return ModelSpec(
        provider="openai_compatible",
        model_id="image-model-v1",
        display_name="Fixture image model",
        model_type=ModelTypes.IMAGE,
        operations=frozenset({ModelOperations.IMAGE_GENERATE}),
        input_modalities=frozenset({ModelModalities.TEXT}),
        output_modalities=frozenset({ModelModalities.IMAGE}),
        interaction=ModelInteractionSpec(mode="isolated"),
        capabilities={ModelCapabilityNames.IMAGE_GENERATION: ModelCapability(
            supported=True,
            config={
                "sizes": ["512x512"], "default_size": "512x512", "max_images": 3,
                "max_output_bytes": 1024, "output_format": "png",
                "idempotency_key_supported": True,
            },
        )},
    )


class Recorder:
    def __init__(self):
        self.events = []

    async def emit(self, event_type, payload, *, durable):
        self.events.append((event_type, payload, durable))


@pytest.fixture
def run_context():
    context = new_execution_context()
    context.runtime_principal = object()
    context.artifact_workspace_binding = RuntimeArtifactBinding(
        workspace_id="workspace_1",
        scope=Scope("project_1", Environment.DRAFT),
        catalog_version=4,
        actions=frozenset({Action.WRITE}),
        binding_scope="run",
    )
    context.run_event_recorder = Recorder()
    token = current_execution.set(context)
    try:
        yield context
    finally:
        current_execution.reset(token)


async def test_image_tool_output_is_persisted_with_exact_run_and_source_provenance(
    monkeypatch, run_context,
):
    import modules.artifacts.composition.run_sources as run_sources

    source = SimpleNamespace(artifact_id="source_artifact", revision_id="source_revision")
    monkeypatch.setattr(
        run_sources,
        "get_run_source_manifest",
        lambda *_: _async_value(SimpleNamespace(sources=(source,))),
    )
    requests = []
    writes = []

    def provider(request):
        requests.append(request)
        assert request.headers["idempotency-key"] == "operation_1"
        return httpx.Response(
            200,
            headers={"x-request-id": "provider-request-1"},
            json={"data": [{"b64_json": base64.b64encode(PNG).decode()}] * 2,
                  "usage": {"images_generated": 2, "cost_usd": 0.04}},
            request=request,
        )

    async def output_ingestor(**kwargs):
        writes.append(kwargs)
        digest = hashlib.sha256(kwargs["content"]).hexdigest()
        output = {
            "artifact_id": f"artifact_{len(writes)}",
            "revision_id": f"revision_{len(writes)}",
            "path": kwargs["path"],
            "content_type": kwargs["content_type"],
            "size_bytes": len(kwargs["content"]),
            "sha256": digest,
            "source_refs": list(kwargs["source_refs"]),
        }
        await run_context.run_event_recorder.emit(
            "artifact.available", output, durable=True,
        )
        return output

    spec = _spec()
    invoker = configure_runtime_artifact_image_generator(
        provider=spec.provider,
        model=spec.model_id,
        model_spec=spec.as_dict(),
        credential="scoped-test-key",
        destination="https://images.example/v1",
        run_id="run_1",
        output_ingestor=output_ingestor,
        event_recorder_provider=lambda: run_context.run_event_recorder,
        provider_transport=httpx.MockTransport(provider),
    )

    result = await invoker(
        prompt="A fictional, peaceful mountain observatory",
        path="generated/observatory",
        size="512x512",
        count=2,
        operation_id="operation_1",
        producer_id="tool_image",
    )
    repeated = await invoker(
        prompt="A fictional, peaceful mountain observatory",
        path="generated/observatory",
        size="512x512",
        count=2,
        operation_id="operation_1",
        producer_id="tool_image",
    )
    with pytest.raises(ArtifactError, match="per-Run output limit") as limit_error:
        await invoker(
            prompt="A second image set in the same Run",
            path="generated/second-set",
            size="512x512",
            count=3,
            operation_id="operation_2",
            producer_id="tool_image",
        )

    outputs = result["output"]["output_artifacts"]
    assert repeated == result
    assert limit_error.value.code == "ARTIFACT_LIMIT_EXCEEDED"
    assert len(requests) == 1 and len(writes) == 2
    assert [write["path"] for write in writes] == [
        "generated/observatory-1.png", "generated/observatory-2.png",
    ]
    assert all(write["external_operation_ref"] == "provider-request-1" for write in writes)
    assert all(write["producer_id"] == "tool_image" for write in writes)
    assert all(write["source_refs"] == [{
        "artifact_id": "source_artifact", "revision_id": "source_revision",
    }] for write in writes)
    assert [item["ref"] for item in outputs] == [
        {"artifact_id": "artifact_1", "revision_id": "revision_1"},
        {"artifact_id": "artifact_2", "revision_id": "revision_2"},
    ]
    assert all(item["run_id"] == "run_1" for item in outputs)
    assert result["output"]["usage"] == {
        "images_generated": 2, "cost_usd": 0.04, "cost_status": "reported",
    }
    assert [event[0] for event in run_context.run_event_recorder.events] == [
        "artifact.external_operation.pending",
        "artifact.available", "artifact.available",
        "artifact.external_operation.completed",
    ]
    assert all(event[2] is True for event in run_context.run_event_recorder.events)
    assert run_context.run_event_recorder.events[-1][1]["usage"]["cost_usd"] == 0.04


async def test_unknown_provider_result_is_marked_uncertain_and_never_retried(
    monkeypatch, run_context,
):
    import modules.artifacts.composition.run_sources as run_sources

    monkeypatch.setattr(run_sources, "get_run_source_manifest", lambda *_: _async_value(None))
    requests = []

    def provider(request):
        requests.append(request)
        raise httpx.ReadTimeout("test timeout")

    spec = _spec()
    invoker = configure_runtime_artifact_image_generator(
        provider=spec.provider,
        model=spec.model_id,
        model_spec=spec.as_dict(),
        credential="scoped-test-key",
        destination="https://images.example/v1",
        run_id="run_1",
        output_ingestor=lambda **_: _async_value(None),
        event_recorder_provider=lambda: run_context.run_event_recorder,
        provider_transport=httpx.MockTransport(provider),
    )
    arguments = {
        "prompt": "One uncertain test operation",
        "path": "generated/uncertain",
        "size": None,
        "count": 1,
        "operation_id": "operation_uncertain",
        "producer_id": "tool_image",
    }

    with pytest.raises(ArtifactError, match="outcome is uncertain"):
        await invoker(**arguments)
    with pytest.raises(ArtifactError, match="already dispatched"):
        await invoker(**arguments)

    assert len(requests) == 1
    assert [event[0] for event in run_context.run_event_recorder.events] == [
        "artifact.external_operation.pending", "artifact.external_operation.uncertain",
    ]


async def _async_value(value):
    return value


def test_image_generation_tool_is_exposed_only_with_write_and_explicit_capability():
    binding = RuntimeArtifactBinding(
        workspace_id="workspace_1",
        scope=Scope("project_1", Environment.DRAFT),
        catalog_version=1,
        actions=frozenset({Action.WRITE}),
        binding_scope="run",
    )
    definitions, names, _handlers = build_runtime_artifact_tools(
        principal=object(),
        binding=binding,
        run_id="run_1",
        image_generation_spec=_spec().as_dict(),
    )
    assert "woobe_artifact_generate_image" in names
    definition = next(
        item["function"] for item in definitions
        if item["function"]["name"] == "woobe_artifact_generate_image"
    )
    assert definition["parameters"]["properties"]["count"]["maximum"] == 3
    assert definition["parameters"]["properties"]["size"]["anyOf"][0]["const"] == "512x512"

    read_only = RuntimeArtifactBinding(
        workspace_id="workspace_1",
        scope=Scope("project_1", Environment.DRAFT),
        catalog_version=1,
        actions=frozenset({Action.READ}),
        binding_scope="run",
    )
    _definitions, read_names, _read_handlers = build_runtime_artifact_tools(
        principal=object(),
        binding=read_only,
        run_id="run_1",
        image_generation_spec=_spec().as_dict(),
    )
    assert "woobe_artifact_generate_image" not in read_names
