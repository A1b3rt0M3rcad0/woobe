# Woobe licensing model

Woobe has two software licenses and a separate brand policy:

| Document | Scope |
| --- | --- |
| [LICENSE.md](LICENSE.md) | First-party Core software and supporting content, excluding Enterprise, separately licensed components and brand assets |
| [LICENSE_EE.md](LICENSE_EE.md) | First-party material originally distributed under `packages/woobe-ee/**`, including its copies, modifications, derivative portions and compiled forms |
| [TRADEMARKS.md](TRADEMARKS.md) | Woobe names, logos, symbols and distinctive brand assets |
| Third-party licenses | The applicable third-party components, regardless of their location |

This document explains those controlling texts; it does not replace them or grant additional rights. None of the repository licenses grants the right to sell the Woobe platform, supply paid access to it or use the Woobe brand to market such a supply. Enterprise Production Use authorization does not grant resale or brand rights.

## Core scope

Core includes `woobe-core`, `woobe-api`, `woobe-workers`, `woobe-runtime-client`, `woobe-ui`, `woobe-frontend` and `woobe-embed`, as well as first-party tooling, tests, scripts and documentation outside the exclusions.

Core is source-available, self-hostable and usable in production. Its license permits internal business operations, private modifications and use as infrastructure for your own applications and commercial services. Private modifications and independently developed applications do not have to be published merely because they use Core.

| Activity | Core terms |
| --- | --- |
| Read, download, compile, study, evaluate and test | Permitted |
| Self-host for personal use or internal production | Permitted, including in commercial organizations |
| Run on rented general-purpose cloud infrastructure | Permitted |
| Use Core behind your own commercial application | Permitted within LICENSE.md section 3 |
| Use Runtime APIs, embedded chat, execution views or application-specific configuration | Permitted within the application's purpose |
| Deliver Core as a component of a permitted application installed for a customer | Permitted with the Core license and notices; it must not be a disguised platform sale |
| Maintain private modifications | Permitted without a publication obligation |
| Share a free non-commercial fork | Permitted with its license, attribution and clear independent identity |
| Charge for technical work on a customer's own controlled and permitted deployment | Permitted; selling platform access is not a professional-services exception |
| Sell the platform as a copy, image, package, appliance or installation | Prohibited |
| Supply paid hosted or managed access to a Woobe instance | Prohibited |
| Sell general-purpose Woobe control-plane or runtime functionality through another UI or API | Prohibited |
| Rename, rebrand, white-label or OEM-resell a Woobe-derived platform | Prohibited |
| Include platform access in a required paid plan or bundle while calling it free | Prohibited |
| Remove restrictions from Woobe's code through a replacement license | Prohibited |

The commercial restriction concerns the supply of the Woobe platform or a material part of its general-purpose capabilities. It does not prohibit an application merely because its functionality relies heavily on Woobe.

Free non-commercial sharing does not give recipients commercial platform-supply rights. Genuine consulting, integration, installation and support fees remain permitted for the customer's own deployment; relabeling payment for an instance or access as consulting does not make that supply permissible.

## Enterprise scope and production authorization

The only Enterprise Covered Paths currently designated by [LICENSE_EE.md](LICENSE_EE.md) are `packages/woobe-ee/**`. The directory currently contains a boundary README, not an Enterprise feature implementation; the license defines the permissions for material supplied under that boundary.

The repository license itself grants limited Non-Production Use rights. Production Use requires a separate, valid Enterprise Production Authorization expressly granted by Woobe in writing and covering the actual licensee and use.

