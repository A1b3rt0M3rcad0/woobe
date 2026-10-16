"""Persisted aliases are interpreted, never rewritten in historical snapshots."""

from shared.contracts.errors import ValidationError

PROVIDER_ALIASES = {"custom": "openai_compatible"}


def canonical_provider_key(value: object, *, aliases=None) -> str:
    key = str(getattr(value, "value", value)).strip().lower()
    return (PROVIDER_ALIASES if aliases is None else aliases).get(key, key)


def providers_equivalent(left: object, right: object) -> bool:
    return canonical_provider_key(left) == canonical_provider_key(right)


def validate_provider_base_url(value: object) -> str:
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(value) if isinstance(value, str) else None
        valid = (
            parsed is not None
            and parsed.scheme in {"http", "https"}
            and parsed.hostname
        )
        if parsed is not None:
            parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Provider base_url must be an absolute HTTP(S) URL")
    return str(value)


def validate_model_spec_binding(spec, credential, model_id, declared_model_type=None):
    declared = declared_model_type.strip().lower() if declared_model_type else None
    declared = {
        "generation": "language",
        "llm": "language",
        "chat": "language",
        "chat_completion": "language",
        "embeddings": "embedding",
    }.get(declared, declared)
    if (
        not providers_equivalent(spec.provider, credential.provider)
        or spec.model_id != model_id
        or (declared is not None and spec.model_type != declared)
    ):
        raise ValidationError("ModelSpec identity differs from the destination Model")
