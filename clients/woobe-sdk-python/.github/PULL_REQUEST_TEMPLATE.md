## Scope

Describe the concrete problem and the smallest change that solves it.

## Changes

- 

## Public API / Runtime contract impact

- [ ] No public API or Runtime contract change
- [ ] Backward-compatible public change
- [ ] Breaking public change
- [ ] Runtime Protocol / streaming behavior change

Describe compatibility or migration impact when applicable.

## Validation

State exactly what was executed.

- [ ] `ruff check .`
- [ ] `pytest`
- [ ] `python -m build`
- [ ] `twine check dist/*`
- [ ] Manual Runtime smoke validation, when applicable

## Dependencies / licensing

- [ ] No new third-party dependency/material
- [ ] Dependency provenance/license reviewed
- [ ] `THIRD_PARTY_NOTICES.md` updated when required

## Checklist

- [ ] PR targets `master`
- [ ] Change is limited to one concern
- [ ] No unrelated refactor
- [ ] No Runtime Keys, tokens, customer data or private endpoints
- [ ] SDK remains a client, not an execution engine/control plane
- [ ] Recovery cannot duplicate a logical Run
- [ ] Private transport details are not exposed as public API
- [ ] Tests cover changed behavior
- [ ] Documentation/changelog updated when public behavior changed
- [ ] Brand usage complies with `TRADEMARKS.md`

## Contribution license

- [ ] I have the right to submit this contribution and agree that accepted contributions are licensed under the repository MIT License.
