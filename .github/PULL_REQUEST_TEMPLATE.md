## Scope

Describe the concrete problem, why it matters, and the smallest change that solves it.

## Changes

- 

## Product / license impact

- [ ] Core
- [ ] Enterprise boundary
- [ ] Licensing / trademark / notice change
- [ ] No product-license impact

Explain any change to Core ↔ Enterprise boundaries, package ownership, licensing paths, distributed artifacts, third-party notices or Woobe brand usage.

## Validation

State exactly what was executed. Do not mark a check as passing unless it was actually run.

- [ ] Relevant backend tests
- [ ] Relevant frontend tests/build
- [ ] Migration validation, when applicable
- [ ] Container/Compose validation, when applicable
- [ ] Manual acceptance/smoke validation, when applicable

## Database

- [ ] No schema change
- [ ] Migration included and rollback/compatibility considered

Describe migration and data compatibility impact when applicable.

## Third-party material

- [ ] No new third-party code/assets/dependencies
- [ ] Third-party provenance and license obligations reviewed
- [ ] `THIRD_PARTY_NOTICES.md` updated when required

## Risk / rollback

Describe breaking changes, operational impact, known limitations, and the rollback path.

## Checklist

- [ ] PR targets `master`
- [ ] Change is limited to the requested scope
- [ ] No unrelated refactor
- [ ] No secrets, tokens, customer data or internal-only artifacts
- [ ] Core does not depend on Enterprise implementation
- [ ] Product packages do not depend on `tooling/`
- [ ] Backend remains the enforcement boundary for critical rules
- [ ] Documentation updated when public behavior or contracts changed
- [ ] Brand/trademark usage complies with `TRADEMARKS.md`

## External contributor CLA

External contributors must explicitly accept the repository CLA before merge:

- [ ] I have read and agree to the Woobe Contributor License Agreement.
