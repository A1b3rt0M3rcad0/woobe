# woobe-ee

Reserved implementation boundary for Woobe Enterprise capabilities. This directory currently contains no Enterprise feature implementation.

Core deployments of API and Workers must remain runnable without installing or activating Enterprise implementation. Optional integrations must respect the repository's architectural dependency rules.

## License

The Enterprise Covered Paths are `packages/woobe-ee/**`. First-party material supplied under this boundary is **not covered by the Woobe Core license grant**. Its copies, modifications, derivative portions and compiled forms retain their Enterprise terms when moved or incorporated elsewhere.

Repository-root [LICENSE_EE.md](../../LICENSE_EE.md) permits reading, evaluation, development, integration work, modification, isolated testing and the specified non-production source forks and contributions.

**Production Use requires a valid Enterprise Production Authorization expressly granted by Woobe in writing.** Source access, downloading, installation and importability do not grant production rights.

Independent Core code that imports or invokes EE retains its own license. A shared process or container does not merge the licenses.

Neither the repository license nor production authorization grants platform resale, paid hosted-platform, OEM, commercial white-label or brand rights. See [LICENSE.md](../../LICENSE.md), [LICENSING.md](../../LICENSING.md) and [TRADEMARKS.md](../../TRADEMARKS.md).
