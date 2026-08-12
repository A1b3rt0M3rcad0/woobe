# Woobe Cloud source boundary

Code under `src/editions/cloud/**` belongs to the Woobe Cloud commercial edition and is not licensed under the Woobe Community/Core license.

The source remains visible so operators and customers can inspect the implementation and security boundaries. Visibility does not grant production, hosting, resale, white-label, OEM or redistribution rights beyond `LICENSE-CLOUD.md` or a separate written commercial agreement.

The shared Woobe runtime remains under `src/modules/**`. Cloud code may depend on the shared core; the shared core must not require Cloud modules in Community deployments.

`billing/` is currently the only Cloud-specific backend bounded context. Future commercial capabilities should be placed here only when they are genuinely Cloud-specific rather than used to artificially limit the Community core.
