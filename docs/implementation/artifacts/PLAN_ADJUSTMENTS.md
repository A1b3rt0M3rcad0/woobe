# Approved execution scope adjustments

The supplied implementation plan remains preserved byte-for-byte in
[`PLAN.md`](PLAN.md); its original source hash remains recorded in
[`manifest.json`](manifest.json). This file records execution-scope adjustments
requested by the user and does not rewrite that source document.

## Steps 21, 36, 37, 58 and G8: provider qualification is optional

The plan's live-provider acceptance requirement is replaced for this delivery by
deterministic provider-contract tests and database-backed integration tests using
the same provider ports. This applies to document enrichment, visual input,
image generation, and the retrieval/generation benchmark. Tests cover provider
selection, endpoint scoping, credential isolation, authorization, metering,
durable recovery, citations, and invalid or uncertain outcomes.

No OpenAI account, API key, endpoint, model, or `WOOBE_ARTIFACT_OPENAI_API_KEY`
binding is required. The implementation remains provider-neutral; a deployment
can select any supported provider and configure its credential through the
existing Environment approval path. Without a configured provider, model-backed
operations stay unavailable while deterministic and storage-backed behavior
continues to work. Live-provider smoke tests remain optional deployment
qualification and are never reported as passed by this implementation plan.

This adjustment changes the acceptance method in steps 21, 36, 37 and 58 and the
provider wording in G8. It does not waive security, isolation, provider
revocation, output validation, or honest reporting of skipped live tests. The
provider-neutral tests must exercise the actual production adapters through
peers/fixtures, and implementation completion must not be presented as live
provider qualification.
