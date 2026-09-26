# Architecture rules

Concrete Execution Strategies are intentionally constrained so algorithm code stays independent from runtime infrastructure.

## One file per Strategy

The required convention is:

```text
strategies/
├── standard.py
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
ctx.bootstrap
ctx.conversation
ctx.knowledge
ctx.context
ctx.model
ctx.tools
ctx.output
ctx.checkpoint()
```

## No Strategy-to-Strategy imports

Concrete Strategies must not import one another.

If two Strategies need the same stable concept, evaluate whether that concept belongs in the shared Strategy SDK. Do not create hidden inheritance or utility coupling between concrete algorithms.

## Execution ownership boundary

The outer runner is not a second orchestrator.

Before `ExecutionStrategy.execute(ctx)`, Runtime may resolve, authorize, freeze and restore dependencies/state. After the Strategy returns, Runtime may persist and project terminal evidence. Between those boundaries, only the Strategy may decide to start semantic execution operations.

Forbidden outer-runtime decisions include:

```text
preflight Tool execution
conversation-to-Knowledge query construction
Knowledge retrieval
Context Manager invocation outside the Execution Strategy boundary
Model invocation
provider fallback
structured-output repair
new semantic checkpoints
```

Capabilities own mechanisms; the Execution Strategy decides when to request Context operations; the selected Context Manager decides how Context is inspected, compacted and assembled.

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
