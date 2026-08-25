# Public edition integration boundary

This directory contains only the public integration contract used to compose separately distributed Woobe editions with Community/Core.

## License boundary

`contracts.py` is Covered Software under the repository-level `LICENSE.md` and is part of Woobe Community/Core.

Using, importing, implementing, or satisfying the contract does **not** grant any license or other rights to Woobe Cloud, future Woobe Enterprise code, or any other proprietary implementation maintained outside this repository. Proprietary implementations are governed exclusively by the license shipped with their own repository or by a separate written agreement with Woobe.

The contract is an interoperability boundary. It is not a feature flag and it is not a license switch.

## Dependency direction

The allowed dependency direction is one-way:

```text
separately licensed edition implementation
                ↓
       Community integration contract
                ↓
          Community/Core runtime
```

Community/Core must never import proprietary edition implementation modules.

`editions` intentionally remains a Python namespace package. Do not add `src/editions/__init__.py`. A private build may overlay a separately licensed package such as `editions.cloud` while Community provides only `editions.contracts`.

No proprietary source may be committed under `src/editions/cloud/` or `src/editions/enterprise/` in this repository.
