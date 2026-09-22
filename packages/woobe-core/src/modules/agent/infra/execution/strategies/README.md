# Agent Execution Strategies

An Execution Strategy defines **how an Agent carries out an execution**.

From the outside, an Agent receives an input and eventually produces an output. Between those two points, the Agent may need to call a Model once, use Tools, continue for several rounds, stop because a limit was reached, or follow a different reasoning pattern.

An Execution Strategy is the part of Woobe that defines that behavior.

Woobe currently ships two built-in examples of this boundary. `standard` is the general-purpose Model/Tool loop. `scientific_method` is a hypothesis-driven multi-phase algorithm that uses per-invocation Directives for observation, hypothesis formulation, evidence analysis, falsification, and conclusion without changing the shared Strategy Runtime.

The convention is intentionally simple:

```text
one Strategy = one Python file
```

```text
strategies/
├── README.md
├── resolver.py
├── standard.py
├── planner.py
├── react.py
└── reflection.py
```

`standard.py` is the minimal reference implementation. `scientific_method.py` is the advanced reference showing how a Strategy can define a substantially different algorithm with multiple phases, durable experiment checkpoints, and phase-specific Directives while using the same Strategy SDK and Runtime.

## Creating a new Execution Strategy

This README is only an introduction to the concept.

If you are going to build a new Execution Strategy, start with the documentation index:

**[Execution Strategy documentation →](./docs/README.md)**

The documentation explains what to create, where each piece belongs, how State and Policy should be used, how to register the Strategy, which tests are required, and which architecture boundaries must not be crossed. The existing [`standard.py`](./standard.py) implementation is used throughout the guide as the canonical example.
