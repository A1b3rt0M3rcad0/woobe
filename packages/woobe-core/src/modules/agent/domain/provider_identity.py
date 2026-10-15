"""Persisted aliases are interpreted, never rewritten in historical snapshots."""

PROVIDER_ALIASES = {"custom": "openai_compatible"}


def canonical_provider_key(value: object, *, aliases=None) -> str:
    key = str(getattr(value, "value", value)).strip().lower()
    return (PROVIDER_ALIASES if aliases is None else aliases).get(key, key)


def providers_equivalent(left: object, right: object) -> bool:
    return canonical_provider_key(left) == canonical_provider_key(right)