| Activity | Enterprise terms |
| --- | --- |
| Read, study, download, copy and compile | Permitted for the authorized non-production purposes |
| Evaluate, develop integrations, modify, run CI and perform isolated tests | Permitted |
| Develop within a business or as paid technical work | Permitted when the Enterprise execution remains non-production |
| Maintain development forks or submit patches | Permitted under the license and applicable contribution terms |
| Share free source forks for development, evaluation, testing or contribution | Permitted with Enterprise restrictions, notices and independent identity |
| Keep inactive EE in a lawfully obtained official distribution used for Core production | Permitted only within LICENSE_EE.md section 5 |
| Execute Enterprise features in internal operations | Requires a valid Enterprise Production Authorization |
| Execute Enterprise features in a free operational service or a real operational pilot | Requires a valid Enterprise Production Authorization |
| Execute Enterprise behind a commercial application | Requires an authorization covering that use |
| Execute a modified Enterprise implementation in production | Requires an authorization covering that use |
| Deliver EE to another operator for production | Distribution and the recipient's Production Use must be expressly covered; no platform resale rights follow |
| Operate outside the authorization's scope or validity | Prohibited |
| Share a key or authorization beyond its authorized licensee and scope | Prohibited |
| Bypass checks to enable unauthorized Production Use | Prohibited |
| Resell Enterprise or supply paid access to a Woobe platform | Prohibited, including for a holder of production authorization |
| Treat installation, importability or source access as production permission | Not permitted |

Production is defined by actual operational use, not an environment label or the existence of revenue. A staging or pilot environment performing real operational work is production. Isolated tests do not become production merely because they use representative data.

The inactive-distribution permission allows only possession, installation and loading needed to detect availability, register disabled status or check authorization. It does not authorize operational execution of an Enterprise feature.

## Integration does not change the license boundary

An independent file in `woobe-api` or another Core package remains Core when it imports or invokes EE. The EE implementation remains Enterprise, and calling it does not grant Production Use rights.

If an Enterprise implementation is copied into another file, the copied material and its derivative portions retain Enterprise terms. The independent code around it does not automatically become Enterprise. Moving, renaming, packaging or compiling material does not change its license.

A single process or container may contain components governed by different terms. Runtime availability, software licensing and production authorization are separate questions. Architectural dependency rules still apply.

## Brand permissions

[TRADEMARKS.md](TRADEMARKS.md) permits ordinary identification of legitimate official installations and truthful descriptive references such as "compatible with Woobe", "built with Woobe" and "forked from Woobe", without implying official status.

It does not permit using Woobe as the identity of a third-party offering, selling the platform under the Woobe name, presenting a fork as official or claiming reseller, partner or endorsement status from an Enterprise authorization.

| Situation | Brand rule |
| --- | --- |
| Preserve copyright notices and technical module identifiers | Permitted; legal notices must be retained where required |
| Preserve original branding in a legitimate official installation | Permitted without claiming Woobe operates the installation |
| Truthfully describe compatibility, integration or independent consulting | Permitted under the policy |
| Discuss or document Woobe in lawful tutorials, research or reviews | Permitted |
| Give a distributed fork its own identity and truthful upstream attribution | Required |
| Use the Woobe logo as your offering's identity or an approval badge | Not granted |
| Market a third-party paid offering of the Woobe platform | Prohibited |
| Claim official status, partnership or representation without that status | Prohibited |

A truthful reference does not legalize a prohibited software offering, and using another brand does not legalize platform resale. The policy preserves rights independently protected by applicable law.

## Distribution and notices

Permitted distributions must include the applicable software license, brand policy and required third-party notices, preserve attribution and identify modifications. This applies to source and compiled forms, including packages and container images.

Core component-distribution permission does not grant Enterprise distribution rights. The applicable Enterprise rights must be checked independently. Brand assets are excluded from the general software grant.

Third-party software remains governed by its own terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [NOTICE.md](NOTICE.md).

## Contributions

External contributions are accepted under [CONTRIBUTOR_LICENSE_AGREEMENT.md](CONTRIBUTOR_LICENSE_AGREEMENT.md). The CLA allows Woobe to use and relicense contributed code across Core and Enterprise while contributors retain their underlying ownership rights. Merely making an Enterprise modification does not assign its authorship to Woobe.

## Release status

The license and contribution documents are active pre-release candidates. Qualified legal review remains a release gate in [RELEASING.md](RELEASING.md). Changes to repository terms do not automatically relicense previously obtained copies.
