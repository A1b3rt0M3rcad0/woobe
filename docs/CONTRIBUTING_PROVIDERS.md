# Contributing model/provider support

Provider support is a valid Woobe community contribution axis, but it must not bypass the existing model-config, credential, release and observability boundaries.

A provider adapter must keep credentials server-side, preserve the effective provider/model identity on Runs/Traces, normalize streaming/error behavior, respect timeouts and avoid adding provider-specific business rules to shared runtime code.

Prefer compatibility through an existing protocol before creating a new abstraction. OpenAI-compatible providers should reuse that path when semantics are genuinely compatible.

A contribution should include focused tests for request mapping, response/stream normalization, provider errors and any capability flags it introduces. Provider pricing belongs to explicit versioned pricing/usage logic rather than credential objects.
