# Architecture and mental model

An Execution Strategy is the algorithm that decides **how an Agent conducts Model and capability execution**.

A Strategy may decide when to invoke the Model, whether Tool calls should be executed, how many rounds should be allowed, when the algorithm should stop, and when progress should be checkpointed.

The Strategy should read like algorithm code, not infrastructure code.

## Dependency direction

```text
Concrete Strategy
      │
      ▼
StrategyContext
├── state
├── model
├── tools
└── checkpoint()
      │
      ▼
Strategy Runtime
├── conversation progression
├── State persistence
├── recovery
├── call indexes
├── instrumentation
└── runtime execution state
      │
      ▼
Execution Capabilities
├── Model invocation
└── Tool execution
```

The concrete Strategy owns algorithm decisions. The Strategy Runtime owns the mechanics required to execute those decisions safely and durably.

## What a Strategy owns

Typical Strategy responsibilities include:

```text
Model invocation order
Tool-use loop structure
algorithm-local counters
planning or reflection phases
per-invocation directives
stop conditions
checkpoint placement
final outcome selection
```

The current [`StandardExecutionStrategy`](../standard.py) is a Model/Tool loop. A future Planner or ReAct Strategy may use the same runtime primitives in a different order.

## Phase and Directive

A Phase and a Directive solve different problems.

```text
Phase       = stable semantic identity of an execution step
Directive   = ephemeral Model behavior instruction for one invocation
```

The Phase is structural. It is useful to the Strategy algorithm, instrumentation, traces and recovery semantics. A Directive is an optional instruction supplied by the Strategy to refine how the Model should operate during that invocation.

Example:

```python
result = await ctx.model.invoke(
    phase=ReasoningPhase.REFLECT,
    directive=(
        "Evaluate the evidence collected so far, identify contradictions "
        "and determine whether additional actions are required."
    ),
)
```

Directives are invocation-local. The Strategy Runtime materializes them only for the current Model call, routes them through Context Engineering, and never appends them to persistent conversation progression.

A Directive does not mutate or replace:

```text
Agent Behavior
Agent objective
Skills
Session state
persistent context
Release configuration
```

Dynamic business data, Tool results and other evidence should flow through normal context sources rather than being embedded in a Directive.

## What the Strategy Runtime already handles

A concrete Strategy must assume these concerns are already handled by `infra/execution/strategy_runtime`:

```text
Model/Tool conversation progression
call_index allocation
InstrumentedExecution mutation
Model instrumentation
Tool instrumentation
durable Tool evidence
checkpoint serialization
State serialization
State restoration
recovery message reconstruction
legacy recovery compatibility
provider/model preparation
per-invocation Directive materialization
final execution result materialization
```

Therefore this is normal Strategy code:

```python
result = await ctx.model.invoke(
    phase=MyPhase.REASONING,
)

batch = await ctx.tools.execute_many(
    result.tool_calls,
)

await ctx.checkpoint()
```

And this is also normal when the Phase requires a specific cognitive behavior:

```python
result = await ctx.model.invoke(
    phase=MyPhase.REFLECT,
    directive="Inspect the current evidence and identify unresolved gaps.",
)
```

The Strategy should not manually maintain message history, call indexes or recovery cursors.

## When the Strategy Runtime should change

Adding a normal Strategy should not require changes to:

```text
infra/execution/strategy_runtime/builder.py
infra/execution/strategy_runtime/context.py
infra/execution/strategy_runtime/model.py
infra/execution/strategy_runtime/tools.py
infra/execution/strategy_runtime/checkpoint.py
infra/execution/strategy_runtime/state.py
infra/execution/strategy_runtime/runtime_state.py
```

If a new algorithm appears to require changes there, classify the requirement first.

If the behavior is specific to one algorithm, keep it in the Strategy file. Examples include planning order, reflection loops, replan rules and algorithm-specific termination.

If several Strategies need the same capability and the current Strategy SDK cannot express it, a small shared primitive may belong in `strategy_sdk` and `strategy_runtime`. Per-invocation Directives are an example of such a shared primitive because multiple algorithms can require phase-specific Model behavior without changing Agent configuration.

The rule is:

> Do not expand the Strategy Runtime to make one Strategy more convenient when the behavior is actually algorithm-specific.
