# Enterprise integration boundary

This directory contains the Core-side integration contract used to compose separately licensed Woobe Enterprise implementation.

## License boundary

`contracts.py` is Core software governed by repository-root `LICENSE.md`.

Implementing, importing or satisfying the contract does **not** grant rights to Enterprise implementation. Enterprise code is governed by `LICENSE_EE.md` and/or a separate written agreement with Woobe.

The contract is an interoperability boundary. It is not a feature flag and it is not a license switch.

## Dependency direction

```text
Enterprise implementation
          ↓
Core integration contract
          ↓
     Woobe Core runtime
```

Core must never import Enterprise implementation modules.

`editions` intentionally remains a Python namespace package. Do not add `src/editions/__init__.py`.
