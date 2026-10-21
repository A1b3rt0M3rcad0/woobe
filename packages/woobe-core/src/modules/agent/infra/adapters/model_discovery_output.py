"""Shared normalized catalog DTO projection for every discovery endpoint."""

from modules.agent.application.dtos.model_discovery_dtos import AvailableProviderModelOutput
from modules.agent.application.interfaces.provider_registry import UnclassifiedProviderModel
from modules.agent.domain.model_spec import ModelCapabilityNames, ModelSpec


def _capability_supported(
    spec: ModelSpec,
    name: str,
) -> bool | None:
    capability = spec.capability(name)
    return capability.supported if capability is not None else None


def _spec_to_available_output(
    spec: ModelSpec,
    *,
    provider: str,
) -> AvailableProviderModelOutput:
    if isinstance(spec, UnclassifiedProviderModel):
        return AvailableProviderModelOutput(id=spec.model_id, label=spec.display_name,
            provider=spec.provider, raw=dict(spec.raw), normalization_status="unclassified",
            normalization_issues=list(spec.issues))
    pricing = dict(spec.pricing or {})
    metadata = dict(spec.metadata or {})
    raw = metadata.get("provider_model_raw")
    return AvailableProviderModelOutput(
        id=spec.model_id,
        label=spec.display_name,
        provider=spec.provider,
        source=spec.source,
        owned_by=(
            str(raw.get("owned_by"))
            if isinstance(raw, dict) and raw.get("owned_by")
            else None
        ),
        context_window=(
            spec.limits.context_window
            or spec.limits.max_input_tokens
        ),
        max_output_tokens=spec.limits.max_output_tokens,
        input_cost_per_1m_tokens=pricing.get(
            "input_cost_per_1m_tokens"
        ),
        output_cost_per_1m_tokens=pricing.get(
            "output_cost_per_1m_tokens"
        ),
        supports_tools=_capability_supported(
            spec,
            ModelCapabilityNames.TOOL_CALLING,
        ),
        supports_json=_capability_supported(
            spec,
            ModelCapabilityNames.STRUCTURED_OUTPUT,
        ),
        supports_streaming=_capability_supported(
            spec,
            ModelCapabilityNames.STREAMING,
        ),
        model_type=spec.model_type,
        operations=sorted(spec.operations),
        input_modalities=sorted(spec.input_modalities),
        output_modalities=sorted(spec.output_modalities),
        capabilities={
            name: capability.as_dict()
            for name, capability in spec.capabilities.items()
        },
        model_spec=spec.as_dict(),
        normalization_status=("normalized" if spec.operations & {"language.generate", "embedding.create"} else "unsupported_execution"),
        raw={
            **(raw if isinstance(raw, dict) else {}),
            "woobe_model_spec": spec.as_dict(),
        },
    )
