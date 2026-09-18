# SDK primitives

The stable Manager-facing surface is:

```text
ctx.policy
ctx.candidates
ctx.budget
ctx.sources
ctx.has_active_skills
ctx.complete()
```

## candidates

`ctx.candidates` controls candidate-selection policy:

- `allow(...)`
- `recent_session(...)`
- `cap(...)`
- `require(...)`
- `deduplicate(...)`
- `order(...)`

These operations never construct a Context Snapshot directly.

## budget

`ctx.budget` controls configured input limits and pressure thresholds.

The Runtime still clamps the result against actual model capacity, reserved output and runtime reserve. A Manager cannot bypass those invariants.

## sources

`ctx.sources` enables optional runtime-owned materialization.

Current shared capability:

```python
ctx.sources.skills()
```

Skills materialization, budget validation, contribution metadata and retention manifest are implemented once by the Runtime.

## complete

`ctx.complete()` freezes the algorithm decisions for the current invocation into a `ContextManagerOutcome`.

The outcome is then finalized by `ContextManagerRunner`.
