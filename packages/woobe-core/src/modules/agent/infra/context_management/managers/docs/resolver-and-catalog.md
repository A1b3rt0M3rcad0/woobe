# Resolver and product catalog

Runtime implementation and product metadata are separate.

## Resolver

```text
infra/context_management/managers/resolver.py
```

The resolver owns concrete factories and wraps Managers with `ContextManagerRunner`.

## Catalog

```text
application/context_manager_registry.py
```

The application catalog owns product-facing metadata only.

Application code must not import concrete infrastructure Managers.

## Identity parity

Every selectable Manager name must exist in both places.

Names are stable and unversioned:

```text
standard
adaptive
long-horizon
```

Do not introduce `standard:v2` or similar product identities.
