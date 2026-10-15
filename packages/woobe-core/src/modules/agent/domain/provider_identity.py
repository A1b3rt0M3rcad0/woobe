"""Persisted aliases are interpreted, never rewritten in historical snapshots."""

PROVIDER_ALIASES = {"custom": "openai_compatible"}


def canonical_provider_key(value: object) -> str:
    key = str(getattr(value, "value", value)).strip().lower()
    return PROVIDER_ALIASES.get(key, key)


def providers_equivalent(left: object, right: object) -> bool:
    return canonical_provider_key(left) == canonical_provider_key(right)
