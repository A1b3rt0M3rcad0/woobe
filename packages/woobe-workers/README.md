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

## Published container

The deployable image is `ghcr.io/a1b3rt0m3rcad0/woobe-workers:<VERSION>`. Its default process is `python -m worker_main`. Workers require the compatible Woobe data/runtime services plus RabbitMQ and may be scaled independently from the API.

See [`docs/runbooks/container-packages.md`](../../docs/runbooks/container-packages.md) for pull, environment, shared-storage and standalone run examples.

## License

`woobe-workers` is part of Woobe Core and is licensed under the **Woobe Core
Sustainable Use License 1.0** in repository-root `LICENSE.md`, except
third-party components or files carrying their own license notice.
