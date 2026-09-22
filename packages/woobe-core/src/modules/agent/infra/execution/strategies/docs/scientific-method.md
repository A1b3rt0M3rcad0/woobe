# Scientific Method Execution Strategy

`scientific_method` is Woobe's first built-in multi-phase Execution Strategy driven by per-invocation Directives.

Its purpose is not to make the Agent permanently "scientific". Agent Behavior, objective, Skills, Tools, Knowledge, Session state, and Release configuration remain unchanged. The Strategy only changes how one execution is orchestrated.

## Algorithm

The normal flow is:

```text
observation
    ↓
hypothesis_formulation
    ↓
experiment through Tool call
    ↓
evidence_analysis_N
    ↓
critical_review
    ├── material uncertainty remains → experiment → evidence_analysis_N → critical_review
    └── no material test remains → conclusion
```

A Tool call is treated as an experiment because it obtains evidence that was not already available to the Model. Tool results still use the normal runtime conversation progression and instrumentation; the Strategy does not create a second evidence store.

## Phase versus Directive

The Strategy is intentionally a concrete demonstration of the distinction introduced by the Directive primitive.

```text
Phase       = where the scientific algorithm currently is
Directive   = how the Model should operate during that one invocation
```

Examples:

- `observation` directs the Model to separate observations from assumptions and frame an investigable question;
- `hypothesis_formulation` directs it to create falsifiable competing explanations and identify discriminating evidence;
- `evidence_analysis_N` directs it to compare newly collected evidence against those hypotheses and request another minimal experiment only when needed;
- `critical_review` directs it to attempt falsification, search for contradictory evidence, and challenge the weakest inference;
- `conclusion` directs it to report only what the evidence supports and distinguish evidence, inference, and uncertainty.

Directives are materialized as system-controlled context for the current Model invocation and are never appended to persistent Strategy conversation state.

The Strategy also declares delivery semantics per invocation. Observation, hypothesis formulation, evidence analysis, and critical review use `StrategyOutputMode.INTERNAL`, while `conclusion` uses `StrategyOutputMode.FINAL`. The runtime therefore does not need to recognize the name `conclusion`. A future Strategy can use `StrategyOutputMode.INTERMEDIATE` to emit a durable Assistant message, continue with Tools or more Model calls, and later produce its final response.

## State

The Strategy State contains only durable algorithm information:

```text
phase
experiment_round
after_evidence_phase
stop_reason
```

It does not store messages, hypotheses, Tool payloads, Model output, Directives, call indexes, or recovery cursors.

`after_evidence_phase` exists because evidence may be collected from different points in the algorithm. For example, evidence requested while framing observations should return to hypothesis formulation after analysis, while evidence requested during critical review should return to critical review.

## Experiment policy

The default policy permits five completed Tool-backed experiment rounds.

The limit is checked before executing a new Tool request. Therefore the fifth completed experiment can still be analyzed; only a request for a sixth experiment is rejected.

When the limit is reached, the Strategy uses `ctx.model.finalize()` with a conservative Directive that forbids further Tools and requires the result to expose unresolved uncertainty rather than pretending the investigation completed normally.

## Critical review can reopen investigation

Critical review is not a cosmetic final prompt.

If the Model identifies a material falsifiable gap and requests a Tool, the Strategy executes that Tool, checkpoints the result, enters the next `evidence_analysis_N` phase, and then returns to critical review.

This creates a real feedback loop rather than a fixed linear chain.

## Checkpoint and recovery

Every completed Tool-backed experiment is followed by a Tool-boundary checkpoint.

A recovery after experiment 1 restores a State equivalent to:

```text
phase = evidence_analysis_1
experiment_round = 1
after_evidence_phase = critical_review
```

The Strategy Runtime restores the durable conversation evidence and call indexes. The concrete Strategy simply sees its restored State, derives the evidence-analysis Directive, and continues. The completed Tool call is not replayed.

## Why this matters for future Strategies

Scientific Method does not add Scientific-Method-specific branches to `strategy_runtime`. It uses the generic `output_mode` primitive in the Strategy Model contract, which also supports intermediate Assistant messages for future multi-phase Strategies.

That demonstrates the intended extension model:

```text
new algorithm
    → new concrete Strategy file
    → local phases
    → local State
    → optional local Policy
    → phase-specific Directives
    → explicit output delivery mode
    → existing Model / Tool / checkpoint primitives
```

A Planner, verifier, reflection loop, debate algorithm, or another future execution style should first attempt to fit this model. A new shared SDK/runtime primitive is justified only when multiple independent Strategies expose the same missing capability.

## Standard versus Scientific Method

`standard` is the general-purpose default and minimizes orchestration overhead. It lets Model-directed capability use drive the loop.

`scientific_method` intentionally spends additional Model invocations to make observation, hypothesis formation, evidence testing, falsification, and conclusion explicit.

Neither Strategy changes Agent identity or configuration. They are alternative execution algorithms operating on the same Agent snapshot.
