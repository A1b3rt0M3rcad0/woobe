"""Explicit semantics of the deterministic test provider, never a production catalog."""

from modules.agent.domain.model_spec import (
    ModelCapability,
    ModelInteractionSpec,
    ModelLimits,
    ModelSpec,
)
from modules.agent.domain.provider_identity import canonical_provider_key


def declare_language_model_evidence(documents):
    """Fresh tool-bearing fixtures must affirm the provider capabilities they use."""
    for document in documents.values():
        spec = document.get("spec", {})
        if (
            document.get("kind") != "Model"
            or spec.get("model_type", "language") != "language"
            or spec.get("model_spec_hint")
        ):
            continue
        spec["model_spec_hint"] = ModelSpec(
            provider=canonical_provider_key(spec["provider"]),
            model_id=spec["model"],
            display_name=document["metadata"]["name"],
            model_type="language",
            operations=frozenset({"language.generate"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            interaction=ModelInteractionSpec(
                mode="conversation",
                supports_conversation=True,
                supports_history=True,
                supports_system_instruction=True,
                supports_context_injection=True,
            ),
            capabilities={
                name: ModelCapability(True, source="test_fixture")
                for name in ("tool_calling", "structured_output", "streaming")
            },
            limits=ModelLimits(context_window=128000, max_output_tokens=8192),
            source="manual",
            metadata={"base_url": spec["base_url"]} if spec.get("base_url") else {},
        ).as_dict()
