# Architecture rules

Concrete Context Managers may depend on:

```text
application/context_manager_sdk
domain context enums/contracts
```

They must not depend directly on:

```text
ContextAssemblyRequest
LangChain message classes
ContextSnapshot constructors
ContextContribution constructors
hash/provenance mechanics
database repositories
provider factories
execution lifecycle
```

Shared reusable mechanics belong in:

```text
infra/context_management/manager_runtime/
```

A new algorithm-specific behavior belongs in the concrete Manager.

A new capability needed by several Managers may justify a small SDK + Runtime primitive.

Adding a normal Manager must not require modifying the Agent execution path.
