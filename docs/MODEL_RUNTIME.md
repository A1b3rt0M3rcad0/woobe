# Model and Provider Runtime

Woobe treats provider integration, model semantics and execution orchestration as separate boundaries.

## Runtime model

```text
Agent / Release
    |
ProviderModel
    |
ModelSpec
    |
Compatibility validation
    |
RuntimePlan
    +-- ExecutionStrategy
    +-- ModelOperationStrategy
    +-- ContextStrategy?
    +-- KnowledgeStrategy?
    +-- OutputStrategy
    +-- Tools state
    |
Provider implementation
    |
External model API
```

A model is not assumed to be a conversational LLM. `ModelSpec` explicitly declares model type, operations, input/output modalities, interaction semantics, capabilities, limits, pricing/provenance and provider metadata.

Known operation identifiers include `language.generate`, `embedding.create`, reranking, image generation, speech transcription/synthesis, realtime sessions and video generation. The identifiers are strings so custom families such as JEV can be introduced without redesigning the core type system.

## Strategy compatibility

ExecutionStrategy owns orchestration: order, conditions, retries, capability phases and termination. ModelOperationStrategy owns one semantic model operation. Provider implementations own provider/protocol translation.

Compatibility is checked before provider invocation. Standard execution requires conversational `language.generate` semantics and text output. Embedding execution uses `embedding.create`, does not require conversation, does not bind ContextManager or Knowledge, and does not expose Tools.

Tools are conditional: a Strategy may allow Tools without requiring them. When Tools are enabled, the effective ModelSpec must support tool calling.

Output validity is modality-specific. Empty text is invalid for a text-output strategy, but a valid embedding/image/audio/custom output is not considered empty merely because it contains no text.

## ModelSpec resolution and override precedence

Woobe uses one normalized ModelSpec contract rather than maintaining a second global model database.

The composition path is:

1. the ProviderAdapter normalizes remote provider discovery/catalog data into ModelSpec;
2. explicit Project/manual metadata overrides supported limits, pricing and declared capabilities when a ProviderModel is created or updated;
3. the effective normalized ModelSpec is persisted with the ProviderModel together with its version/hash;
4. a Release freezes that effective spec/hash so later provider-catalog changes cannot alter released behavior;
5. historical ProviderModels/Releases without a normalized spec use LegacyModelSpecResolver as the compatibility fallback.

Provider raw metadata remains provenance/evidence and is not itself the runtime semantic contract. A future curated Woobe model catalog can participate before persistence by producing/augmenting the same ModelSpec; it does not require another runtime abstraction.

## Backward compatibility

Current ProviderModel, Agent provider/model fields, LangChain-backed language execution and legacy Releases remain supported during migration.

Legacy records that do not contain a normalized ModelSpec are materialized by `LegacyModelSpecResolver`. Historical model-name inference is intentionally isolated there. New runtime/domain code must use normalized ModelSpec semantics.

The historical `custom` provider identifier remains an alias for `openai_compatible`.

## Deterministic releases

Drafts may resolve current provider/catalog information. Releases freeze the effective normalized ModelSpec and hash used by execution. Later provider discovery changes must not silently change the semantics of an already released Agent.

## Extension rules

To add a provider, implement the provider contract and register the implementation. Do not add provider branches to ExecutionStrategy.

To add a model family, add/emit its ModelSpec semantics and implement a ModelOperationStrategy plus compatible execution/output strategies. Context, Knowledge and Tools should only be bound when those strategies declare them compatible.

Provider-specific SDK classes, LangChain types and wire-format payloads remain infrastructure details and must not become application/domain contracts.
