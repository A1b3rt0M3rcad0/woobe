from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from modules.agent.domain.model_spec import (
    ModelInteractionSpec,
    ModelModalities,
    ModelOperations,
    ModelSpec,
    ModelTypes,
)
from modules.agent.infra.execution.visual_artifact_inputs import (
    attach_visual_inputs,
    materialize_visual_inputs,
    safe_message_preview,
    visual_input_preflight,
)
from modules.artifacts.application.services.files import FileService
from modules.artifacts.domain.models import ArtifactError
from shared.infra.object_storage.local import LocalObjectStorage
from shared.contracts.errors import ValidationError


IMAGE = b"\x89PNG\r\n\x1a\nsmall deterministic image fixture"


def spec(*, modalities=("text", "image")):
    return ModelSpec(
        provider="fake-provider",
        model_id="a-model-with-no-vision-name-hint",
        display_name="Contract peer",
        model_type=ModelTypes.LANGUAGE,
        operations=frozenset({ModelOperations.LANGUAGE_GENERATE}),
        input_modalities=frozenset(modalities),
        output_modalities=frozenset({ModelModalities.TEXT}),
        interaction=ModelInteractionSpec(mode="conversation", supports_conversation=True),
        source="provider_model",
    ).as_dict()


def image_reference(content=IMAGE):
    return {
        "artifact_id": "artifact-1",
        "revision_id": "revision-1",
        "content_type": "image/png",
        "size_bytes": len(content),
        "source_sha256": hashlib.sha256(content).hexdigest(),
    }


class FakeFactory:
    def __init__(self, *, supports=True):
        self.supports = supports
        self.formatted = []

    def supports_vision_input(self, provider):
        return self.supports and provider == "fake-provider"

    def format_vision_input(self, provider, *, content_type, content):
        value = {"type": "peer_image", "content_type": content_type, "content": content}
        self.formatted.append((provider, value))
        return value


def agent_with_spec(model_spec, *, fallback=None):
    return SimpleNamespace(
        provider="fake-provider",
        model="model-id",
        fallback_provider="fake-provider" if fallback else None,
        fallback_model="fallback-id" if fallback else None,
        settings={"model_spec": model_spec, **({"fallback_model_spec": fallback} if fallback else {})},
    )


def test_effective_model_spec_and_provider_adapter_gate_before_reading_bytes():
    factory = FakeFactory()
    image = image_reference()
    agent = agent_with_spec(spec(modalities=("text",)))
    with pytest.raises(ValidationError, match="does not accept image input"):
        visual_input_preflight(agent, factory, (image,))
    assert factory.formatted == []

    agent = agent_with_spec(spec())
    with pytest.raises(ValidationError, match="cannot format image input"):
        visual_input_preflight(agent, FakeFactory(supports=False), (image,))


@pytest.mark.parametrize("count,total", [(5, 5), (3, 9 * 1024 * 1024)])
def test_visual_reference_count_and_cumulative_bytes_are_bounded(count, total):
    chunk = total // count
    data = b"\x89PNG\r\n\x1a\n" + b"x" * (chunk - 8)
    references = tuple(image_reference(data) for _ in range(count))
    with pytest.raises(ValidationError, match="at most four|combined Run byte limit"):
        visual_input_preflight(agent_with_spec(spec()), FakeFactory(), references)


def test_effective_model_input_byte_limit_is_applied_before_storage_read():
    per_image = 3 * 1024 * 1024
    data = b"\x89PNG\r\n\x1a\n" + b"x" * (per_image - 8)
    model_spec = spec()
    model_spec["limits"]["max_input_bytes"] = 5 * 1024 * 1024
    references = (image_reference(data), image_reference(data))
    with pytest.raises(ValidationError, match="combined Run byte limit"):
        visual_input_preflight(agent_with_spec(model_spec), FakeFactory(), references)


@pytest.mark.asyncio
async def test_exact_image_bytes_are_verified_then_formatted_only_at_provider_boundary():
    reference = image_reference()
    calls = []

    async def resolve(artifact_id, revision_id):
        calls.append((artifact_id, revision_id))
        return {**reference, "content": IMAGE}

    factory = FakeFactory()
    images = visual_input_preflight(agent_with_spec(spec()), factory, (reference,))
    formatted = await materialize_visual_inputs(
        images=images, resolver=resolve, llm_factory=factory, provider="fake-provider",
    )
    messages = [HumanMessage(content="What is shown?")]
    attach_visual_inputs(messages, formatted)

    assert calls == [("artifact-1", "revision-1")]
    assert factory.formatted[0][1]["content"] == IMAGE
    assert messages[0].content[0] == {"type": "text", "text": "What is shown?"}
    assert messages[0].content[1]["content"] == IMAGE
    assert safe_message_preview(messages[0].content) == "What is shown?"
    assert IMAGE.decode("latin1") not in safe_message_preview(messages[0].content)


