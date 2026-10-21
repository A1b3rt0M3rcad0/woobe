import base64
from io import BytesIO
import json

import httpx
from PIL import Image
import pytest

from modules.agent.application.interfaces.model_runtime import ModelOutput
from modules.agent.domain.model_spec import (
    ModelCapability,
    ModelCapabilityNames,
    ModelInteractionSpec,
    ModelModalities,
    ModelOperations,
    ModelSpec,
    ModelTypes,
)
from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential
from modules.agent.infra.models.image_generation import (
    GeneratedImage,
    ImageGenerationModelRuntime,
    image_generation_constraints,
    image_generation_request,
)
from modules.agent.infra.models.operation_strategies import ImageGenerationModelStrategy


_png = BytesIO()
Image.new("RGB", (2, 2), color=(30, 80, 140)).save(_png, format="PNG")
PNG = _png.getvalue()


def image_spec(*, provider="openai_compatible", config=None, output_limit=1024):
    return ModelSpec(
        provider=provider,
        model_id="image-model-v1",
        display_name="Fixture image model",
        model_type=ModelTypes.IMAGE,
        operations=frozenset({ModelOperations.IMAGE_GENERATE}),
        input_modalities=frozenset({ModelModalities.TEXT}),
        output_modalities=frozenset({ModelModalities.IMAGE}),
        interaction=ModelInteractionSpec(mode="isolated"),
        capabilities={ModelCapabilityNames.IMAGE_GENERATION: ModelCapability(
            supported=True,
            config=config or {
                "sizes": ["512x512", "1024x1024"],
                "default_size": "512x512",
                "max_images": 3,
                "max_output_bytes": output_limit,
                "output_format": "png",
                "output_format_parameter_supported": True,
                "idempotency_key_supported": True,
            },
            source="test-provider-contract",
        )},
    )


def mock_transport(handler):
    return httpx.MockTransport(handler)


async def test_image_generation_uses_one_scoped_bounded_request_and_returns_typed_images():
    seen = []

    async def resolve(destination):
        assert destination == "https://images.example/v1/images/generations"
        return "tenant-secret-fixture"

    def handler(request):
        seen.append(request)
        assert request.method == "POST"
        assert request.url == "https://images.example/v1/images/generations"
        assert request.headers["authorization"] == "Bearer tenant-secret-fixture"
        assert request.headers["idempotency-key"] == "operation_17"
        body = json.loads(request.content)
        assert body == {
            "model": "image-model-v1",
            "prompt": "A quiet coastal town at dawn",
            "size": "1024x1024",
            "n": 2,
            "response_format": "b64_json",
            "output_format": "png",
        }
        return httpx.Response(
            200,
            headers={"x-request-id": "req-fixture-17"},
            json={
                "data": [{"b64_json": base64.b64encode(PNG).decode()}] * 2,
                "usage": {"output_tokens": 37, "cost_usd": 0.02},
            },
            request=request,
        )

    spec = image_spec()
    runtime = ImageGenerationModelRuntime(
        spec=spec,
        provider="openai_compatible",
        model=spec.model_id,
        credential=BoundConfigurationCredential(resolve),
        destination="https://images.example/v1",
        transport=mock_transport(handler),
    )
    strategy = ImageGenerationModelStrategy()
    assert strategy.supports(spec)
    result = await strategy.invoke(
        runtime,
        image_generation_request(
            "A quiet coastal town at dawn", size="1024x1024", count=2,
            operation_id="operation_17",
        ),
    )

    images = result.outputs_for(ModelModalities.IMAGE)
    assert result.has_output(ModelModalities.IMAGE)
    assert not result.has_output(ModelModalities.TEXT)
    assert len(seen) == 1
    assert len(images) == 2
    assert all(isinstance(output, ModelOutput) for output in images)
    assert all(isinstance(output.value, GeneratedImage) for output in images)
    assert [output.value.index for output in images] == [0, 1]
    assert all(output.value.content == PNG and output.value.content_type == "image/png" for output in images)
    assert result.metadata["provider_request_id"] == "req-fixture-17"
    assert result.usage.metrics == {"output_tokens": 37}
    assert result.usage.cost_usd == 0.02


