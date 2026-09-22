# Architecture rules

Concrete Execution Strategies are intentionally constrained so algorithm code stays independent from runtime infrastructure.

## One file per Strategy

The required convention is:

```text
strategies/
├── standard.py
├── scientific_method.py
├── planner.py
├── react.py
└── reflection.py
```

Do not create nested Strategy packages.

The architecture tests automatically reject Python files under nested Strategy directories.

## Allowed dependencies

A concrete Strategy may depend on:

```text
Python standard library
modules.agent.application.strategy_sdk
stable modules.agent.application.interfaces contracts
```

Only import the contracts required by the algorithm.

## Forbidden dependencies

A concrete Strategy must not directly depend on:

```text
infra/execution/capabilities
infra/execution/strategy_runtime
persistence/database code
Network implementation
LangChain
provider SDKs
Redis
MongoDB
SQLAlchemy
runtime streaming internals
workers
presentation
composition
```

The Strategy must use `StrategyContext` rather than bypassing the runtime facade.

## No private runtime access

Do not access private `StrategyContext` fields or concrete runtime implementation details.

The public algorithm-facing surface should remain approximately:

```text
ctx.state
ctx.model
ctx.tools
ctx.checkpoint()
```

## Phase-specific Directives stay narrow

A Strategy may provide an optional Directive when invoking the Model:

```python
await ctx.model.invoke(
    phase=MyPhase.REFLECT,
    directive="Evaluate the current evidence and identify unresolved gaps.",
)
```

The Directive defines invocation-local execution behavior. It must not be treated as a second Agent prompt or as a general context transport.

Do not use a Directive to:

```text
replace Agent objective or Behavior
bypass allowed/disallowed behavior constraints
rewrite Skill semantics
persist instructions into Session history
carry large Tool results or business payloads
smuggle runtime infrastructure state into the Model
```

If information is part of the task or evidence, use the normal context pipeline. If behavior is persistent Agent configuration, place it in Agent Behavior or the relevant Skill. Directives are only for behavior required by the current execution Phase.

## No Strategy-to-Strategy imports

Concrete Strategies must not import one another.

If two Strategies need the same stable concept, evaluate whether that concept belongs in the shared Strategy SDK. Do not create hidden inheritance or utility coupling between concrete algorithms.

## State boundary

Concrete State contains algorithm data only.

Architecture tests reject infrastructure-shaped methods such as:

```text
create
checkpoint_cursor
checkpoint_messages
record_model_result
record_tool_batch
```

and old recovery-facing symbols such as:

```text
StrategyInitialization
StrategyResumeSnapshot
```

Recovery, checkpoint serialization and message progression belong to Strategy Runtime.

A Directive normally does not belong in State. It should be derived by the Strategy from the current Phase and algorithm state when the Model is invoked. Persist the data that determines the next Phase, not the temporary prompt overlay itself.

## Composition points

Concrete Strategy classes are composed through `strategies/resolver.py`.

The product-facing catalog is maintained separately in `application/execution_strategy_registry.py`.

Application metadata must not import concrete infrastructure Strategy classes.

## Quality Gate

The repository architecture policy contains explicit Strategy rules, including the flat one-file convention and import boundaries.

Relevant tests:

```text
tests/architecture/test_execution_strategy_boundary.py
tests/architecture/execution_strategy/test_strategy_import_quality_gate.py
```

If a new Strategy cannot satisfy these rules, do not add a local exception first. Re-evaluate whether the implementation is placing algorithm behavior in the wrong layer or whether a genuinely shared platform primitive is missing.


## Advanced Strategy example

`scientific_method.py` is intentionally implemented without imports from `strategy_runtime`, provider frameworks, persistence, or `standard.py`. Its phase machine, experiment counter, stop policy, and Directive selection are algorithm concerns and therefore remain in the concrete Strategy.

If a future Strategy needs planning, verification, debate, reflection, search, or another multi-step pattern, prefer the same approach: express the behavior with local phases, State, Policy, Directives, Tool decisions, and checkpoints before proposing a new shared runtime primitive.
