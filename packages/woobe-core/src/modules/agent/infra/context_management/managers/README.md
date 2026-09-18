# Context Managers

Context Managers define how Woobe assembles the effective context for each Model Invocation.

Concrete Managers contain algorithm decisions only. Shared mechanics belong to `manager_runtime/`.

Use [`standard.py`](./standard.py) as the canonical implementation reference.

To create another Manager, start with [`docs/creating-a-manager.md`](./docs/creating-a-manager.md).
