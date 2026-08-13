# Woobe licensing model

`LICENSE.md` is the definitive license for the Community/Core source distributed in this repository. This document only explains the product boundary in practical terms.

## Community

Woobe Community is source-available and self-hostable. It is intended to be usable in real production deployments, including as internal infrastructure behind a separate commercial product.

Typical Community use includes self-hosting, running Agents and Agent Networks in production, integrating Runtime APIs, embedding ChatSurface, maintaining permitted private modifications, and providing implementation or support around a customer's own Community deployment.

The Community license does not turn hosted access to the Woobe control plane itself into an unrestricted resale product. Refer to `LICENSE.md` for the actual permissions and restrictions.

## Copies, forks and acceptance

Community may be forked, cloned, downloaded and copied for uses permitted by `LICENSE.md`.

The license treats local copies, source archives, repository forks, compiled builds, packages, installers and container images as technical forms of the Covered Software. Changing the packaging format does not remove the Community license restrictions.

Merely viewing the repository, or merely creating or retaining a repository-host-provided fork to the extent independently permitted by that host, is not intended by itself to be the acceptance event for the Woobe license.

Using rights granted by the Woobe license — for example cloning for local or server use, downloading and retaining a copy, running, building, packaging, containerizing, modifying, deploying or redistributing Community — constitutes acceptance of the license terms.

| Action | Community intent |
| --- | --- |
| View the public source repository | Permitted; not by itself a Woobe license acceptance event |
| Create a repository-host-provided fork | Permitted subject to the host's terms; further use remains subject to the Woobe license |
| `git clone` for local or server use | Permitted under the Woobe license |
| Download a source archive or ZIP | Permitted under the Woobe license |
| Keep a private modified fork for your own permitted use | Permitted |
| Run Community in production inside your organization | Permitted |
| Build a commercial product that uses Woobe internally | Permitted |
| Package Community as a container image for your own permitted deployment | Permitted |
| Redistribute a Community fork or image without charge for non-commercial purposes while retaining notices | Permitted under the license conditions |
| Sell hosted access to the Woobe control plane itself | Separate commercial agreement required |
| White-label, OEM-resell or commercially redistribute Woobe itself | Separate commercial agreement required |

## Cloud

Woobe Cloud is a proprietary Woobe-managed product. Proprietary Cloud implementation is not distributed in the Community source tree or Community build context. The Community license does not grant rights to proprietary Cloud implementation.

## Enterprise

Woobe Enterprise is not currently implemented or distributed. No placeholder Enterprise implementation or license is maintained. If Enterprise capabilities are introduced later, their source and distribution terms must be defined explicitly at that time.

## Release status

The current licensing documents are pre-release candidates. Public release remains blocked on the reviews and repository-history checks listed in `docs/PUBLIC_RELEASE_CHECKLIST.md`.
