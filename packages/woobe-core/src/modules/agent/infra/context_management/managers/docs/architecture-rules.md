# Architecture rules

Concrete Context Managers are algorithm code.

## Allowed dependency surface

A normal Manager may depend on:

~~~text
modules.agent.application.context_manager_sdk
stable Application interfaces required by that SDK
modules.agent.domain enums/value types
sibling Manager modules only for explicit composition
~~~

## Forbidden concerns

Concrete Managers must not depend directly on:

~~~text
ContextAssemblyRequest
manager_runtime implementation
LangChain message classes
provider SDKs
ContextSnapshot constructors
ContextContribution constructors
hash/provenance mechanics
database repositories
Redis/Mongo/PostgreSQL clients
provider factories
execution lifecycle
Network infrastructure
API/worker packages
~~~

## Primitive rule

If one Manager needs algorithm-specific behavior, keep it in that Manager.

If multiple Managers need the same operation and Runtime can give it precise reusable semantics, introduce a small SDK + Runtime primitive.

If the operation needs I/O, durability, instrumentation or provider behavior, it belongs to Runtime and must have an explicit execution boundary.

Do not create a primitive merely because a field exists in `ContextPolicyV1`. A field whose runtime semantics are incomplete should remain documented as incomplete.

## One-file convention

~~~text
infra/context_management/managers/adaptive.py
~~~

A normal Manager must not grow a parallel private runtime package.

## Enforced Quality Gate partition

- `ARCH082`: resolver is the explicit composition point;
- `ARCH083`: flat concrete Managers depend only on SDK/stable application/domain surfaces;
- `ARCH084`: Manager Runtime bridges SDK to shared assembly mechanics and cannot depend on concrete Managers.
