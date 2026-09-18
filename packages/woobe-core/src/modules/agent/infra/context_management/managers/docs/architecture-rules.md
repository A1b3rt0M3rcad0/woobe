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

## Enforced Quality Gate partition

The Agent architecture policy has narrow rules for Context Management:

- `ARCH082`: resolver is the explicit composition point;
- `ARCH083`: concrete Managers depend only on the Context Manager SDK, stable Application interfaces and Domain values;
- `ARCH084`: Manager Runtime bridges the SDK to the existing shared context assembly and Skill mechanics and cannot depend on concrete Managers.

The broad `ARCH004` infrastructure rule remains unchanged for all other infrastructure.
