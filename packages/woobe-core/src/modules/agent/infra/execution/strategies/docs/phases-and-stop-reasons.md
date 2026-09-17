# Phases and stop reasons

The concepts of execution phase and stop reason are shared across Strategies, but their concrete values belong to each algorithm.

Use the shared bases:

```python
class MyPhase(ExecutionPhase):
    ...

class MyStopReason(ExecutionStopReason):
    ...
```

## Standard phases

The Standard implementation currently defines:

```python
class StandardPhase(ExecutionPhase):
    RESPONSE_GENERATION = "response_generation"
    CAPABILITY_RESPONSE_GENERATION = "capability_response_generation"
    TOOL_FOLLOWUP = "tool_followup"
    FINAL_RESPONSE_GENERATION = "final_response_generation"
```

These values describe Standard-specific algorithm stages.

A Planner may instead need phases such as:

```text
planning
step_execution
replanning
synthesis
```

A ReAct Strategy may use another vocabulary.

Do not create one global enum containing every future Strategy phase. The shared SDK owns the concept; each Strategy owns its semantic values.

## Standard stop reasons

The Standard implementation defines:

```python
class StandardStopReason(ExecutionStopReason):
    REPEATED_SEMANTIC_FAILURES = "repeated semantic capability failures"
    CAPABILITY_ROUND_LIMIT = "capability round limit reached"
    PROVIDER_REJECTED_FOLLOWUP = (
        "the capability follow-up request was rejected by the provider"
    )
```

Future Strategies should define only the stop reasons meaningful to their own algorithm.

## Iterated phase labels

When an existing observability or recovery contract requires an iteration number in the phase label, use the shared helper:

```python
strategy_phase_with_iteration(
    MyPhase.STEP,
    iteration,
)
```

The Standard Strategy currently uses it for Tool follow-up phases such as:

```text
tool_followup_1
tool_followup_2
```

Do not invent incompatible string-building conventions when the shared helper already expresses the same requirement.
