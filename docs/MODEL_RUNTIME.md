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

Provider raw metadata remains provenance/evidence and is not itself the runtime semantic contract. OpenAI discovery has a small, versioned exact-ID enrichment with documented sources. Remote explicit fields take precedence over enrichment; explicit Project overrides take precedence over the resulting baseline. Unknown IDs and fine-tunes are not matched by name fragments.

Discovery exposes an additive `model_spec` field and the same object at the historical `raw.woobe_model_spec` path. `normalization_status` distinguishes `normalized`, `unclassified` and `unsupported_execution`. An unclassified item has no invented operations or spec. Generation selection requires `language.generate` and text output; Agent binding additionally checks the existing strategy's interaction requirements. Image/audio/video/realtime identification does not add executable strategies.

New definitions use strict authoring validation shared with portable ModelSpec validation. Provider/model/type must match the credential and declared family. Unknown fields, invalid flags, empty operation/modality sets and nonfinite numbers are rejected. `spec_hash` and `spec_version` are server-derived; optional client values are assertions, including in a hash-only PATCH. A normalized Model cannot be cleared with `spec: null`; identity changes require a matching new spec and discard stale catalog overrides. Historical deserialization and frozen hashes retain their existing format.

### Baseline and explicit overrides

`metadata.model_spec_baseline` retains the normalized baseline. `metadata.model_spec_overrides` contains only explicit author decisions, grouped as `capabilities`, `limits` and `pricing`. The persisted `spec` is the effective result. For example:

```json
{
  "model_spec_overrides": {
    "capabilities": {"tool_calling": false, "streaming": "unknown"},
    "limits": {"context_window": 128000},
    "pricing": {"input_cost_per_1m_tokens": 0}
  }
}
```

On update, an omitted field preserves its override. `{"action":"inherit"}` or `{"action":"clear"}` removes that field's override and restores the baseline. Capability `"unknown"` deliberately removes the effective declaration. Legacy metadata nulls remain no-ops; normalized override nulls are rejected. Positive integer limits, finite nonnegative prices and real booleans are validated by the backend. Zero price is distinct from missing price. Rates are normalized to currency per million tokens; only confirmed USD token rates qualify for USD metering.

New manual definitions must affirm required capabilities: unknown tool calling fails closed when Tools are enabled, with `model_capability_unknown` rather than an unsupported claim. Historical legacy resolution retains its diagnostic warning behavior.

Fresh portable Agent definitions that use Tools should include a `model_spec_hint` affirming tool calling for their Model. The same rule applies to local YAML development and structural installation; declaring remote references does not imply model capability support. Exported historical specs and records resolved through legacy compatibility keep their original evidence.

### Explicit catalog comparison and application

`GET /ai/provider-models/sync-preview` accepts `project_id`, `provider_credential_id`, `environment` (default `draft`) and optional `capability` (`generation` or `embedding`). It does not change Models or runtime bindings. Each candidate includes installed and proposed specs, `candidate_digest`, expected credential/model revisions and a change classification: new, unchanged, semantic/pricing/display/provenance change, manual override, unsupported/unclassified or not discovered. Missing catalog entries never imply archival.

`POST /ai/provider-models/sync-apply` accepts the same scope, `expected_credential_revision`, `expected_configuration_revision` from preview, and selected `{model_id, installed_model_id, expected_model_revision, candidate_digest}` objects. The backend rediscovers outside SQL, then rechecks authority, environment pins, status, revisions and digests under owner locks. A changed candidate or binding returns HTTP 409 with a stable conflict code. The batch is atomic: all preconditions pass before writes.

Apply creates a new definition or reuses an active semantic equivalent, preserving explicit manual overrides. Reuse retains the exact installed definition and records the reviewed catalog evidence separately in `metadata.catalog_observation`, without changing its authoring revision time. It never rebinds Agents, Staging, Production, Releases or pinned Sessions. Adopt the returned Model ID explicitly on the Agent Draft. Repeated or concurrent application reuses the same definition. There is no scheduler or automatic refresh job.

Preview requires `model:read` and `provider:read`; apply additionally requires `model:write`. Centrally bound discovery also requires the existing environment validation permission. Configuration acquisition/validation evidence follows the existing discovery contract. Remote HTTP and secret resolution occur before the apply transaction.

The exact `model_spec_hash()` remains the definition/snapshot integrity hash. `effective_model_semantic_fingerprint()` is a separate comparator: it includes canonical identity, operations, modalities, interaction, capability flags/configuration, limits, normalized pricing and runtime constraints, while excluding display names, capability sources, timestamps and raw provenance. It never replaces a release, portable-package or metering hash.

## Backward compatibility

Current ProviderModel, Agent provider/model fields, LangChain-backed language execution and legacy Releases remain supported during migration.

Legacy records that do not contain a normalized ModelSpec are materialized by `LegacyModelSpecResolver`. Historical model-name inference is intentionally isolated there. New runtime/domain code must use normalized ModelSpec semantics.

The historical `custom` provider identifier remains an alias for `openai_compatible`.

## Deterministic releases

Drafts may resolve current provider/catalog information. Releases freeze the effective normalized ModelSpec and hash used by execution. Later provider discovery changes must not silently change the semantics of an already released Agent.

Primary and fallback execution use the frozen spec's provider/model and the captured credential ID. The linked credential must still belong to the Project, be active and resolve to the same canonical provider; otherwise execution fails before invocation. Editing or rebinding the current Model does not redirect a frozen Release. Model identifiers/credential bindings/endpoints referenced by Releases cannot be retargeted in place (`MODEL_IDENTITY_IN_USE`). Credential provider/endpoint changes under Models or Releases fail with `CREDENTIAL_IDENTITY_IN_USE`; compatible secret rotation remains supported. Publication rechecks bindings under the same SQL locks as identity changes.

Legacy Releases without a complete frozen spec keep compatibility resolution, without rewriting historical snapshots or hashes. Alias interpretation (`custom` / `openai_compatible`) does not rewrite published evidence.

## Embeddings

The implemented embedding clients are OpenAI, OpenAI Compatible (including `custom`) and OpenRouter. Credential listing advertises `supports_embedding` from the registered provider manifest, so the UI follows implemented support. Compatible endpoints require a configured Base URL and never fall through to OpenAI's default endpoint. Model endpoint metadata takes precedence for compatible clients; OpenRouter retains credential endpoint precedence. OpenRouter's `/embeddings/models` endpoint uses the same normalized ModelSpec pipeline and converts documented prompt prices from USD/token to USD/million tokens. Missing prices/dimensions stay unknown.

Vector Snapshots currently require 1536 dimensions. Catalog eligibility alone does not establish that a model can build a snapshot; configure an accepted dimension and pass the existing snapshot validation before indexing. Anthropic/DeepSeek embedding clients and new image/audio/video/realtime strategies are not introduced by catalog classification.

## Extension rules

To add a provider, implement the provider contract and register the implementation. Do not add provider branches to ExecutionStrategy.

To add a model family, add/emit its ModelSpec semantics and implement a ModelOperationStrategy plus compatible execution/output strategies. Context, Knowledge and Tools should only be bound when those strategies declare them compatible.

Provider-specific SDK classes, LangChain types and wire-format payloads remain infrastructure details and must not become application/domain contracts.
