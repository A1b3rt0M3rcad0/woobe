---
name: projectrai-spec-orchestrator
description: Execute ProjectRAI agent migration specs in strict numeric order, enforce prerequisites, update specs/execution/runtime.md, and stop safely on blockers.
license: MIT
compatibility: opencode
metadata:
  project: ProjectRAI
  phase: orchestration
  scope: specs-runtime
---

# ProjectRAI Spec Orchestrator

Use this skill when the user asks OpenCode to execute, continue, plan, resume, audit, or repair the ProjectRAI `agent` migration specs under `/specs`.

This skill is the top-level controller. It does not replace the individual specs. It forces the agent to treat `/specs/execution/runtime.md`, `/specs/MANIFEST.md`, and the current numbered spec as the source of truth.

## Operating contract

The migration consolidates `src/modules/ai`, `src/modules/knowledge`, and `src/modules/runtime` into `src/modules/agent` while preserving a modular monolith. Do not create microservices. Do not keep `ai`, `knowledge`, and `runtime` as independent final modules. Do not alter business behavior outside the active spec.

Execute exactly one numbered spec at a time unless the user explicitly asks for a planning-only batch. Never skip ahead because a later spec looks easier. Never remove legacy modules before the deprecation/removal specs. Never move physical files before the discovery specs `003` through `009` and the initial architecture test specs `015` through `019` are completed or explicitly marked with a justified blocker.

## Required start sequence

Before changing code, read these files in this order:

1. `/specs/execution/runtime.md`
2. `/specs/MANIFEST.md`
3. `/specs/README.md`
4. The current target spec, usually the first `pending` spec in `runtime.md`
5. Any dependency specs listed by the target spec or manifest

Then run detection commands from the target spec, adapting only when a tool is absent. Record absent tools as runtime pendencies instead of inventing success.

## Spec execution loop

For each active spec:

1. Confirm the spec id, title, type, prerequisites, allowed changes, prohibited changes, contracts, mandatory tests, validation commands, acceptance criteria, rollback notes, and runtime update requirements.
2. Check `git status --short`. If the worktree is dirty, continue only when the changes are clearly part of the active migration; otherwise report the conflict and do not mix unrelated edits.
3. Execute the spec's discovery/detection commands first. Do not write code before observing current repository state.
4. Implement the smallest patch that satisfies the active spec only.
5. Add or update tests required by the spec. Architecture tests are mandatory when the spec requires them.
6. Run confirmed validation commands. Standard commands are typically `ruff check src tests`, `pytest`, `pytest tests/architecture`, `alembic upgrade head`, and `alembic downgrade -1`; run only commands that exist in the project or are confirmed by the inventory.
7. Update `/specs/execution/runtime.md` with the spec status, files changed, validations, blockers, risks, inconsistencies, and next recommended spec.
8. Stop after the spec is completed or blocked. Provide a concise execution report.

## Runtime update requirements

Every completed, blocked, or skipped spec must update these runtime sections when present:

- `Estado atual da migração`
- `Status das specs`
- `Specs executadas`
- `Decisões tomadas durante a execução`
- `Riscos ativos`
- `Inconsistências encontradas`
- `Próxima spec recomendada`

Do not mark a spec as `completed` if required validations were not run and no explicit inventory-based reason is recorded.

## Blocker policy

Block instead of forcing a bad migration when any of these occur:

- Required inventory is missing for a destructive or physical move.
- A prerequisite spec is still `pending` and the active spec depends on it.
- Validation tools are missing and the spec requires their existence to prove safety.
- The patch would import internals from another module.
- The patch would create cross-module Unit of Work, cross-module Foreign Keys, direct synchronous state-changing calls between modules, or domain logic in `shared`.
- The patch would remove legacy `ai`, `knowledge`, or `runtime` before specs `140` through `145`.

When blocked, update `runtime.md` with the exact blocker, current evidence, files touched, and recommended next action.

## Output format for OpenCode responses

After execution, report:

- Active spec id and file.
- Final status: `completed`, `blocked`, or `skipped`.
- Files changed.
- Validations run with exit codes.
- Runtime updates made.
- Next recommended spec.
- Any blocker or residual risk.

Do not write generic summaries. Tie every claim to files, commands, and spec ids.
