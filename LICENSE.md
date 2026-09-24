# Woobe Core Sustainable Use License 1.0

Copyright (c) 2026 Woobe. All rights reserved except for the permissions expressly granted below.

Woobe Core is source-available software. This is not an OSI Open Source license.

## 1. License boundaries

"Woobe" is the licensor identified in the applicable copyright notices. "You" is the individual or legal entity exercising the permissions below.

"Woobe Core" or "Core Software" means the first-party software and supporting repository content that Woobe distributes under this license, including copies, modifications, derivative portions and compiled forms of that material, subject to the exclusions below.

The Core packages include:

- `packages/woobe-core`
- `packages/woobe-api`
- `packages/woobe-workers`
- `packages/woobe-runtime-client`
- `packages/woobe-ui`
- `packages/woobe-frontend`
- `packages/woobe-embed`

First-party tooling, tests, scripts and documentation are also covered unless Woobe supplies a different applicable license notice.

Enterprise Software, as defined in [LICENSE_EE.md](LICENSE_EE.md), is not licensed as Woobe Core. Its original Covered Paths are `packages/woobe-ee/**`. This exclusion also covers copies, modifications, derivative portions and compiled forms of Enterprise Software, even if a recipient moves or incorporates that material elsewhere. Moving a file or changing its notice does not relicense it.

Independent integration code outside those Covered Paths does not become Enterprise Software merely because it imports, loads, invokes, links to or interoperates with Enterprise Software; it remains under its applicable Core license. This rule does not relicense Enterprise implementation incorporated into that code. Combining components in one process, package or container does not replace their respective licenses. No Core permission grants Enterprise Production Use rights.

Third-party components retain their own licenses. Woobe names, logos, symbols and distinctive brand assets are excluded from the general software grant and governed by [TRADEMARKS.md](TRADEMARKS.md), including the limited permissions for ordinary identification and descriptive references.

## 2. Acceptance and grant

You do not need to accept this license merely to view the repository where applicable law or repository-host terms independently permit that activity.

By exercising permissions granted here, including downloading, building, running, modifying, deploying or redistributing Core Software, you accept these terms.

Subject to these terms, Woobe grants you a worldwide, royalty-free, non-exclusive, non-transferable and non-sublicensable license to use, copy, compile, run, modify, prepare derivative works from and distribute Core Software for the permitted uses in section 3. Recipients obtain their permissions to Woobe's material directly under this license; you may not sublicense that material on terms that remove its restrictions.

## 3. Permitted uses

### Personal, internal and production use

You may use Core Software for personal use, non-commercial use and your own internal business operations, including production. You may self-host it on your own equipment or on general-purpose infrastructure you rent from a third party.

You may maintain private forks and modifications for permitted uses. This license does not require publication of private modifications or of independently developed applications merely because they use Core Software.

### Infrastructure for your own applications and services

You may use Core Software as infrastructure for your own applications, products and services, including commercial offerings. You may integrate Runtime APIs, ChatSurface, Agents, Agent Networks and related capabilities into those applications.

You may distribute Core Software as a component of such an application, including an application installed on a customer's infrastructure, subject to sections 4 and 6. Customers must receive the applicable Core terms for the included Core material.

These permissions cover the delivery of your application's functionality or outcomes. They do not authorize the commercial supply of the Woobe platform itself described in section 4. An application is not excluded merely because it depends heavily on Core Software, uses its APIs, exposes an embedded chat or execution view, or provides configuration confined to that application's purpose.

### Professional services

You may charge for genuine consulting, implementation, integration, training, maintenance or support work on a customer's own permitted deployment. The customer must control that deployment and obtain software rights under the applicable Woobe terms. The charge must be for the technical work, rather than for a software license, a supplied Woobe instance or continued access to the Woobe platform.

Renting general-purpose compute, storage or network infrastructure does not itself constitute supplying the Woobe platform.

### Free distribution

You may publish and share copies, source forks and modifications without charge for non-commercial purposes, subject to the notice and brand requirements below. A free distribution does not authorize recipients to commercially supply the platform.

## 4. Prohibited commercial supply of the Woobe platform

You may not sell, rent, lease, sublicense, commercially redistribute, resell, OEM-supply, commercially white-label, or charge third parties for access to Core Software itself or to a fork, modification or derivative of it as a platform.

