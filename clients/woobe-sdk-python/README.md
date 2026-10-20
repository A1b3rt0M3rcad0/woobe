# Woobe SDK

Python SDK for consuming Agents and Agent Networks running on the Woobe Runtime API.

The SDK is intentionally a **runtime client**, not a second control plane and not an agent framework. Agent configuration, Releases, Tools, Knowledge, execution strategies and runtime infrastructure remain server-side in Woobe. Applications connect to an already published runtime target and consume its execution events.

> **Pre-1.0:** the SDK is public and usable, but its APIs can still evolve before the 1.0.0 compatibility boundary.

## Quick start

```python
from woobe import Woobe


woobe = Woobe()

agent = woobe.connect.agent(
    alias="support",
    key="...",
)

# No HTTP request is executed here.
chat = agent.chat(input="Olá")

# The Runtime request starts when events() is actually iterated.
async for event in chat.events():
    print(event.type, event.payload)
```

`Chat` is lazy: constructing it does not create a Run. Iterating `events()` performs the Runtime request.

When the target policy supports conversational continuity, reuse the Session returned by the previous interaction:

```python
chat = agent.chat(
    input="Continue de onde paramos",
    session_id=previous_chat.session_id,
)

async for event in chat.events():
    print(event)
```

When the selected Release declares an External Context contract, provide its values on the Run:

```python
chat = agent.chat(
    input="Consulte meus pedidos",
    external_context={
        "customer_id": "customer-123",
        "language": "pt-BR",
    },
)

async for event in chat.events():
    print(event)
```

The Runtime validates `external_context` against the Agent or Network Release contract during Acceptance. The SDK sends it only when creating the Run; reattach observes the already accepted Run and does not resend context.

After a completed Run, `Chat.result` exposes the terminal Runtime payload as typed SDK objects:

```python
chat = agent.chat(
    input="O que perguntei antes?",
    session_id=session_id,
)

async for event in chat.events():
    if event.type == "token":
        print(event.payload["content"], end="")

result = chat.result
if result is not None:
    print(result.answer)
    print(result.message_id)
    print(result.model)
    print(result.provider)

    if result.usage is not None:
        print(result.usage.total_tokens)
        print(result.usage.cost_usd)

    print(result.agent_release_version)
    print(result.execution_strategy)

    if result.diagnostics is not None:
        print(result.diagnostics.agent_runtime_latency_ms)
```

`result` is `None` before completion and for terminal failures that do not produce a completed result. Agent `done` and Network `execution_completed` events are normalized to the same `ChatResult` surface. Raw streaming events remain available unchanged through `events()`.

The typed result includes `Usage`, `Source`, `ToolCall`, `FallbackInfo`, `ExecutionEvent` and `ExecutionDiagnostics` objects. Unknown future Runtime fields are preserved so the SDK remains forward compatible with additive payload changes.


## Runtime contract validation

The SDK can validate both client-side contract declarations against the immutable Release bound to the Runtime Key before starting a Run.

```python
from pydantic import BaseModel

from woobe import Woobe


class SupportOutput(BaseModel):
    message: str
    confidence: float


class SupportContext(BaseModel):
    name: str
    age: int


woobe = Woobe()

agent = woobe.connect.agent(
    alias="support",
    key="...",
)

validation = await agent.validate_contracts(
    output_contract=SupportOutput,
    external_context=SupportContext,
)

if not validation.valid:
    for issue in validation.output_contract.issues:
        print("output:", issue.code, issue.field)
    for issue in validation.external_context.issues:
        print("external_context:", issue.code, issue.field)
```

`validate_contracts(...)` always declares both public contracts. Each argument accepts a Pydantic `BaseModel` type, a model instance, an explicit JSON Schema `dict`, or `None`. Local Pydantic `$ref` definitions are inlined before the request is sent to `POST /v1/contracts/validate`.

The Runtime Key determines the Agent or Network and the published `staging` or `production` Release being checked. The result contains the Release identity plus separate normalized comparisons for `output_contract` and `external_context`, including deterministic hashes and field-level mismatch issues.

For focused checks, the same target also exposes:

```python
output = await agent.validate_output_contract(SupportOutput)
external = await agent.validate_external_context(SupportContext)
```

The older `validate_output_context(...)` name remains available as a backward-compatible alias for `validate_output_contract(...)`.

