# Governed document model operations

`governed-model/1` adds inferred summaries to an extraction recipe. Its model
reference identifies an actual Agent provider model definition revision and a
Core Environment key definition revision. Provider model definition revisions
are independent from the ModelSpec JSON schema version.

Admission freezes metadata, approved Environment value pins, destination,
credential binding revision, semantic model specification and configured pricing
in the real ProcessingJob transaction. No Run, Agent, Trace or Run configuration
lease is synthesized. Core remains the authority for current use policy,
revocation, destination and retained pinned value availability. A rotated value
does not silently replace a queued job's accepted pin. Binding identity participates
in generation reuse, preventing a cache hit across credentials or value versions.

The Worker invokes the existing Agent semantic runtime/provider factory through
public capabilities and a shared composition bridge. Document application code
has no provider SDK or secret dependency. Existing scoped HTTP credential
transport resolves Core material immediately before outbound transmission,
disables redirects and environment proxy inheritance, and removes authorization
headers after use. No global provider key is changed. SDK retries are explicitly
zero. Owned clients close before cancellation acknowledgement.

Each operation reserves durable admission before sending. The default policy
permits at most four operations and 100,000 reserved tokens per job, 32,768 UTF-8
input bytes including control/schema, at most the recipe's output token limit,
and a 60-second invocation deadline. Input bytes conservatively reserve input
tokens; unknown usage retains that reservation. These are token/call limits;
unknown provider pricing is never represented as a guaranteed dollar cap.

A deterministic operation identity binds the job, operation key, input and model
binding. Completed bounded results are checkpointed before any summary object
write, so recovering object publication does not repeat a paid call. A dispatched
operation with an unknown outcome becomes uncertain and cannot be blindly sent
again. Invalid model output still records known usage. Acknowledgement can
account previously admitted I/O after authority changes, but cannot authorize
another send or publish a generation. SQL protects accepted bindings, operation
identity, dispatched ownership and terminal evidence from mutation.

Only locally verified canonical text fragments enter the prompt. Version 1
selects at most eight nonempty blocks and at most 512 Unicode characters from
each; coverage is explicitly partial when anything is omitted. Model responses
are strict bounded JSON, with duplicate keys, unsupported fields, foreign source
identifiers, reversed section intervals and invalid UTF-8 rejected. All source
locators/checksums are constructed by the server from the verified document;
model-generated identifiers never grant authority.

`summary.json` is a read-only representation entry marked
`inferred: true` and `untrusted_model_derivative`. Each summary cites exact
revision, original checksum, generation, block and canonical character interval.
It is written before bundle sealing and becomes visible only in the same commit
as its coherent generation, optional native document index and successful job.
Native structure is preserved. This interface is not a chat/tool execution loop.

Usage observations enter the standard Artifacts outbox and Metering inbox in
short owned transactions. Stable call/usage identity and observation revisions
prevent duplicate call/token/cost totals. A later known observation adjusts the
original daily bucket by the difference, without fabricating a Run or Trace.
Tokens and dollar costs remain nullable when unknown. Configured price estimates
are distinguished from provider-reported costs.

## Qualification

Deterministic provider-port tests exercise actual Core encryption/policies,
PostgreSQL, local/S3 storage, Worker execution, source reads, cache reuse,
revocation, invalid output, uncertainty and metering. Separate runtime tests
qualify real OpenAI SDK construction with zero retries and owned cleanup without
sending network traffic. These tests are not live-provider acceptance.

The explicit live test is
`tests/integration/artifacts/test_document_model_live_postgres.py`. It is an
optional environment acceptance check, enabled only with
`WOOBE_ARTIFACT_RUN_LIVE_MODEL=1`. Installing, starting and testing the environment
does not require an OpenAI account, an OpenAI key, or a live-provider connection.
The original plan's live acceptance remains unexecuted until an authorized
provider is selected; passing deterministic tests does not establish live acceptance.

For an explicitly requested live test, configure the selected provider through:

- `WOOBE_ARTIFACT_MODEL_PROVIDER`: an existing Woobe provider identifier.
- `WOOBE_ARTIFACT_MODEL_NAME`: that provider's model identifier.
- `WOOBE_ARTIFACT_MODEL_BASE_URL`: its approved HTTPS endpoint.
- `WOOBE_ARTIFACT_MODEL_API_KEY`: its credential, supplied securely.

There is no default vendor, model, endpoint or global-key fallback for the live
test. It creates the same Core-approved scoped binding and invokes the same
Agent/Worker path, using one tiny source and at most 512 output tokens. Run with
`--tb=no` and private logs. An opted-in run with incomplete configuration fails;
an ordinary run records this test as skipped without asking for any credential.

Existing registered adapters include OpenAI, OpenAI-compatible endpoints,
OpenRouter, DeepSeek and Anthropic. A self-hosted model may use the compatible
adapter through an approved authenticated HTTPS endpoint. This does not claim
support for unauthenticated or plain-HTTP model servers. Model availability and
structured-output support still depend on the selected adapter and model.

An existing cloud draft may contain a legacy OpenAI-specific secret declaration.
The application and these tests do not read it, and no OpenAI binding is required
to install, start, or validate the implementation. Environment configuration
removal is handled in environment settings because the draft API cannot remove an
existing secret requirement. A retained declaration is not provider qualification
and does not enable model-backed features by itself.
