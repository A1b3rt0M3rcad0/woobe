"""Resolve exact authorized image revisions at the ephemeral provider boundary."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from modules.agent.domain.model_spec import ModelModalities, ModelOperations, ModelSpec
from shared.contracts.errors import ValidationError


MAX_VISUAL_IMAGES = 4
MAX_VISUAL_IMAGE_BYTES = 4 * 1024 * 1024
MAX_VISUAL_TOTAL_BYTES = 8 * 1024 * 1024
SUPPORTED_VISUAL_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


def _provider_key(provider) -> str:
    return str(provider.value if hasattr(provider, "value") else provider)


def _effective_model_spec(agent, *, fallback: bool = False) -> ModelSpec:
    prefix = "fallback_" if fallback else ""
    settings = agent.settings if isinstance(agent.settings, Mapping) else {}
    raw = settings.get(prefix + "model_spec")
    if isinstance(raw, Mapping):
        return ModelSpec.from_dict(raw)
    from modules.agent.application.interfaces.model_spec_compatibility import LegacyModelSpecResolver

    model = getattr(agent, prefix + "model", None)
    provider = getattr(agent, prefix + "provider", None)
    return LegacyModelSpecResolver().resolve(
        type("CompatibilityModel", (), {"model": model, "name": model, "metadata": {}})(),
        provider=_provider_key(provider),
    )


def _require_vision_model(agent, llm_factory) -> int:
    specs = [(False, getattr(agent, "provider", None))]
    if getattr(agent, "fallback_provider", None) and getattr(agent, "fallback_model", None):
        specs.append((True, getattr(agent, "fallback_provider")))
    max_input_bytes = MAX_VISUAL_TOTAL_BYTES
    for is_fallback, provider in specs:
        spec = _effective_model_spec(agent, fallback=is_fallback)
        if (
            not spec.supports_operation(ModelOperations.LANGUAGE_GENERATE)
            or not spec.accepts(ModelModalities.IMAGE)
        ):
            raise ValidationError("The configured model operation does not accept image input")
        supports = getattr(llm_factory, "supports_vision_input", None)
        if not callable(supports) or not supports(_provider_key(provider)):
            raise ValidationError("The configured provider adapter cannot format image input")
        if spec.limits.max_input_bytes is not None:
            max_input_bytes = min(max_input_bytes, spec.limits.max_input_bytes)
    return max_input_bytes


def _image_references(
    resolved_parts: tuple[dict, ...], *, max_total_bytes: int = MAX_VISUAL_TOTAL_BYTES,
) -> list[dict]:
    images = [
        part for part in resolved_parts
        if str(part.get("content_type", "")).lower().startswith("image/")
    ]
    if len(images) > MAX_VISUAL_IMAGES:
        raise ValidationError("A Run can include at most four image references")
    total = 0
    for part in images:
        content_type = str(part.get("content_type", "")).split(";", 1)[0].strip().lower()
        size_bytes = part.get("size_bytes")
        digest = part.get("source_sha256")
        if content_type not in SUPPORTED_VISUAL_TYPES:
            raise ValidationError("The referenced image media type is not supported")
        if type(size_bytes) is not int or not 1 <= size_bytes <= MAX_VISUAL_IMAGE_BYTES:
            raise ValidationError("The referenced image exceeds the configured byte limit")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValidationError("The referenced image integrity metadata is invalid")
        total += size_bytes
    if total > max_total_bytes:
        raise ValidationError("Visual input exceeds the combined Run byte limit")
    return images


def visual_input_preflight(agent, llm_factory, resolved_parts: tuple[dict, ...]) -> list[dict]:
    max_total_bytes = _require_vision_model(agent, llm_factory) if any(
        str(part.get("content_type", "")).lower().startswith("image/")
        for part in resolved_parts
    ) else MAX_VISUAL_TOTAL_BYTES
    return _image_references(resolved_parts, max_total_bytes=max_total_bytes)


def _matches_media_signature(content_type: str, content: bytes) -> bool:
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    return False


async def materialize_visual_inputs(*, images: list[dict], resolver, llm_factory, provider: str) -> list[dict]:
    if not images:
        return []
    if not callable(resolver):
        raise ValidationError("Authorized image input is unavailable for this Run")
    formatter = getattr(llm_factory, "format_vision_input", None)
    if not callable(formatter):
        raise ValidationError("The configured provider adapter cannot format image input")
    output = []
    total = 0
    for reference in images:
        try:
            resolved = await resolver(reference["artifact_id"], reference["revision_id"])
        except Exception as error:
            raise ValidationError("The exact authorized image revision is unavailable") from error
        content = resolved.get("content") if isinstance(resolved, dict) else None
        content_type = resolved.get("content_type") if isinstance(resolved, dict) else None
        if (
            not isinstance(content, bytes)
            or content_type != reference["content_type"]
            or resolved.get("artifact_id") != reference["artifact_id"]
            or resolved.get("revision_id") != reference["revision_id"]
            or len(content) != reference["size_bytes"]
            or hashlib.sha256(content).hexdigest() != reference["source_sha256"]
            or not _matches_media_signature(content_type, content)
        ):
            raise ValidationError("The exact image revision failed content integrity validation")
        total += len(content)
        if total > MAX_VISUAL_TOTAL_BYTES:
            raise ValidationError("Visual input exceeds the combined Run byte limit")
        try:
            output.append(formatter(provider, content_type=content_type, content=content))
        except Exception as error:
            raise ValidationError("The configured provider could not prepare image input") from error
    return output


def attach_visual_inputs(messages: list, formatted_images: list[dict]) -> None:
    if not formatted_images:
        return
    from langchain_core.messages import HumanMessage

    message = next((item for item in reversed(messages) if isinstance(item, HumanMessage)), None)
    if message is None or not isinstance(message.content, str):
        raise ValidationError("Visual input could not be attached to the current user message")
    message.content = [
        {"type": "text", "text": message.content},
        *formatted_images,
    ]


def safe_message_preview(content: object, *, limit: int = 100) -> str:
    """Log text only; never stringify provider image blocks or encoded image bytes."""
    if isinstance(content, str):
        return content[:limit]
    if isinstance(content, list):
        text_blocks = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        return " ".join(text_blocks)[:limit] or "[multimodal content]"
    return "[multimodal content]" if content else ""

