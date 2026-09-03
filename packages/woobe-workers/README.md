# woobe-workers

Process host and composition root for Woobe background execution.

This package owns concrete consumers, registries, polling loops, process
lifecycle, worker health and worker-only settings. It may depend on the public
background boundaries exposed by `woobe-core`; `woobe-core` must never depend
on `woobe-workers`.

Dependency direction:

```text
woobe-api      ──► woobe-core
woobe-workers  ──► woobe-core
woobe-core      ✕  woobe-workers
```

Concrete consumers live under `woobe_workers.consumers`. Cross-module
composition lives under `woobe_workers.composition`.

## License

`woobe-workers` is part of Woobe Core and is licensed under the **Woobe Core
Sustainable Use License 1.0** in repository-root `LICENSE.md`, except
third-party components or files carrying their own license notice.
