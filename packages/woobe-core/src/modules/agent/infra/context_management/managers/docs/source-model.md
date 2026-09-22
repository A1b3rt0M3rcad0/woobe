# Source and transformation model

Context Manager decisions operate over typed context sources. Source type describes provenance/role, not a Python message class.

## Source taxonomy

| Source | Meaning | Produced by | Manager controls today |
| --- | --- | --- | --- |
| `SYSTEM` | canonical instructions and Tool definitions | execution/runtime | mandatory invariants |
| `USER_INPUT` | current direct user input | execution/runtime | mandatory invariants |
| `SESSION` | prior conversation messages | Session history | recent window, priority, dedup, order |
| `CHECKPOINT` | checkpoint-derived context | upstream runtime | cap, priority, dedup, order |
| `MEMORY` | memory contribution | memory system | cap, priority, dedup, order |
| `KNOWLEDGE` | RAG/knowledge contribution | retrieval runtime | cap, priority, dedup, order |
| `TOOL` | Tool result/receipt context | Tool runtime | cap, priority, dedup, order |
| `ARTIFACT` | file/document contribution | artifact system | cap, priority, dedup, order |
| `DELEGATION` | parent/network input | Network runtime | cap, priority, order |
| `RUNTIME` | runtime contextual data, including exposed External Context | runtime | priority/order with contract exception |
| `SKILL` | installed/activated Skill context | Skills runtime | optional materialization and policy budgets |

## Source production versus source selection

A Context Manager primarily owns **selection/materialization policy**, not production of every source.

- Knowledge retrieval ranking happens before Context assembly.
- Memory retrieval is a separate capability when available.
- Checkpoint creation belongs to execution/recovery.
- External Context exposure is authorized by the Agent contract.
- Skills activation/catalog logic belongs to Skills runtime.

The Manager decides how available contributions participate.

## Transformations

`ContextContribution.transformations` records modifications applied before the Model sees a contribution.

Current examples:

~~~text
session_budget_truncate
source_budget_truncate
global_budget_truncate
tool_output_compaction
~~~

Transformations must be observable. If Runtime changes the materialized representation, evidence should record what happened.

## Selection and exclusion evidence

The Context Snapshot manifest records candidate sources, selected sources, exclusions, exclusion reasons, ordering, deduplication, metrics, modalities and health.

Two Managers may produce different effective context while Runtime preserves the same evidence model.

## External Context exception

External Context explicitly exposed by the Agent contract is authorized by that narrow contract. Historical frozen policies may omit generic RUNTIME; that omission does not silently revoke the explicit exposure decision.

Runtime still applies safe structured compaction and budget enforcement.
