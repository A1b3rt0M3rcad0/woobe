# Execution Policy

`ExecutionPolicy` is optional.

Use a Policy when a Strategy has deterministic limits or stop rules that should remain separate from the orchestration flow.

## Standard reference

The Standard Strategy uses Policy for two limits:

```python
@dataclass(frozen=True, slots=True)
class StandardExecutionPolicy(
    ExecutionPolicy[StandardExecutionState]
):
    max_tool_rounds: int = 5
    max_consecutive_failures: int = 2

    def stop_reason(
        self,
        state: StandardExecutionState,
    ) -> StandardStopReason | None:
        if state.consecutive_failures >= self.max_consecutive_failures:
            return StandardStopReason.REPEATED_SEMANTIC_FAILURES

        if state.tool_round >= self.max_tool_rounds:
            return StandardStopReason.CAPABILITY_ROUND_LIMIT

        return None
```

The Strategy then asks a narrow question:

```python
state.stop_reason = self.policy.stop_reason(state)
```

## Good Policy responsibilities

Examples include:

```text
maximum Tool rounds
maximum ReAct iterations
maximum replans
maximum reflection rounds
maximum consecutive semantic failures
```

A Policy should normally inspect algorithm State and return a deterministic decision such as a stop reason or `None`.

## What Policy should not own

Do not put these concerns in Policy:

```text
Model invocation
Tool execution
checkpoint persistence
Run status transitions
provider calls
message progression
recovery serialization
arbitrary orchestration
```

Those belong either to the Strategy algorithm or the Strategy Runtime.

## When not to create Policy

If the Strategy has no meaningful configurable limits or deterministic stop rules, omit the Policy class.

Do not create Policy only to make `execute()` shorter. The goal is a clear algorithm boundary, not maximum class count.
