# Architecture and mental model

An Execution Strategy is the algorithm that decides **how an Agent conducts Model and capability execution**.

A Strategy may decide when to retrieve Knowledge, how Knowledge contributes to Context, which authorized Tools are visible to each Model invocation, when to invoke the Model, whether Tool calls should be executed, how many rounds should be allowed, when the algorithm should stop, and when progress should be checkpointed.

The Strategy should read like algorithm code, not infrastructure code.

## Dependency direction

```text
Concrete Strategy
      │
      ▼
StrategyContext
├── state
├── knowledge
├── context
├── model
├── tools
└── checkpoint()
      │
      ▼
Strategy Runtime
├── Knowledge facade
├── Context contribution state
├── conversation progression
├── State persistence
├── recovery
├── call indexes
├── instrumentation
└── runtime execution state
      │
      ▼
Execution Capabilities
├── Knowledge retrieval
├── Context assembly
├── Model invocation
└── Tool execution
```

The concrete Strategy owns algorithm decisions. The Strategy Runtime owns the mechanics required to execute those decisions safely and durably.

## What a Strategy owns

Typical Strategy responsibilities include:

```text
Knowledge retrieval timing and query choice
Context contribution lifecycle
per-invocation Tool selection
Model invocation order
Tool-use loop structure
algorithm-local counters
planning or reflection phases
stop conditions
checkpoint placement
final outcome selection
```

The current [`StandardExecutionStrategy`](../standard.py) is a Model/Tool loop. A future Planner or ReAct Strategy may use the same runtime primitives in a different order.

## What the Strategy Runtime already handles

A concrete Strategy must assume these concerns are already handled by `infra/execution/strategy_runtime`:

```text
Knowledge implementation binding
Context Manager implementation binding
Tool authorization
Model/Tool conversation progression
call_index allocation
InstrumentedExecution mutation
Knowledge/Model/Tool instrumentation
durable Tool evidence
checkpoint serialization
State serialization
State restoration
Context contribution restoration
recovery message reconstruction
legacy recovery compatibility
provider/model preparation
final execution result materialization
```

Therefore this is normal Strategy code:

```python
knowledge = await ctx.knowledge.retrieve(
    phase="knowledge_retrieval",
)
if knowledge.found:
    ctx.context.set(
        StrategyContextContribution(
            key="knowledge.primary",
            source_type="KNOWLEDGE",
            content=knowledge.content,
        )
    )

tools = ctx.tools.select("search")
invocation = await ctx.context.assemble(
    phase=MyPhase.REASONING,
    tools=tools,
)
result = await ctx.model.invoke(
    context=invocation,
    tools=tools,
    phase=MyPhase.REASONING,
)

if result.has_tool_calls:
    await ctx.tools.execute_many(result.tool_calls)
    await ctx.checkpoint()
```

The Context → Model boundary is explicit: `ctx.model.invoke(...)` never silently assembles Context. The Strategy should not manually maintain message history, call indexes, authorization state or recovery cursors.

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

If several Strategies need the same capability and the current Strategy SDK cannot express it, a small shared primitive may belong in `strategy_sdk` and `strategy_runtime`.

The rule is:

> Do not expand the Strategy Runtime to make one Strategy more convenient when the behavior is actually algorithm-specific.


## Core invariants

The runtime resolves and freezes concrete dependencies; the Strategy orchestrates them through the stable SDK.

- Knowledge retrieval and Knowledge inclusion in Context are separate decisions.
- Context is assembled for one Model invocation, not globally for an execution.
- Tool authorization belongs to the runtime; Tool selection belongs to the Strategy.
- Model invocation receives an already assembled `StrategyInvocationContext`.
- Terminal responses use `ctx.context.assemble_final(...)` before `ctx.model.finalize(...)`.
- Concrete Strategies do not import infrastructure adapters or mutate `InstrumentedExecution` directly.