@pytest.mark.parametrize(
    ("payload", "count", "message"),
    [
        ({"data": [{"b64_json": base64.b64encode(PNG).decode()}]}, 2, "incomplete"),
        ({"data": [{"b64_json": "not-base64!"}]}, 1, "invalid base64"),
        ({"data": [{"b64_json": base64.b64encode(b"GIF89a-data").decode()}]}, 1, "do not match"),
        ({"data": [{"b64_json": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()}]}, 1, "invalid or exceeds"),
        ({"data": [{"url": "https://untrusted.example/image.png"}]}, 1, "invalid or oversized"),
    ],
)
async def test_incomplete_invalid_or_url_only_image_responses_are_rejected(payload, count, message):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload, request=request)

    spec = image_spec(config={
        "sizes": ["512x512"], "default_size": "512x512", "max_images": 2,
        "max_output_bytes": 64, "output_format": "png",
        "output_format_parameter_supported": True,
        "idempotency_key_supported": True,
    })
    runtime = ImageGenerationModelRuntime(
        spec=spec,
        provider="openai_compatible",
        model=spec.model_id,
        credential="local-test-only",
        destination="https://images.example/v1",
        transport=mock_transport(handler),
    )
    with pytest.raises(ValueError, match=message):
        await runtime.invoke(image_generation_request("make a test image", count=count))
    assert len(requests) == 1


async def test_redirects_are_not_followed_and_the_endpoint_is_never_resolved_from_response_url():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://attacker.example/image"}, request=request)

    spec = image_spec()
    runtime = ImageGenerationModelRuntime(
        spec=spec, provider="openai_compatible", model=spec.model_id,
        credential="local-test-only", destination="https://images.example/v1",
        transport=mock_transport(handler),
    )
    with pytest.raises(ValueError, match="request failed"):
        await runtime.invoke(image_generation_request("make a test image"))
    assert len(requests) == 1
    assert requests[0].url.host == "images.example"


async def test_provider_response_is_bounded_by_the_total_model_output_byte_limit():
    oversized = PNG
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={
            "data": [{"b64_json": base64.b64encode(oversized).decode()}] * 2,
        }, request=request)

    spec = image_spec(config={
        "sizes": ["512x512"], "default_size": "512x512", "max_images": 2,
        "max_output_bytes": 128, "output_format": "png",
        "output_format_parameter_supported": True,
        "idempotency_key_supported": True,
    })
    runtime = ImageGenerationModelRuntime(
        spec=spec, provider="openai_compatible", model=spec.model_id,
        credential="local-test-only", destination="https://images.example/v1",
        transport=mock_transport(handler),
    )
    with pytest.raises(ValueError, match="total ModelSpec output byte limit"):
        await runtime.invoke(image_generation_request("make two test images", count=2))
    assert len(requests) == 1


@pytest.mark.parametrize("changes", [
    {"provider": "anthropic"},
    {"output_limit": 4},
])
def test_generation_constraints_reject_undeclared_operation_provider_or_limits(changes):
    if changes.get("provider"):
        spec = image_spec(provider=changes["provider"])
        with pytest.raises(ValueError, match="OpenAI-compatible"):
            ImageGenerationModelRuntime(
                spec=spec, provider="anthropic", model=spec.model_id,
                credential="fixture", destination="https://images.example/v1",
            )
    else:
        spec = image_spec(output_limit=changes["output_limit"])
        constraints = image_generation_constraints(spec)
        assert constraints.max_output_bytes == 4


def test_generation_requires_declared_provider_idempotency_for_recovery_safety():
    spec = image_spec(config={
        "sizes": ["512x512"], "default_size": "512x512", "max_images": 1,
        "max_output_bytes": 128, "output_format": "png",
    })
    with pytest.raises(ValueError, match="guarantee provider idempotency keys"):
        image_generation_constraints(spec)


async def test_generation_preflight_enforces_supported_size_count_and_prompt_bound():
    spec = image_spec(config={
        "sizes": ["512x512"], "default_size": "512x512", "max_images": 1,
        "max_output_bytes": 128, "output_format": "png",
        "output_format_parameter_supported": True,
        "idempotency_key_supported": True,
    })
    runtime = ImageGenerationModelRuntime(
        spec=spec, provider="openai_compatible", model=spec.model_id,
        credential="fixture", destination="https://images.example/v1",
        transport=mock_transport(lambda request: pytest.fail("invalid request must fail before provider I/O")),
    )

    async def assert_invalid(request):
        with pytest.raises(ValueError):
            await runtime.invoke(request)

    await assert_invalid(image_generation_request("prompt", size="1024x1024"))
    await assert_invalid(image_generation_request("prompt", count=2))
    with pytest.raises(ValueError, match="8192"):
        image_generation_request("x" * 8193)
