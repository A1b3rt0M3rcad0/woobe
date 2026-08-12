# Commercial licensing boundary

Woobe Community is intended to be useful as a real self-hosted product, not as a crippled trial.

The Community/Core license is designed to allow companies to run the covered Woobe core internally and to build commercial products that use Agents, Agent Networks, Runtime APIs and ChatSurface. The customer's product may charge its own users.

A separate commercial/OEM agreement is intended when the commercial value being sold is substantially access to the Woobe control plane itself, including hosted Woobe, white-label control-plane offerings, resale or OEM redistribution.

## Source boundary

The repository separates shared core code from edition-specific commercial code:

```text
src/modules/**                 Woobe Community/Core
src/editions/cloud/**          Woobe Cloud
web/src/editions/cloud/**      Woobe Cloud frontend
```

`LICENSE.md` governs the covered Community/Core source. `LICENSE-CLOUD.md` governs the Cloud edition paths. Source visibility is intentional for review and transparency, but it does not grant production or commercial rights to the Cloud edition.

A compatibility import outside an edition directory does not move the Cloud implementation into the Community/Core license.

Woobe Cloud is a separate managed offering that may charge for managed infrastructure, storage, backups, upgrades, support, capacity and usage according to its commercial terms. Billing is currently a Cloud-specific bounded context and lives under the Cloud edition boundary.

Enterprise capabilities such as SSO/SAML, SCIM, advanced governance, advanced audit export, external KMS/secrets, supported HA and SLA are future commercial capabilities and are not prerequisites for the Community release. No empty Enterprise source boundary is created until real Enterprise functionality exists; when it does, it must receive an explicit license rather than inheriting Community rights accidentally.

This document explains product intent. Definitive rights come from `LICENSE.md`, `LICENSE-CLOUD.md`, any future edition-specific license, and any signed commercial agreement.