@pytest.mark.asyncio
async def test_resolver_result_must_match_exact_revision_checksum_mime_and_signature():
    reference = image_reference()
    factory = FakeFactory()
    images = visual_input_preflight(agent_with_spec(spec()), factory, (reference,))

    async def bad_resolver(_artifact_id, _revision_id):
        return {**reference, "content": b"not an image"}

    with pytest.raises(ValidationError, match="integrity validation"):
        await materialize_visual_inputs(
            images=images, resolver=bad_resolver, llm_factory=factory, provider="fake-provider",
        )
    assert factory.formatted == []

    changed = IMAGE[:-1] + bytes([IMAGE[-1] ^ 1])

    async def checksum_mismatch(_artifact_id, _revision_id):
        return {**reference, "content": changed}

    with pytest.raises(ValidationError, match="integrity validation"):
        await materialize_visual_inputs(
            images=images, resolver=checksum_mismatch, llm_factory=factory, provider="fake-provider",
        )
    assert factory.formatted == []


def test_fallback_model_must_also_accept_vision_input():
    agent = agent_with_spec(spec(), fallback=spec(modalities=("text",)))
    with pytest.raises(ValidationError, match="does not accept image input"):
        visual_input_preflight(agent, FakeFactory(), (image_reference(),))


def test_builtin_provider_adapters_format_only_declared_image_payloads():
    from modules.agent.infra.llm.providers import build_legacy_chat_provider_registry

    registry = build_legacy_chat_provider_registry()
    openai_block = registry.format_vision_input("openai", content_type="image/png", content=IMAGE)
    anthropic_block = registry.format_vision_input("anthropic", content_type="image/png", content=IMAGE)
    assert openai_block["type"] == "image_url"
    assert openai_block["image_url"]["url"].startswith("data:image/png;base64,")
    assert anthropic_block["type"] == "image"
    assert anthropic_block["source"]["media_type"] == "image/png"
    assert registry.supports_vision_input("openai") is True
    assert registry.supports_vision_input("unknown-provider") is False


@pytest.mark.asyncio
async def test_artifact_visual_read_verifies_exact_image_revision_and_storage_bytes(tmp_path):
    storage = LocalObjectStorage(tmp_path / "objects")
    key = "projects/project/environments/development/artifact-workspaces/workspace/artifacts/artifact/revisions/revision/original"

    async def chunks():
        yield IMAGE

    await storage.put(
        key, chunks(), size_bytes=len(IMAGE), sha256=hashlib.sha256(IMAGE).hexdigest(),
        content_type="image/png",
    )
    revision = SimpleNamespace(
        content_type="image/png", size_bytes=len(IMAGE),
        sha256=hashlib.sha256(IMAGE).hexdigest(), object_key=key,
    )
    snapshot = SimpleNamespace(revision=revision, storage_profile="local")

    async def resolve(_request):
        return snapshot

    files = FileService(resolve, None, None, None, lambda _profile: storage)
    observed, content = await files.read_visual_bytes(object())
    assert observed is snapshot
    assert content == IMAGE


@pytest.mark.asyncio
async def test_artifact_visual_read_rejects_mime_mismatch_and_oversized_revisions():
    async def resolve(_request):
        return SimpleNamespace(
            revision=SimpleNamespace(
                content_type="text/plain", size_bytes=1, sha256="0" * 64, object_key="unused",
            ),
            storage_profile="unused",
        )

    files = FileService(resolve, None, None, None, lambda _profile: None)
    with pytest.raises(ArtifactError, match="not supported as visual input"):
        await files.read_visual_bytes(object())

    async def oversized(_request):
        return SimpleNamespace(
            revision=SimpleNamespace(
                content_type="image/png", size_bytes=4 * 1024 * 1024 + 1,
                sha256="0" * 64, object_key="unused",
            ),
            storage_profile="unused",
        )

    files.resolve = oversized
    with pytest.raises(ArtifactError, match="byte limit"):
        await files.read_visual_bytes(object())
