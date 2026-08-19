# Woobe Quality Gate

`quality_gate/architecture` enforces executable import boundaries for modules that have been migrated to the Woobe architecture contract.

Each governed bounded context owns one TOML policy in `quality_gate/architecture/policies/`. The checker is generic: adding a module means adding a policy, not adding module-specific branches to the checker.

The first governed module is `agent`. Its policy follows the composition model used by the HostGator challenge: application owns contracts, infrastructure implements them, presentation controllers depend on contracts, routes enter through composition, and composition is the only layer allowed to wire concrete implementations.

Run locally with:

```bash
uv run python -m quality_gate.architecture.checker
uv run pytest -q tests/quality_gate
```

The `Quality Gate` GitHub Actions workflow runs on pull requests targeting `development` whenever governed source, policies, gate tests, dependencies, or the workflow itself changes. A failing architecture policy blocks that CI check.

A policy is strict. Governed modules do not have architecture allowlists; a violation must be removed from the source or explicitly changed in the policy as an architectural decision.
