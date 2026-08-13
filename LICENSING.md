# Woobe licensing model

`LICENSE.md` is the definitive license for the Community/Core source distributed in this repository. This document only explains the product boundary in practical terms.

## Community

Woobe Community is source-available and self-hostable. It is intended to be usable in real production deployments, including as internal infrastructure behind a separate commercial product.

Typical Community use includes self-hosting, running Agents and Agent Networks in production, integrating Runtime APIs, embedding ChatSurface, maintaining permitted private modifications, and providing implementation or support around a customer's own Community deployment.

The Community license does not turn hosted access to the Woobe control plane itself into an unrestricted resale product. Refer to `LICENSE.md` for the actual permissions and restrictions.

## Internal use versus resale

A company may fork and modify Woobe Community for its own internal business use, including production. Internal modifications may include source code changes, integrations, configuration, UI changes and internal branding. The company does not have to publish those private modifications merely because it changed Community.

The same fork may also operate behind a separate commercial product. For example, a company may use a private Woobe fork to run Agents and Networks that power its own customer-facing application through Runtime APIs or ChatSurface. In that case, the customer is buying the company's separate product or outcome rather than access to the Woobe control plane itself.

What Community does not permit without a separate written commercial agreement is turning the fork itself into the commercial product. A company may not take Woobe Community, rebrand or redesign it, and then sell, license, rent, host, white-label, OEM-resell or otherwise commercially supply the resulting control plane to third parties when the primary or substantial value being sold is Woobe's own control-plane functionality.

Changing the name, logo, colors, interface, domain, packaging, container image or hosting arrangement does not change that boundary. The relevant distinction is the substance of what the third party is receiving, not the brand placed on top of the software.

Practical examples:

| Scenario | Community intent |
| --- | --- |
| Private fork used by employees inside the company | Permitted |
| Private fork modified and rebranded only for internal use | Permitted |
| Private fork deployed in internal production | Permitted |
| Private fork used behind the company's own SaaS feature | Permitted when customers receive a separate product/outcome rather than the Woobe control plane |
| Customer-facing application using Runtime APIs or ChatSurface | Permitted under the license conditions |
| Consultant installs or supports Community for the customer's own permitted deployment | Permitted; professional services may be charged |
| Fork is renamed and sold as an AI agent platform | Separate commercial agreement required |
| Fork is white-labeled and sold to customers | Separate commercial agreement required |
| Fork is hosted and customers pay to access the control plane | Separate commercial agreement required |
| Docker image, installer or package containing Woobe is commercially resold as the product | Separate commercial agreement required |
| OEM or reseller offering where Woobe itself is the supplied technology | Separate commercial agreement required |

## Copies, forks and acceptance

Community may be forked, cloned, downloaded and copied for uses permitted by `LICENSE.md`.

The license treats local copies, source archives, repository forks, compiled builds, packages, installers and container images as technical forms of the Covered Software. Changing the packaging format does not remove the Community license restrictions.

Merely viewing the repository, or merely creating or retaining a repository-host-provided fork to the extent independently permitted by that host, is not intended by itself to be the acceptance event for the Woobe license.

Using rights granted by the Woobe license — for example cloning for local or server use, downloading and retaining a copy, running, building, packaging, containerizing, modifying, deploying or redistributing Community — constitutes acceptance of the license terms.

## Cloud

Woobe Cloud is a proprietary Woobe-managed product. Proprietary Cloud implementation is not distributed in the Community source tree or Community build context. The Community license does not grant rights to proprietary Cloud implementation.

## Enterprise

Woobe Enterprise is not currently implemented or distributed. No placeholder Enterprise implementation or license is maintained. If Enterprise capabilities are introduced later, their source and distribution terms must be defined explicitly at that time.

## Release status

`LICENSE.md` is the active Community license text in this repository. Public release remains blocked until the legal, dependency-inventory, artifact and repository-history gates in `docs/PUBLIC_RELEASE_CHECKLIST.md` are completed.
