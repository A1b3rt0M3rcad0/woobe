# Suspension and current limitations

The Strategy SDK can currently represent a suspended algorithm outcome:

```python
Suspended(...)
```

This is useful as a contract boundary for future durable asynchronous execution.

However, the outer Agent Run lifecycle does not yet provide the complete production flow:

```text
RUNNING
   ↓
WAITING
   ↓
external completion / approval
   ↓
RESUME
   ↓
RUNNING
```

The current outer runner still rejects suspended outcomes because the corresponding `WAITING -> RESUME` lifecycle is not enabled end to end.

## What this means for new Strategies

Do not design a new built-in Strategy that requires suspension to function correctly until the outer lifecycle is implemented.

A Strategy may be designed so future suspension support can fit naturally, but it should not depend on unsupported runtime behavior.

## Future examples

This contract is expected to become relevant for cases such as:

```text
ASYNC_AWAIT Tool operations
Human Approval
external event waits
long-running capability completion
```

When those flows are implemented, the lifecycle and recovery behavior should remain runtime-owned. Concrete Strategies should still express only the algorithm decision to suspend and the information required to continue.
