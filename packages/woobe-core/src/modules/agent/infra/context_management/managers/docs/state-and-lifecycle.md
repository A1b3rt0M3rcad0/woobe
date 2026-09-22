# State and lifecycle

Every Context Manager now declares a serializable `state_type`, parallel to Execution Strategies.

## Base state

~~~python
class ContextManagerState(BaseModel):
    model_config = ConfigDict(extra="forbid")
~~~

Standard uses the empty base state because its algorithm is stateless.

Adaptive uses:

~~~python
class AdaptiveContextState(ContextManagerState):
    summaries: dict[str, ContextSummaryResult]
    summary_generation: int = 0
~~~

## Invocation lifecycle

~~~text
Run-local Context Manager state
        │ restore
        ▼
Model Invocation begins
        │
        ▼
Runtime builds ContextManagerContext
        │
        ▼
await Manager.assemble(ctx)
        │
        ├── inspect capacity/inventory/invocation
        ├── mutate typed state
        ├── await summary capability if required
        ├── await checkpoint if state becomes durable
        └── program effective selection policy
        │
        ▼
shared materialization + ContextSnapshot
        │
        ▼
Model Invocation
~~~

A new `ContextManagerContext` is built for each Model Invocation, but its `ctx.state` is restored from run-local `context_manager_state`.

## Hot state

When `await ctx.checkpoint(...)` succeeds, Runtime immediately updates the current execution context's `context_manager_state`. The next Model Invocation in the same Run sees that state without reading an external repository.

## Durable state

A Context checkpoint emits a durable `context.checkpoint` event containing:

~~~text
manager_name
boundary
serialized state
~~~

Normal Execution checkpoints also embed the current Context Manager state. This means a later safe Execution continuation already carries the latest Context algorithm state.

## Recovery semantics

`context.checkpoint` is not itself a causal continuation point for Tool execution.

Recovery first applies the existing Tool-safety rules using real `execution.checkpoint` boundaries. If the durable prefix is resumable, it overlays the newest durable Context Manager state onto the continuation passed to the recovery runtime.

If no Execution checkpoint exists but the durable prefix has no unsafe Tool side effect, execution may restart from the beginning while still restoring Context Manager state. This avoids repeating an already checkpointed semantic summary.

## State ownership

State belongs to the concrete algorithm. Runtime serializes it generically and validates it through `state_type` on restore.

Do not put these in Manager state:

~~~text
provider clients
LangChain/provider messages
database sessions
Redis/Mongo handles
runtime stream objects
ContextSnapshot objects
Tool executors
~~~

Store typed identifiers, hashes, counters and serializable transformation results instead.

## Summary state

Adaptive persists `ContextSummaryResult`, including summary content, source refs/hash, units and summary-model provenance. The summary remains a transformation result; persisting its metadata in Manager state does not change its source ontology.

## Run-local versus cross-Run

Current Context Manager state is Run-local. A new user turn that creates a new Run does not automatically inherit Adaptive summary state.

Cross-Run rolling Session summary requires a separate Session Context Store or checkpoint/memory persistence contract. That is intentionally not hidden inside Context Manager state.

## Manager changes

If a selected Manager changes, state is restored only when the persisted `manager_name` matches the selected Manager. State from one algorithm is not deserialized into another algorithm's state type.
