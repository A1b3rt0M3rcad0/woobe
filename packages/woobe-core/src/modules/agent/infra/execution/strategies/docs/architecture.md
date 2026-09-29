# Architecture and mental model

An Execution Strategy is the algorithm that decides **how an Agent conducts Model and capability execution**.

A Strategy may decide when to retrieve Knowledge, how Knowledge contributes to Context, whether a Model invocation receives all authorized Tools or no Tools, when to invoke the Model, whether Tool calls should be executed, how many rounds should be allowed, when the algorithm should stop, and when progress should be checkpointed.

The Strategy should read like algorithm code, not infrastructure code.

## Dependency direction

```text
Concrete Strategy
      │
      ▼
StrategyContext
├── state
├── bootstrap
├── conversation
│   ├── current_user_message
│   ├── history
│   ├── system_messages
│   └── messages
├── knowledge
├── context
│   ├── inspect()
│   ├── compact()
│   └── assemble()
├── model
│   ├── invoke()
│   ├── invoke_fallback()
│   └── finalize()
├── tools
├── output
└── checkpoint()
      │
      ▼
Strategy Runtime
├── Knowledge facade
├── selected Knowledge Strategy
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
├── Knowledge mechanisms
├── Context assembly
├── Model invocation
└── Tool execution
```

The concrete Strategy owns algorithm decisions. The Strategy Runtime owns the mechanics required to execute those decisions safely and durably.

The governing rule is:

> **Runtime owns guarantees. Capabilities own mechanisms. ExecutionStrategy owns decisions.**

The runner may build/freeze bindings before `execute(ctx)` and perform terminal bookkeeping after it returns, but it must not execute Model, Tool, Knowledge, Context, fallback or output-repair capabilities around that boundary.

## What a Strategy owns

Typical Strategy responsibilities include:

```text
bootstrap/preflight execution decisions
read-only conversation inspection
Knowledge retrieval timing and input conversation
Context inspection, compaction requests and Knowledge inclusion
per-invocation Tool enable/disable decision
Model invocation and fallback order
Tool-use loop structure
structured-output repair decisions
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
Knowledge Strategy + mechanism binding
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
fallback Model binding
output repair mechanism binding
final execution result materialization
```

Therefore this is normal Strategy code:

```python
knowledge = await ctx.knowledge.retrieve(
    conversation=ctx.conversation,
    phase="knowledge_retrieval",
)
if knowledge.found:
    ctx.context.include_knowledge(knowledge)

tools = ctx.tools.all()
invocation = await ctx.context.prepare(
    phase=MyPhase.REASONING,
    tools=tools,
)
result = await ctx.model.invoke(invocation)

if result.has_tool_calls:
    await ctx.tools.execute_many(result.tool_calls)
    await ctx.checkpoint()
```

The Context → Model boundary is explicit: `ctx.model.invoke(...)` never silently assembles Context. Fallback and structured-output repair are also explicit Strategy decisions. `ctx.context.compact(...)` asks the configured Context Manager to manage pressure; the manager decides whether that means summarization, trimming, replacement or no-op. The Strategy never implements the compaction algorithm itself. The Strategy should not manually maintain message history, call indexes, authorization state or recovery cursors.

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

- Runtime freezes the execution conversation; Strategies inspect it through `ctx.conversation` without mutating runtime message state.
- Conversation-to-Knowledge query construction belongs to the selected Knowledge Strategy; Execution supplies the conversation without interpreting query mode, history limits or backend retrieval details.
- Knowledge capabilities expose mechanisms only. They do not own query policy or a concrete Knowledge algorithm.
- The built-in `rag` Knowledge Strategy may delegate an already-final query to a nested RAG Strategy such as `classic`; RAG selection is independent from Execution Strategy selection.
- Knowledge retrieval and Knowledge inclusion in Context are separate decisions.
- Context is assembled for one Model invocation, not globally for an execution.
- Tool authorization and the complete Tool inventory belong to the Runtime. The Strategy may only enable all authorized Tools or disable Tools for an invocation; it cannot select a subset.
- Model invocation receives an already assembled `StrategyInvocationContext`.
- Terminal responses use `ctx.context.assemble_final(...)` before `ctx.model.finalize(...)`.
- Fallback Context is assembled only when the Strategy selects `StrategyContextTarget.FALLBACK`, and fallback executes only when it calls `ctx.model.invoke_fallback(...)`.
- Structured-output repair executes only when a Strategy calls `ctx.output.repair(...)`.
- Context compaction begins only when a Strategy calls `ctx.context.compact(...)`; the configured Context Manager owns the compaction algorithm and may use model-assisted summarization through runtime-provided capabilities.
- After a Strategy returns `Completed`, the runner may not start another execution capability.
- Concrete Strategies do not import infrastructure adapters or mutate `InstrumentedExecution` directly.

Execution cannot manipulate Context storage through `has`, `set` or `remove`. Contribution storage, replacement and materialization remain internal to Context management. `inspect()` is a read-only view.
