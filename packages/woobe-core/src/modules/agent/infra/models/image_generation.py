"""Bounded one-shot image generation over an OpenAI-compatible endpoint."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from io import BytesIO
import json
import math
import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from modules.agent.application.interfaces.model_runtime import (
    ModelInput,
    ModelOutput,
    ModelRequest,
    ModelResult,
    ModelRuntime,
    ModelUsage,
)
from modules.agent.domain.model_spec import (
    ModelCapabilityNames,
    ModelModalities,
    ModelOperations,
    ModelSpec,
)
from modules.agent.infra.adapters.configuration_transport import (
    BoundConfigurationCredential,
    ConfigurationTransport,
)


_DEFAULT_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_MAX_IMAGES = 4
_MAX_PROMPT_BYTES = 8192
_MAX_RESPONSE_OVERHEAD = 64 * 1024
_SAFE_SIZE = re.compile(r"^[1-9][0-9]{1,3}x[1-9][0-9]{1,3}$")
_FORMATS = {"png", "jpeg", "webp"}


@dataclass(frozen=True, slots=True)
class ImageGenerationConstraints:
    sizes: tuple[str, ...]
    default_size: str
    max_images: int
    max_output_bytes: int
    output_format: str
    output_format_parameter_supported: bool
    idempotency_key_supported: bool


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    content: bytes
    content_type: str
    index: int
    external_operation_ref: str | None = None


def image_generation_constraints(spec: ModelSpec) -> ImageGenerationConstraints:
    capability = spec.capability(ModelCapabilityNames.IMAGE_GENERATION)
    if (
        capability is None
        or not capability.supported
        or not spec.supports_operation(ModelOperations.IMAGE_GENERATE)
        or not spec.accepts(ModelModalities.TEXT)
        or not spec.produces(ModelModalities.IMAGE)
    ):
        raise ValueError("ModelSpec does not declare image.generate with text input and image output")

    config = capability.config
    raw_sizes = config.get("sizes", ("1024x1024",))
    if not isinstance(raw_sizes, (list, tuple)) or not raw_sizes:
        raise ValueError("Image generation capability must declare supported sizes")
    sizes = tuple(dict.fromkeys(str(size) for size in raw_sizes))
    if any(not _SAFE_SIZE.fullmatch(size) for size in sizes):
        raise ValueError("Image generation capability contains an invalid size")
    default_size = str(config.get("default_size") or sizes[0])
    if default_size not in sizes:
        raise ValueError("Image generation default size must be supported")

    raw_count = config.get("max_images", 1)
    if isinstance(raw_count, bool) or not isinstance(raw_count, int) or not 1 <= raw_count <= _MAX_IMAGES:
        raise ValueError("Image generation max_images must be between one and four")
    configured_bytes = config.get("max_output_bytes", spec.limits.max_output_bytes or _DEFAULT_MAX_OUTPUT_BYTES)
    if isinstance(configured_bytes, bool) or not isinstance(configured_bytes, int) or configured_bytes <= 0:
        raise ValueError("Image generation max_output_bytes must be positive")
    if spec.limits.max_output_bytes is not None:
        configured_bytes = min(configured_bytes, spec.limits.max_output_bytes)
    configured_bytes = min(configured_bytes, _DEFAULT_MAX_OUTPUT_BYTES)
    output_format = str(config.get("output_format") or "png").lower()
    if output_format not in _FORMATS:
        raise ValueError("Image generation output_format must be png, jpeg or webp")
    output_format_parameter_supported = config.get("output_format_parameter_supported") is True
    if output_format != "png" and not output_format_parameter_supported:
        raise ValueError("Non-PNG image output requires the provider output_format parameter")
    if config.get("idempotency_key_supported") is not True:
        raise ValueError("Image generation capability must guarantee provider idempotency keys")
    return ImageGenerationConstraints(
        sizes, default_size, raw_count, configured_bytes, output_format,
        output_format_parameter_supported, True,
    )


def image_generation_request(
    prompt: str,
    *,
    size: str | None = None,
    count: int = 1,
    operation_id: str | None = None,
) -> ModelRequest:
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > _MAX_PROMPT_BYTES:
        raise ValueError("Image generation prompt must be non-empty and at most 8192 UTF-8 bytes")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= _MAX_IMAGES:
        raise ValueError("Image generation count must be between one and four")
    if operation_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", operation_id):
        raise ValueError("Image generation operation id is invalid")
    return ModelRequest(
        operation=ModelOperations.IMAGE_GENERATE,
        inputs=(ModelInput(ModelModalities.TEXT, prompt),),
        parameters={"size": size, "count": count},
        context={"idempotency_key": operation_id} if operation_id else None,
    )


def _endpoint(provider: str, destination: str | None) -> str:
    if provider not in {"openai", "openai_compatible", "custom"}:
        raise ValueError("This image generation adapter requires an OpenAI-compatible provider")
    base = destination or ("https://api.openai.com/v1" if provider == "openai" else None)
    if not base:
        raise ValueError("OpenAI-compatible image generation requires a configured endpoint")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Image generation endpoint must be an HTTPS URL without embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("Image generation endpoint cannot include a query or fragment")
    return f"{base.rstrip('/')}/images/generations"


def _decode_image(raw: Any, *, output_format: str, max_output_bytes: int, index: int) -> GeneratedImage:
    if not isinstance(raw, str) or not raw or len(raw) > ((max_output_bytes + 2) // 3) * 4:
        raise ValueError("Provider returned an invalid or oversized image")
    try:
        content = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Provider returned invalid base64 image data") from None
    if not content or len(content) > max_output_bytes:
        raise ValueError("Provider image exceeds the configured output limit")

    signatures = {
        "png": (b"\x89PNG\r\n\x1a\n", "image/png"),
        "jpeg": (b"\xff\xd8\xff", "image/jpeg"),
        "webp": (b"RIFF", "image/webp"),
    }
    signature, content_type = signatures[output_format]
    valid = content.startswith(signature)
    if output_format == "webp":
        valid = len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    if not valid:
        raise ValueError("Provider image bytes do not match the declared output format")
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            if image.format != output_format.upper() and not (
                output_format == "jpeg" and image.format == "JPEG"
            ):
                raise ValueError
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > 40_000_000:
                raise ValueError
            image.verify()
    except Exception:
        raise ValueError("Provider image is invalid or exceeds the image dimension limit") from None
    return GeneratedImage(content, content_type, index)


class OpenAICompatibleImageGenerationAdapter:
    """Single request, no redirects/retries, no URL dereference, bounded response."""

    def __init__(self, *, provider: str, credential: Any, destination: str | None,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._url = _endpoint(provider, destination)
        self._credential = credential
        self._transport = transport

    async def generate(self, *, model: str, prompt: str, size: str,
                       count: int, output_format: str,
                       output_format_parameter_supported: bool,
                       max_output_bytes: int,
                       idempotency_key: str | None) -> tuple[tuple[GeneratedImage, ...], str | None, ModelUsage | None]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if isinstance(self._credential, BoundConfigurationCredential):
            transport = ConfigurationTransport(self._credential, transport=self._transport)
        else:
            if not isinstance(self._credential, str) or not self._credential:
                raise ValueError("Image generation credential is unavailable")
            headers["Authorization"] = f"Bearer {self._credential}"
            transport = self._transport or httpx.AsyncHTTPTransport()

        body = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": count,
            "response_format": "b64_json",
        }
        if output_format_parameter_supported:
            body["output_format"] = output_format
        max_response = min(((max_output_bytes + 2) // 3) * 4 + _MAX_RESPONSE_OVERHEAD,
                           40 * 1024 * 1024)
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(60.0, connect=10.0),
        ) as client:
            async with client.stream("POST", self._url, headers=headers, json=body) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise ValueError("Image generation provider request failed")
                payload_bytes = bytearray()
                async for chunk in response.aiter_bytes():
                    payload_bytes.extend(chunk)
                    if len(payload_bytes) > max_response:
                        raise ValueError("Image generation provider response exceeds the configured limit")
                try:
                    payload = json.loads(payload_bytes)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise ValueError("Image generation provider returned invalid JSON") from None
                if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                    raise ValueError("Image generation provider returned an unsupported response")
                items = payload["data"]
                if len(items) != count or any(not isinstance(item, dict) for item in items):
                    raise ValueError("Image generation provider returned an incomplete result")
                images = tuple(
                    _decode_image(item.get("b64_json"), output_format=output_format,
                                  max_output_bytes=max_output_bytes, index=index)
                    for index, item in enumerate(items)
                )
                request_id = response.headers.get("x-request-id")
                if not request_id and isinstance(payload.get("id"), str):
                    request_id = payload["id"]
                if (not isinstance(request_id, str)
                    or not 1 <= len(request_id) <= 256
                    or not re.fullmatch(r"[A-Za-z0-9_.:-]+", request_id)):
                    request_id = None
                usage = _model_usage(payload.get("usage"))
                return images, request_id, usage


def _model_usage(raw: Any) -> ModelUsage | None:
    if not isinstance(raw, dict):
        return None
    metrics = {}
    for key, value in raw.items():
        name = str(key)
        if (len(name) <= 64 and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", name)
            and isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0):
            metrics[name] = value
    raw_cost = raw.get("cost_usd")
    cost = (float(raw_cost) if isinstance(raw_cost, (int, float))
            and not isinstance(raw_cost, bool) and math.isfinite(raw_cost) and raw_cost >= 0
            else None)
    metrics.pop("cost_usd", None)
    return ModelUsage(metrics=metrics, cost_usd=cost) if metrics or cost is not None else None


class ImageGenerationModelRuntime(ModelRuntime):
    def __init__(self, *, spec: ModelSpec, provider: str, model: str,
                 credential: Any, destination: str | None,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._spec = spec
        self._constraints = image_generation_constraints(spec)
        if spec.provider != provider or spec.model_id != model:
            raise ValueError("Image generation provider/model must match the declared ModelSpec")
        self._adapter = OpenAICompatibleImageGenerationAdapter(
            provider=provider, credential=credential, destination=destination,
            transport=transport,
        )

    @property
    def spec(self) -> ModelSpec:
        return self._spec

    def validate_request(self, request: ModelRequest) -> tuple[str, str, int]:
        if request.operation != ModelOperations.IMAGE_GENERATE or request.tools:
            raise ValueError("Image generation runtime accepts only one-shot image.generate requests")
        if len(request.inputs) != 1 or request.inputs[0].modality != ModelModalities.TEXT:
            raise ValueError("Image generation requires exactly one text prompt")
        prompt = request.inputs[0].value
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > _MAX_PROMPT_BYTES:
            raise ValueError("Image generation prompt exceeds its bound")
        size = request.parameters.get("size") or self._constraints.default_size
        count = request.parameters.get("count", 1)
        if size not in self._constraints.sizes:
            raise ValueError("Requested image size is not declared by ModelSpec")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= self._constraints.max_images:
            raise ValueError("Requested image count exceeds ModelSpec capability")
        return prompt, size, count

    async def invoke(self, request: ModelRequest) -> ModelResult:
        prompt, size, count = self.validate_request(request)
        images, request_id, usage = await self._adapter.generate(
            model=self._spec.model_id,
            prompt=prompt,
            size=size,
            count=count,
            output_format=self._constraints.output_format,
            output_format_parameter_supported=(
                self._constraints.output_format_parameter_supported
            ),
            max_output_bytes=self._constraints.max_output_bytes,
            idempotency_key=(str(request.context["idempotency_key"])
                             if request.context and request.context.get("idempotency_key") else None),
        )
        if sum(len(image.content) for image in images) > self._constraints.max_output_bytes:
            raise ValueError("Image generation result exceeds the total ModelSpec output byte limit")
        outputs = tuple(
            ModelOutput(
                modality=ModelModalities.IMAGE,
                value=GeneratedImage(
                    content=image.content,
                    content_type=image.content_type,
                    index=image.index,
                    external_operation_ref=request_id,
                ),
            )
            for image in images
        )
        return ModelResult(
            outputs=outputs,
            finish_reason="completed",
            usage=usage,
            metadata={"provider_request_id": request_id} if request_id else {},
        )


__all__ = [
    "GeneratedImage",
    "ImageGenerationConstraints",
    "ImageGenerationModelRuntime",
    "OpenAICompatibleImageGenerationAdapter",
    "image_generation_constraints",
    "image_generation_request",
]
