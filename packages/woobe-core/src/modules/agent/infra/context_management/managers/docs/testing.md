# Testing and validation

A Context Manager addition should prove behavior at three levels.

## Algorithm

Test the concrete Manager against a Context Manager Context and verify the intended candidate/budget decisions.

## Runtime

Verify that `ContextManagerRunner` preserves:

- mandatory input/system context;
- model budget enforcement;
- source caps;
- Context Snapshot accounting;
- contribution provenance;
- optional source materialization.

## Product/runtime parity

The product catalog and built-in resolver must expose the same selectable names.

For the canonical Standard Manager, regression coverage should also prove that historical `stdcm:v1`, `stdcm:v2`, and `default:v1` snapshots resolve to `standard`.
