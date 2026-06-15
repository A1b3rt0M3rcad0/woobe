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

Use this skill when the user asks OpenCode to execute, continue, plan, resume, audit, or repair a ProjectRAI spec suite under `/specs/{spec_suite}`.

A **spec suite** is an isolated orchestration unit that contains its own manifest, runtime, instructions, and ordered implementation specs.

`{spec_suite}` is the directory identifier of the suite selected for execution. It is not the individual numbered spec currently being executed.

This skill is the top-level controller. It does not replace the individual specs. It forces the agent to treat `/specs/{spec_suite}/execution/runtime.md`, `/specs/{spec_suite}/MANIFEST.md`, `/specs/{spec_suite}/README.md`, and the current numbered spec inside the selected suite as the source of truth.

## Operating contract

Execute the specs contained in `/specs/{spec_suite}` according to the requirements, ordering, dependencies, contracts, validations, and acceptance criteria declared by that suite.

Do not introduce requirements, architectural decisions, implementation constraints, validation commands, or acceptance criteria that are not declared by the active suite or its current numbered spec.

Do not read or update execution files belonging to another spec suite.

Execute exactly one numbered spec at a time unless the user explicitly asks to execute the complete suite or requests a planning-only batch.

Never skip ahead because a later spec looks easier.

Never execute a spec whose prerequisites are incomplete.

Never perform changes reserved for a later spec unless the current spec explicitly requires them.

Do not alter behavior or files outside the scope permitted by the current numbered spec.

## Required start sequence

Before changing code, read these files in this order:

1. `/specs/{spec_suite}/execution/runtime.md`
2. `/specs/{spec_suite}/MANIFEST.md`
3. `/specs/{spec_suite}/README.md`
4. The current target spec inside `/specs/{spec_suite}`, usually the first eligible `pending` spec in `runtime.md`
5. Any dependency specs listed by the target spec or manifest

Confirm that `/specs/{spec_suite}` exists and that the suite contains enough information to determine the current target spec.

Then run detection or discovery commands from the target spec, adapting only when a declared tool is absent and a confirmed equivalent exists.

Record absent tools, unavailable commands, and command adaptations as runtime pendencies instead of inventing success.

## Spec execution loop

For each current numbered spec:

1. Confirm the spec id, title, type, file or directory, prerequisites, allowed changes, prohibited changes, contracts, mandatory tests, validation commands, acceptance criteria, rollback notes, and runtime update requirements.
2. Check `git status --short`. If the worktree is dirty, continue only when the changes are clearly part of the active suite execution; otherwise report the conflict and do not mix unrelated edits.
3. Execute the spec's discovery or detection commands first. Do not write code before observing the current repository state.
4. Implement the smallest patch that satisfies the current spec only.
5. Add or update tests required by the spec.
6. Run the validation commands declared by the current spec or confirmed by the suite inventory. Run only commands that exist in the project or whose availability was confirmed during discovery.
7. Update `/specs/{spec_suite}/execution/runtime.md` with the spec status, files changed, validations, blockers, risks, inconsistencies, and next recommended spec.
8. Stop after the spec is completed, blocked, or skipped, unless the user explicitly requested execution of the complete suite.
9. Provide a concise execution report.

When executing the complete suite, repeat this loop in the order defined by the manifest and runtime until:

* All required specs reach a valid terminal status.
* A blocker prevents safe continuation.
* A failed validation prevents the next spec from starting.
* The suite explicitly requires a manual stop.

Do not continue into specs that depend on a blocked or failed spec.

## Runtime update requirements

Every completed, blocked, or skipped spec must update the applicable sections of:

```text
/specs/{spec_suite}/execution/runtime.md
```

Update these runtime sections when present:

* `Estado atual`
* `Status das specs`
* `Specs executadas`
* `Decisões tomadas durante a execução`
* `Riscos ativos`
* `Inconsistências encontradas`
* `Próxima spec recomendada`

Preserve the existing names, structure, language, and formatting conventions of the runtime file when its sections differ from this list.

For each execution, record:

* Spec suite.
* Current spec id and source file or directory.
* Final status.
* Files created, modified, moved, or deleted.
* Discovery or detection commands executed.
* Validation commands executed.
* Exit code of each command.
* Acceptance criteria results.
* Decisions made during execution.
* Blockers or residual risks.
* Next recommended spec.

Do not rewrite unrelated runtime history.

Do not update a runtime outside `/specs/{spec_suite}`.

Do not mark a spec as `completed` if required validations were not run and no explicit spec-defined or inventory-based reason was recorded.

## Blocker policy

Block instead of forcing an unsafe or unverifiable execution when any of these occur:

* The selected spec suite cannot be determined reliably.
* `/specs/{spec_suite}` does not exist.
* A required suite control file is missing.
* The current numbered spec cannot be identified.
* A prerequisite spec is still `pending`, `blocked`, or otherwise incomplete.
* Required discovery or inventory is missing for a destructive, irreversible, or physical change.
* A required tool or validation command is unavailable and no equivalent is explicitly permitted or confirmed.
* The worktree contains unrelated changes that would be overwritten or mixed with the current spec.
* The active spec contains contradictory or insufficient instructions.
* The patch would violate a prohibited change declared by the current spec.
* The implementation would require work assigned to another spec.
* Required acceptance criteria cannot be proven with the available evidence.
* Continuing would require reading or modifying another spec suite.

When blocked:

1. Do not force the implementation.
2. Preserve valid work already completed.
3. Update `/specs/{spec_suite}/execution/runtime.md`.
4. Record the exact blocker, current evidence, files inspected, files touched, commands executed, exit codes, remaining work, and recommended next action.
5. Stop execution.
6. Do not execute dependent specs.

## Completion policy

Mark a numbered spec as `completed` only when:

* The spec belongs to the selected suite.
* All prerequisites are satisfied.
* Required discovery or detection commands were executed.
* Required changes were implemented.
* Required tests were added or updated.
* Mandatory validations were executed successfully.
* Every acceptance criterion is satisfied.
* `/specs/{spec_suite}/execution/runtime.md` was updated with execution evidence.

Do not infer successful validation from code inspection alone.

Do not report a command as executed when it was not run.

Do not report the suite as completed while any required numbered spec remains pending, failed, or blocked.

## Output format for OpenCode responses

After execution, report:

* Active spec suite: `/specs/{spec_suite}`.
* Current spec id and file or directory.
* Final status: `completed`, `blocked`, or `skipped`.
* Files changed.
* Discovery or detection commands executed.
* Validations run with exit codes.
* Acceptance criteria results.
* Runtime updates made.
* Next recommended spec.
* Suite completion status.
* Any blocker, inconsistency, or residual risk.

Do not write generic summaries.

Tie every claim to the selected suite, spec id, files, commands, exit codes, acceptance criteria, and runtime entries.

