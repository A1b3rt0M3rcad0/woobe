# Testing and validation

A new Execution Strategy must prove two things:

1. its algorithm behaves correctly;
2. it integrates through the generic Strategy Runtime without introducing Strategy-specific runtime plumbing.

## Behavior tests

Add focused unit tests under:

```text
tests/unit/agent/
```

Test the decisions that make the Strategy different.

For example, Scientific Method tests cover observation → hypothesis → experiment → evidence analysis → critical review → conclusion, phase-specific Directives, investigation reopening from critical review, and deterministic experiment limits. A Planner should test planning, step progression, replanning limits and final synthesis. A ReAct Strategy should test iteration and Tool/observation progression.

Do not duplicate generic runtime tests unless the Strategy depends on a specific behavior that must be preserved.

## Recovery tests

If the Strategy checkpoints durable progress, simulate a process interruption after a checkpoint and verify that resume:

```text
restores algorithm State
restores conversation progression
preserves execution evidence
does not replay completed Tool side effects
continues with the correct next Model call
```

The Standard reference is:

```text
tests/unit/agent/test_execution_strategy_standard_recovery.py
```

## Extensibility test

The generic non-Standard example is:

```text
tests/unit/agent/test_execution_strategy_extensibility.py
```

It proves that another algorithm can use `ExecutionState`, `StrategyContext`, Model, Tools and checkpointing without importing runtime capabilities directly.

## Catalog and resolver parity

Relevant test:

```text
tests/unit/agent/test_execution_strategy_catalog.py
```

The Strategy name in the product catalog and runtime resolver must match exactly.

## Architecture gates

All flat concrete Strategy files are automatically covered by:

```text
tests/architecture/test_execution_strategy_boundary.py
tests/architecture/execution_strategy/test_strategy_import_quality_gate.py
```

Do not add per-Strategy architecture exceptions unless there is a justified platform-level reason.

## Definition of Done

Before considering a new built-in Execution Strategy complete, verify:

- [ ] exactly one concrete Strategy file was added under `infra/execution/strategies/`;
- [ ] no Strategy-specific package/folder was created;
- [ ] `name` is stable, lowercase and unversioned;
- [ ] `state_type` points to the concrete State;
- [ ] State contains algorithm data only;
- [ ] State is default-constructible and serializable;
- [ ] Policy exists only if the algorithm has real stop rules or limits;
- [ ] Model calls use `ctx.model`;
- [ ] Tool calls use `ctx.tools`;
- [ ] durable boundaries use `ctx.checkpoint()`;
- [ ] the Strategy returns a supported `StrategyOutcome`;
- [ ] no recovery serialization or message progression logic exists in the concrete Strategy;
- [ ] runtime implementation is registered in `strategies/resolver.py`;
- [ ] product metadata is registered in `execution_strategy_registry.py`;
- [ ] resolver and catalog names are in parity;
- [ ] behavior tests cover algorithm-specific decisions;
- [ ] recovery tests exist when durable checkpoints are used;
- [ ] architecture gates pass;
- [ ] relevant backend tests pass.

## Focused validation

Useful focused commands from the repository root include:

```bash
uv run pytest -q \
  tests/unit/agent/test_execution_strategy_catalog.py \
  tests/unit/agent/test_execution_strategy_extensibility.py \
  tests/architecture/test_execution_strategy_boundary.py \
  tests/architecture/execution_strategy/test_strategy_import_quality_gate.py
```

Add the concrete Strategy's own unit and recovery tests to the command.

Do not claim CI, typecheck, build or test success unless it was actually executed.


## Scientific Method reference tests

The Scientific Method adds both focused algorithm tests and a runtime recovery test.

The behavior test verifies that:

- each semantic phase receives the expected Directive;
- Tool requests become experiment rounds;
- evidence analysis receives the completed round number;
- critical review can request another experiment and reopen investigation;
- the experiment limit stops before an extra Tool side effect is executed;
- conservative finalization is used when investigation is stopped by policy.

The recovery test crashes immediately after a durable experiment checkpoint. Resume must restore `evidence_analysis_1`, preserve the Tool evidence, avoid replaying the experiment, materialize the evidence-analysis Directive again, and continue through critical review and conclusion.

This is the preferred test pattern for future Strategies with durable side effects.
