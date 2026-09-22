# Architecture rules

Concrete Context Managers are asynchronous algorithm code. Runtime primitives own mechanics and side effects.

## Allowed dependency surface

A normal Manager may depend on:

~~~text
modules.agent.application.context_manager_sdk
stable Application interfaces required by the SDK
modules.agent.domain enums/value types
sibling Managers only for explicit algorithm composition
pydantic for Manager-specific serializable State
~~~

## Forbidden dependencies

Concrete Managers must not directly import or use:

~~~text
ContextAssemblyRequest
manager_runtime implementation
LangChain/provider message classes
provider SDKs or model clients
ContextSnapshot/ContextContribution constructors
journal recorder/checkpoint persistence
database repositories
Redis/Mongo/PostgreSQL clients
execution lifecycle internals
Network infrastructure
API/worker packages
~~~

## Async side-effect rule

`async def assemble(...)` does not mean the Manager may perform arbitrary I/O.

Allowed:

~~~python
await ctx.summary.create(...)
await ctx.summary.refresh(...)
await ctx.checkpoint(...)
~~~

Forbidden:

~~~python
await provider.ainvoke(...)
await repository.save(...)
await redis.set(...)
~~~

The SDK primitive is the architectural capability boundary.

## State rule

Manager state must inherit `ContextManagerState`, remain JSON-serializable and contain algorithm state only.

Runtime owns create/validate/dump/restore. A Manager must not know how the state is journaled.

## Summary rule

Semantic summary is a transformation capability. Managers choose when/what; Runtime chooses raw source messages, executes the internal model call, validates lineage, records observability and stages replacement.

Do not expose raw messages just to make a custom summarizer easier.

## Checkpoint rule

`ctx.checkpoint` persists Manager state but is not a Tool-causal Execution checkpoint. Recovery must never use a Context checkpoint to prove an external Tool outcome is safe.

## Primitive rule

Add a shared primitive when multiple Managers need a capability and Runtime can provide precise semantics/evidence. Keep one-off pure algorithm logic in the concrete Manager.

## One-file convention

Current built-ins remain flat:

~~~text
managers/standard.py
managers/adaptive.py
~~~

Reusable side-effecting mechanics go under `manager_runtime/`, not a private `adaptive_runtime/`.

## Quality Gate

- `ARCH082`: explicit Manager resolver/composition boundary;
- `ARCH083`: concrete Manager dependency boundary;
- `ARCH084`: Manager Runtime bridges SDK to shared mechanics and must not depend on concrete Managers.

Architecture tests should evolve with new SDK primitives without weakening these ownership rules.
