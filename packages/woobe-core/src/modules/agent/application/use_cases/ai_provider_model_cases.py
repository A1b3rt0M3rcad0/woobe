from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Mapping
from uuid import UUID

from modules.agent.application.dtos.ai_dtos import (
    CreateProviderModelInput,
    ListProviderModelsInput,
    ProviderModelOutput,
    UpdateProviderModelInput,
)
from modules.agent.application.interfaces.model_spec_compatibility import (
    LegacyModelSpecResolver,
)
from modules.agent.application.interfaces.provider_model_repository import (
    ProviderModelRepository,
)
from modules.agent.application.interfaces.repositories import ProviderCredentialRepository
from modules.agent.domain.entities import ProviderModel
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus
from modules.agent.domain.model_spec import (
    ModelCapability,
    ModelCapabilityNames,
    ModelLimits,
    ModelSpec,
    model_spec_hash,
)
from shared.contracts.errors import ValidationError


_MISSING = object()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _embedded_model_spec(metadata: Mapping[str, Any]) -> Mapping[str, Any] | None:
    direct = metadata.get("model_spec")
    if isinstance(direct, Mapping):
        return direct

    raw = metadata.get("provider_model_raw")
    if isinstance(raw, Mapping):
        nested = raw.get("woobe_model_spec")
        if isinstance(nested, Mapping):
            return nested
    return None