These calls validate the SDK's declared contract shape against the published Release. Runtime External Context values passed to `chat(external_context=...)` are still validated authoritatively during Run Acceptance, including required/default/session semantics.

Validation is explicit and separate from `chat()`; the SDK does not add a hidden contract request to every Run.

The same validation surface is available for Networks.

## Runtime model

The public SDK surface follows four concepts:

```text
Target   -> Agent or Network
Session  -> longitudinal/correlation boundary
Run      -> one finite logical execution
Event    -> one semantic event from that Run
```

Every accepted Run belongs to a Session. This also applies to stateless Agent execution: when no Session is supplied, Woobe creates an isolated Session for identity and correlation. That does not enable implicit history continuity for a stateless Agent.

Every event yielded by `Chat.events()` is a canonical Runtime Protocol v2 `WoobeEvent`:

```python
async for event in chat.events():
    event.protocol_version  # 2
    event.event_id
    event.run_id
    event.session_id
    event.run_kind          # "AGENT" | "NETWORK"
    event.sequence
    event.type
    event.occurred_at
    event.payload
```

The SDK preserves Woobe event names and payloads. It does not infer identity from payload aliases such as `execution_id` or `network_session_id`.

## `WoobeEvent`

```python
class WoobeEvent(BaseModel):
    protocol_version: Literal[2]
    event_id: str
    run_id: str
    session_id: str
    run_kind: Literal["AGENT", "NETWORK"]
    sequence: int
    type: str
    occurred_at: datetime
    payload: dict[str, Any]
```

All fields above are mandatory for semantic events. The SDK validates the Runtime v2 envelope instead of fabricating missing identity or ordering metadata.

Transport/control frames are different. Heartbeats, realtime-degradation notices and pre-Acceptance errors do not pretend to be semantic Run events. They are handled internally by the SDK and are not yielded as `WoobeEvent` objects.

## Reattach and duplicate-Run safety

A stream connection observes a Run; it does not own it.

Once the canonical `run_id` is known, a transport interruption is recovered through the reattach endpoint for the **same Run**:

```text
POST /v1/run/stream
        |
        v
 canonical run_id + session_id
        |
   connection loss
        |
        v
GET /v1/runs/{run_id}/stream
        |
        v
 run.state @ high watermark
        |
        v
     same Run
```

If only the Session is known, the SDK can resolve the active Run through `/v1/sessions/{session_id}/active-run` before reattaching.

The SDK never submits a second Agent execution after learning the canonical Run ID. If the initial Agent connection is lost before identity can be recovered safely, it fails closed rather than risking a duplicate Run. Network create retries reuse one idempotency key for the same logical execution.

## Sequence handling

`sequence` is the semantic ordering contract. The SSE `id:` field is a transport cursor and, when present for a semantic event, must match the canonical sequence.

The SDK:

- ignores stale or duplicate incremental events at or below the local sequence;
- detects sequence gaps and reattaches instead of guessing;
- treats `run.state` as replacement state at its high watermark;
- validates that Run, Session and Run kind do not change inside one `Chat`.

## Configuration

The default hosted endpoint is `https://api.woobe.com.br`. Self-hosted environments can provide a base URL explicitly or through `WOOBE_BASE_URL`:

```python
woobe = Woobe(base_url="https://woobe.internal.example")
```

For long-lived processes, close the underlying async HTTP client on shutdown:

```python
await woobe.aclose()
```

or use an async context manager:

```python
async with Woobe() as woobe:
    agent = woobe.connect.agent(alias="support", key="...")
    async for event in agent.chat(input="Olá").events():
        print(event)
```

## Repository

```text
src/woobe/          public SDK and private transport implementation
tests/              SDK unit tests
examples/           small executable usage examples
docs/               architecture and runtime contract documentation
```

Start with [`docs/README.md`](docs/README.md) for the documentation index.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
```

Pull requests run the same quality gate on supported Python versions. The integration branch is `master`.

## Governance and licensing

Woobe SDK is licensed under the [MIT License](LICENSE.md). The SDK license is independent from the licenses that govern the Woobe platform itself; using this client does not relicense Woobe Core or Enterprise software.

Repository policies:

- [Contributing](CONTRIBUTING.md)
- [Releasing](RELEASING.md)
- [Security](SECURITY.md)
- [Licensing](LICENSING.md)
- [Trademark policy](TRADEMARKS.md)
- [Changelog](CHANGELOG.md)
- [Coding-agent entry point](AGENTS.md)
