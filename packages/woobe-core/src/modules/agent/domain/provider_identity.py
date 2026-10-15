"""Persisted aliases are interpreted, never rewritten in historical snapshots."""

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