def _parse_model_spec(value: Any) -> ModelSpec | None:
    if value is None:
        return None
    if isinstance(value, ModelSpec):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("Provider model spec must be an object")
    try:
        return ModelSpec.from_dict(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid Provider model spec: {exc}") from exc


def _resolve_model_spec(
    *,
    explicit: Any = _MISSING,
    metadata: Mapping[str, Any] | None = None,
) -> ModelSpec | None:
    if explicit is not _MISSING:
        return _parse_model_spec(explicit)
    embedded = _embedded_model_spec(metadata or {})
    return _parse_model_spec(embedded) if embedded is not None else None


def _positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _provider_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _apply_model_spec_overrides(
    spec: ModelSpec,
    metadata: Mapping[str, Any] | None,
) -> ModelSpec:
    metadata = _mapping(metadata)
    capability_metadata = _mapping(metadata.get("capabilities"))
    capability_source = str(
        metadata.get("capability_source")
        or metadata.get("source")
        or "manual"
    )

    capabilities = dict(spec.capabilities)
    capability_keys = {
        "supports_tools": ModelCapabilityNames.TOOL_CALLING,
        "supports_json": ModelCapabilityNames.STRUCTURED_OUTPUT,
        "supports_streaming": ModelCapabilityNames.STREAMING,
    }
    for legacy_key, normalized_key in capability_keys.items():
        supported = capability_metadata.get(legacy_key)
        if not isinstance(supported, bool):
            continue
        existing = capabilities.get(normalized_key)
        capabilities[normalized_key] = ModelCapability(
            supported=supported,
            config=(dict(existing.config) if existing is not None else {}),
            source=capability_source,
        )

    context_window = _positive_int(metadata.get("context_window"))
    max_output_tokens = _positive_int(metadata.get("max_output_tokens"))
    limits = ModelLimits(
        context_window=(
            context_window
            if context_window is not None
            else spec.limits.context_window
        ),
        max_input_tokens=spec.limits.max_input_tokens,
        max_output_tokens=(
            max_output_tokens
            if max_output_tokens is not None
            else spec.limits.max_output_tokens
        ),
        max_batch_size=spec.limits.max_batch_size,
        max_input_bytes=spec.limits.max_input_bytes,
        max_output_bytes=spec.limits.max_output_bytes,
    )

    pricing = dict(spec.pricing)
    pricing_override = _mapping(metadata.get("pricing"))
    for key in (
        "input_cost_per_1m_tokens",
        "output_cost_per_1m_tokens",
        "currency",
        "billing_unit",
        "source",
    ):
        value = pricing_override.get(key)
        if value is not None:
            pricing[key] = value

    return replace(
        spec,
        capabilities=capabilities,
        limits=limits,
        pricing=pricing,
    )


def _manual_model_spec(
    item: ProviderModel,
    *,
    provider: Any,
    explicit_model_type: str | None = None,
) -> ModelSpec:
    metadata = dict(item.metadata or {})
    if explicit_model_type:
        metadata["model_type"] = explicit_model_type
    compatibility_model = SimpleNamespace(
        id=item.id,
        provider_credential_id=item.provider_credential_id,
        name=item.name,
        model=item.model,
        metadata=metadata,
    )
    spec = LegacyModelSpecResolver().resolve(
        compatibility_model,
        provider=_provider_value(provider),
    )
    spec = replace(spec, source="manual")
    return _apply_model_spec_overrides(spec, metadata)


def _apply_normalized_spec(
    item: ProviderModel,
    spec: ModelSpec | None,
    *,
    clear_when_none: bool = False,
) -> None:
    if spec is None:
        if clear_when_none:
            item.model_type = None
            item.spec = None
            item.spec_version = None
            item.spec_hash = None
        return

    item.model_type = spec.model_type
    item.spec = spec.as_dict()
    item.spec_version = spec.spec_version
    item.spec_hash = model_spec_hash(spec)


class CreateProviderModelUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(self, input_dto: CreateProviderModelInput) -> ProviderModelOutput:
        credential = await self._load_active_credential(
            input_dto.provider_credential_id,
            input_dto.project_id,
        )
        metadata = input_dto.metadata or {}
        spec = _resolve_model_spec(
            explicit=(
                input_dto.spec
                if input_dto.spec is not None
                else _MISSING
            ),
            metadata=metadata,
        )
        item = ProviderModel(
            project_id=input_dto.project_id,
            provider_credential_id=input_dto.provider_credential_id,
            name=input_dto.name.strip(),
            model=input_dto.model.strip(),
            model_type=input_dto.model_type,
            spec=input_dto.spec,
            spec_version=input_dto.spec_version,
            spec_hash=input_dto.spec_hash,
            metadata=metadata,
            status=ProviderModelStatus.active,
        )
        if spec is None:
            spec = _manual_model_spec(
                item,
                provider=credential.provider,
                explicit_model_type=input_dto.model_type,
            )
        else:
            spec = _apply_model_spec_overrides(spec, metadata)
        _apply_normalized_spec(item, spec)

        if not item.name:
            raise ValidationError("Provider model name is required")
        if not item.model:
            raise ValidationError("Provider model identifier is required")
        saved = await self._provider_model_repo.save(item)
        return _provider_model_to_output(saved, credential.provider)

    async def _load_active_credential(self, credential_id: UUID, project_id: UUID):
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None or credential.project_id != project_id:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)
        status = getattr(credential.status, "value", credential.status)
        if status != CredentialStatus.active.value:
            raise ValidationError("Provider credential must be active")
        return credential


class UpdateProviderModelUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(
        self,
        provider_model_id: UUID,
        input_dto: UpdateProviderModelInput,
    ) -> ProviderModelOutput:
        item = await self._provider_model_repo.get_by_id(provider_model_id)
        if item is None:
            from modules.agent.domain.errors import ModelConfigNotFoundError

            raise ModelConfigNotFoundError
        data = input_dto.model_dump(exclude_unset=True)
        if "provider_credential_id" in data:
            credential = await self._load_credential(
                data["provider_credential_id"],
                item.project_id,
            )
            item.provider_credential_id = credential.id
        else:
            credential = await self._load_credential(
                item.provider_credential_id,
                item.project_id,
            )

        if "name" in data and data["name"] is not None:
            item.name = data["name"].strip()
        if "model" in data and data["model"] is not None:
            item.model = data["model"].strip()
        if "metadata" in data and data["metadata"] is not None:
            item.metadata = data["metadata"] or {}
        if "model_type" in data:
            item.model_type = data["model_type"]
        if "spec_version" in data:
            item.spec_version = data["spec_version"]
        if "spec_hash" in data:
            item.spec_hash = data["spec_hash"]

        explicit_spec = data.get("spec", _MISSING)
        should_re_resolve = (
            explicit_spec is not _MISSING
            or "metadata" in data
            or "model" in data
            or "model_type" in data
            or "provider_credential_id" in data
        )
        if should_re_resolve:
            if explicit_spec is None:
                spec = None
            elif explicit_spec is not _MISSING:
                spec = _resolve_model_spec(
                    explicit=explicit_spec,
                    metadata=item.metadata,
                )
            elif "metadata" in data:
                spec = _resolve_model_spec(metadata=item.metadata)
                if spec is None and item.spec is not None:
                    spec = _parse_model_spec(item.spec)
            else:
                spec = None

            provider_key = _provider_value(credential.provider)
            stale_implicit_spec = (
                explicit_spec is _MISSING
                and spec is not None
                and (
                    spec.model_id != item.model
                    or spec.provider != provider_key
                    or (
                        "model_type" in data
                        and item.model_type is not None
                        and spec.model_type != item.model_type
                    )
                )
            )
            if (
                (spec is None and explicit_spec is not None)
                or stale_implicit_spec
            ):
                spec = _manual_model_spec(
                    item,
                    provider=credential.provider,
                    explicit_model_type=item.model_type,
                )
            elif spec is not None:
                spec = _apply_model_spec_overrides(spec, item.metadata)

            _apply_normalized_spec(
                item,
                spec,
                clear_when_none=explicit_spec is None,
            )

        if "status" in data and data["status"] is not None:
            item.status = data["status"]
        if not item.name:
            raise ValidationError("Provider model name is required")
        if not item.model:
            raise ValidationError("Provider model identifier is required")
        saved = await self._provider_model_repo.update(item)
        return _provider_model_to_output(saved, credential.provider)

    async def _load_credential(self, credential_id: UUID, project_id: UUID):
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None or credential.project_id != project_id:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)
        return credential


class ListProviderModelsUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(
        self,
        input_dto: ListProviderModelsInput,
    ) -> list[ProviderModelOutput]:
        if input_dto.provider_credential_id:
            items = await self._provider_model_repo.list_by_credential(
                input_dto.provider_credential_id
            )
        elif input_dto.project_id:
            items = await self._provider_model_repo.list_by_project(input_dto.project_id)
        else:
            return []
        outputs: list[ProviderModelOutput] = []
        credential_cache = {}
        for item in items:
            credential = credential_cache.get(item.provider_credential_id)
            if credential is None:
                credential = await self._credential_repo.get_by_id(
                    item.provider_credential_id
                )
                credential_cache[item.provider_credential_id] = credential
            outputs.append(
                _provider_model_to_output(
                    item,
                    getattr(credential, "provider", None),
                )
            )
        return outputs


class GetProviderModelUseCase:
    def __init__(
        self,
        provider_model_repo: ProviderModelRepository,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(self, provider_model_id: UUID) -> ProviderModelOutput:
        item = await self._provider_model_repo.get_by_id(provider_model_id)
        if item is None:
            from modules.agent.domain.errors import ModelConfigNotFoundError

            raise ModelConfigNotFoundError
        credential = await self._credential_repo.get_by_id(item.provider_credential_id)
        return _provider_model_to_output(item, getattr(credential, "provider", None))


def _provider_model_to_output(item: ProviderModel, provider=None) -> ProviderModelOutput:
    return ProviderModelOutput(
        id=item.id,
        project_id=item.project_id,
        provider_credential_id=item.provider_credential_id,
        provider=provider,
        name=item.name,
        model=item.model,
        model_type=item.model_type,
        spec=item.spec,
        spec_version=item.spec_version,
        spec_hash=item.spec_hash,
        status=item.status,
        metadata=item.metadata,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
