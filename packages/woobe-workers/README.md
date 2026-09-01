# woobe-workers

Process package for Woobe background workers. Worker process composition may depend on `woobe-core`; `woobe-core` must never depend on this package.

Concrete worker implementations remain with the bounded context that owns their behavior in Core; this package owns the process composition root.

## License

`woobe-workers` is part of Woobe Core and is licensed under the **Woobe Core Sustainable Use License 1.0** in repository-root `LICENSE.md`, except third-party components or files carrying their own license notice.
