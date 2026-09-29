from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from modules.agent.domain.model_spec import ModelSpec


@dataclass(frozen=True, slots=True)
class ProviderManifest:
    key: str
    display_name: str
    protocols: frozenset[str] = frozenset()
    supports_discovery: bool = False
    credential_fields: tuple[str, ...] = ("api_key",)
    metadata_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("Provider key must not be empty")
        if not self.display_name.strip():
            raise ValueError("Provider display name must not be empty")
        object.__setattr__(
            self,
            "protocols",
            frozenset(
                value.strip()
                for item in self.protocols
                if (value := str(item).strip())
            ),
        )
        object.__setattr__(
            self,
            "metadata_schema",
            dict(self.metadata_schema or {}),
        )


@dataclass(frozen=True, slots=True)
class ProviderConnection:
    provider: str
    api_key: str
    base_url: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Provider connection key must not be empty")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@runtime_checkable
class ProviderAdapter(Protocol):
    @property
    def manifest(self) -> ProviderManifest: ...

    async def validate_connection(
        self,
        connection: ProviderConnection,
    ) -> None: ...

    async def discover_models(
        self,
        connection: ProviderConnection,
    ) -> tuple[ModelSpec, ...]: ...


class ProviderRegistryError(ValueError):
    pass


class DuplicateProviderError(ProviderRegistryError):
    pass


class UnknownProviderError(ProviderRegistryError):
    pass


class InvalidProviderAliasError(ProviderRegistryError):
    pass


class ProviderRegistry:
    """Extensible provider catalog.

    Provider identity remains a persisted string. Adding a provider therefore means
    registering an adapter rather than modifying a shared runtime enum/branch.
    """

    __slots__ = ("_adapters", "_aliases")

    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}
        self._aliases: dict[str, str] = {}

    @staticmethod
    def _key(value: str) -> str:
        key = str(value).strip().lower()
        if not key:
            raise ProviderRegistryError("Provider key must not be empty")
        return key

    def register(self, adapter: ProviderAdapter) -> None:
        if not isinstance(adapter, ProviderAdapter):
            raise TypeError("Provider adapter does not satisfy ProviderAdapter")
        key = self._key(adapter.manifest.key)
        if key in self._adapters or key in self._aliases:
            raise DuplicateProviderError(f"Provider already registered: {key}")
        self._adapters[key] = adapter

    def register_alias(self, alias: str, target: str) -> None:
        alias_key = self._key(alias)
        target_key = self._key(target)
        if alias_key in self._adapters or alias_key in self._aliases:
            raise DuplicateProviderError(
                f"Provider or alias already registered: {alias_key}"
            )
        if target_key not in self._adapters:
            raise InvalidProviderAliasError(
                f"Provider alias target is not registered: {target_key}"
            )
        self._aliases[alias_key] = target_key

    def canonical_key(self, key: str) -> str:
        normalized = self._key(key)
        return self._aliases.get(normalized, normalized)

    def contains(self, key: str) -> bool:
        return self.canonical_key(key) in self._adapters

    def resolve(self, key: str) -> ProviderAdapter:
        canonical = self.canonical_key(key)
        adapter = self._adapters.get(canonical)
        if adapter is None:
            raise UnknownProviderError(f"Unknown Provider: {key}")
        return adapter

    def manifests(self) -> tuple[ProviderManifest, ...]:
        return tuple(
            self._adapters[key].manifest
            for key in sorted(self._adapters)
        )

    def aliases(self) -> Mapping[str, str]:
        return dict(self._aliases)


__all__ = [
    "DuplicateProviderError",
    "InvalidProviderAliasError",
    "ProviderAdapter",
    "ProviderConnection",
    "ProviderManifest",
    "ProviderRegistry",
    "ProviderRegistryError",
    "UnknownProviderError",
]