This prohibition covers providing the Woobe control plane or agent runtime, or a material part of its general-purpose platform capabilities, as the software or service being commercially supplied. It includes:

- selling copies, downloads, packages, images, appliances or installations of the platform;
- supplying a Woobe instance through a paid hosted or managed service;
- charging for access to the platform's administration, projects, Agents, Agent Networks, execution capacity or general-purpose runtime APIs;
- supplying a renamed, rebranded or redesigned derivative platform;
- supplying the platform within a paid bundle, even if no separate price is assigned to Woobe.

The prohibition applies to direct and indirect consideration for that supply, including required subscriptions, access plans or bundled charges. Calling the platform free, or describing an access charge as support or consulting, does not change the substance of the transaction.

Names, logos, colors, domains, interfaces, wrappers, deployment models and the absence of a graphical interface do not change this restriction. You need not supply every Woobe feature for a platform offering to fall within it.

The permitted applications, component distribution, professional services and general-purpose infrastructure in section 3 remain permitted. The relevant distinction is whether you supply your own application's functionality or outcomes, or commercially supply Woobe's platform capabilities themselves.

This license grants no platform resale, reseller, OEM, commercial white-label or paid hosted-platform rights. An Enterprise authorization for Production Use does not grant those rights or waive this restriction.

## 5. Woobe name, logo and brand

This software license grants no general trademark, service-mark or branding rights. The limited permissions and restrictions in [TRADEMARKS.md](TRADEMARKS.md) apply independently.

You may make truthful descriptive references such as "compatible with Woobe", "built with Woobe" or "forked from Woobe" under that policy. You may not use the Woobe brand to sell or market the Woobe platform as your own offering or imply that you are Woobe or its official representative.

Using another name or logo does not make prohibited commercial supply permissible. A descriptive reference to Woobe does not authorize an activity prohibited by this license.

## 6. Modifications, distribution and notices

Every permitted distribution must preserve applicable copyright, license and attribution notices and provide recipients with this license, [TRADEMARKS.md](TRADEMARKS.md) and applicable third-party notices. These obligations apply to source and compiled distributions, including packages, container images and embedded copies.

Modified distributions must clearly identify material changes and their independent origin. Do not represent a modified build or fork as an official Woobe distribution.

You may not remove or obscure applicable legal notices or represent that Woobe's code is licensed under unrestricted replacement terms. Your own independent code retains its own applicable terms; distributing it alongside Core Software does not relicense Woobe's material or require publishing that independent code.

A combined distribution containing Enterprise Software must also comply with its own license and notice requirements. Permission to distribute Core Software does not grant permission to distribute or use Enterprise Software.

## 7. Third-party components

Third-party components remain governed by their own licenses. This license does not replace, restrict or expand those licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 8. Patent permission

To the extent Woobe owns patent claims necessarily infringed by Woobe Core, Woobe grants a worldwide, royalty-free, non-exclusive patent license only as necessary to exercise the uses otherwise permitted by this license. This patent permission does not expand the permitted uses or override the restrictions above.

## 9. Warranty and liability

Woobe Core is provided as-is, without warranties or conditions of any kind, express or implied, to the maximum extent permitted by applicable law. To that same maximum extent, Woobe, copyright holders and contributors are not liable for claims or damages arising from use of the software.

## 10. Termination

Rights under this license terminate automatically upon material violation. If a first curable violation is fully cured within thirty days after written notice describing it, the rights terminated because of that violation are reinstated. Other reinstatement requires written agreement when legally available.

## 11. No implied rights

No rights are granted by this license except those expressly stated. Applicable third-party licenses, rights independently provided by a repository-hosting service for its own platform functionality, and rights that applicable law does not allow this license to restrict remain unaffected.

Permissions apply to the material distributed under this text. Updating this repository does not by itself relicense copies previously obtained under other applicable terms.

## 12. Pre-release legal status

This license text is the active Woobe Core license candidate in the repository. Qualified legal review remains required before public or commercial reliance, as tracked in [docs/PUBLIC_RELEASE_CHECKLIST.md](docs/PUBLIC_RELEASE_CHECKLIST.md).
