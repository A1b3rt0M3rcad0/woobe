# Cross-Cutting SDK Invariants

These rules are architectural contracts. A change that violates one needs an explicit redesign, documentation update and targeted regression coverage.

## 1. The SDK is a client, not a control plane

Agent configuration, Network topology, provider/model selection, Tools, Knowledge, execution strategy and durable Runtime truth remain server-side.

The SDK consumes already published runtime targets.

## 2. Runtime Key is authoritative

The application-provided `alias` is a local label. Runtime routing and authorization are determined by the Runtime Key and server-side Release binding.

Do not infer authority from alias, Run ID or Session ID.

## 3. Chat is lazy

Constructing `Chat` must not create a Run. The create-and-observe request starts when `events()` is iterated.

## 4. One Chat represents one logical Run

After the canonical `run_id` is known, transport recovery must reattach to that same Run.

Do not submit a second execution to recover a broken stream.

Before canonical identity is known, fail closed unless a server-supported idempotency mechanism can prove a retry is the same logical create operation.

## 5. Run identity cannot drift

Within one Chat, canonical Run ID, Session ID and Run kind cannot change. A conflicting event is a protocol violation.

## 6. Semantic events are Runtime Protocol v2 events

A yielded `WoobeEvent` must contain the complete canonical envelope:

- `protocol_version`;
- `event_id`;
- `run_id`;
- `session_id`;
- `run_kind`;
- `sequence`;
- `type`;
- `occurred_at`;
- `payload`.

Do not fabricate missing identity, timestamps or sequence values from legacy aliases.

## 7. Transport frames are not semantic events

Heartbeats, realtime-degradation notices and pre-Acceptance transport errors remain transport/control behavior. They must not masquerade as `WoobeEvent`.

## 8. Sequence is semantic ordering

Ignore stale/duplicate incremental events at or below the local high watermark. A gap must trigger safe recovery rather than guessed ordering.

A `run.state` snapshot replaces observed state at its declared high watermark according to the Runtime contract.

## 9. External Context has create-time semantics

External Context values are sent when creating the Run and are authoritatively validated by Runtime Acceptance.

Reattach observes the accepted Run and must not resend or silently mutate External Context.

## 10. Session correlation is not automatic memory

Every accepted Run belongs to a Session, including isolated/stateless execution. Session identity by itself does not imply that a stateless target gains conversational history semantics.

## 11. Public API excludes transport implementation

`src/woobe/_transport/` is private. Public models and exceptions must not expose `httpx` response objects, SSE parser internals, Redis cursors or server persistence details.

## 12. Terminal result projection is additive

`Chat.result` is an ergonomic projection of successful terminal Runtime events. It does not replace the canonical event stream and must not fabricate a successful result for failed/cancelled terminal states.

The result should be available before the corresponding successful terminal event is yielded to the caller.

## 13. Additive Runtime payloads should remain forward compatible

Unknown future fields should be preserved or safely ignored according to the documented model contract rather than causing unnecessary breakage when the Runtime adds compatible data.
