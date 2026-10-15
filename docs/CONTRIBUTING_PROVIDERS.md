# Contributing model/provider support

Provider support is a valid Woobe Core contribution axis, but it must not bypass existing model-config, credential, release and observability boundaries.

A provider adapter must keep credentials server-side, preserve the effective provider/model identity on Runs/Traces, normalize streaming/error behavior, respect timeouts and avoid adding provider-specific business rules to shared runtime code.

Prefer compatibility through an existing protocol before creating a new abstraction. OpenAI-compatible providers should reuse that path when semantics are genuinely compatible.

A contribution should include focused tests for request mapping, response/stream normalization, provider errors and any capability flags it introduces. Provider pricing belongs to explicit versioned pricing/usage logic rather than credential objects.

All external contributions remain subject to `CONTRIBUTOR_LICENSE_AGREEMENT.md`, and third-party SDK/dependency additions must be reviewed for license compatibility and notice obligations.


## Provider runtime contract

Provider support is registered through the model-provider registry. Shared execution code must not branch on provider identity. A provider implementation owns authentication/connection validation, remote model discovery, provider/protocol normalization and provider-specific errors. The normalized result exposed to the rest of Woobe is a `ModelSpec`.

The built-in first-class providers are OpenAI, OpenAI Compatible, OpenRouter, Anthropic and DeepSeek. The historical `custom` identifier remains a compatibility alias for the OpenAI-compatible provider. Persisted provider identifiers remain strings so adding a provider does not require expanding a closed core enum.

Infrastructure implementations consume the stable contracts under `modules.agent.application.interfaces`. Provider-specific SDK or wire-format types must not leak into ExecutionStrategy, ModelSpec or other application/domain contracts.

## ModelSpec and compatibility

`ModelSpec` is the semantic source of truth for a model. It separates:

- model family/type;
- supported operations such as `language.generate` or `embedding.create`;
- input and output modalities;
- interaction semantics such as conversation/history/realtime support;
- structured capabilities such as tool calling, structured output and streaming;
- operational limits and normalized pricing;
- provider/catalog provenance and raw provider metadata.

Execution strategies are not assumed to work with every ModelSpec. Runtime composition is validated before provider invocation. A Strategy declares compatible operations, modalities and whether Context, Knowledge and Tools are required, optional or unsupported.

Legacy ProviderModel records without a normalized spec are resolved by the dedicated compatibility resolver. Model-name heuristics are confined to that compatibility path and must not be introduced into new domain/runtime code.

## Adding a model operation

A new model family should normally add a ModelSpec operation and a `ModelOperationStrategy`, not provider branches inside ExecutionStrategy. The model operation strategy owns operation-level invocation semantics while ExecutionStrategy owns workflow orchestration.

For example, embedding execution uses `embedding.create`, has embedding output, and intentionally does not bind Conversation, ContextManager, Knowledge or Tools. Image, audio, realtime, video and custom/JEV families should follow the same pattern.

## Release determinism

Released Agents carry a frozen normalized ModelSpec snapshot/hash. Provider discovery may evolve after a release, but released execution semantics must not silently change. Legacy releases without a frozen spec remain supported through compatibility resolution.

## Discovery evidence and reconciliation

Normalize explicit provider metadata before applying the small, versioned provider enrichment and then explicit Project overrides. Missing capability evidence is unknown; it is distinct from an explicit false value. Generic `type=model` and substrings of a model name are not evidence of a language or embedding operation. Return an unclassified discovery item when operations/modalities cannot be established. Keep provider-specific features that Woobe does not execute in provenance.

OpenRouter general discovery requests all output modalities; its separate embedding endpoint emits the same spec contract. Anthropic discovery follows bounded `after_id` pagination, deduplicates IDs and rejects missing/repeated cursors or partial-page failure. Lifecycle remains catalog provenance and never changes installed status. DeepSeek preserves effort and protocol constraints without merging Anthropic Messages capabilities into the OpenAI protocol used by Woobe. Missing per-model flags do not become universal support.

Add deterministic fixtures for explicit true/false/unknown capabilities, non-language modalities, invalid numeric values, alias resolution and discovery failures. Pagination, embedding price units and protocol constraints need provider-specific coverage. Do not include authentication headers or upstream error bodies in diagnostics.

Catalog refresh is explicit preview/apply as documented in [Model Runtime](MODEL_RUNTIME.md). Preserve the exact definition hash; use the semantic fingerprint only for comparison/reuse. New provider behavior must preserve identity locks, revision/digest checks, manual overrides and frozen primary/fallback destinations.
