# Woobe licensing model

Woobe has two software boundaries: **Core** and **Enterprise**.

`LICENSE.md` is the controlling legal text for Woobe Core. This document explains the intended boundary in practical terms and does not replace the license.

## Woobe Core

Core includes the first-party product packages:

- `packages/woobe-core`
- `packages/woobe-api`
- `packages/woobe-workers`
- `packages/woobe-frontend`
- `packages/woobe-embed`

Core is source-available and self-hostable. A person or company may run it internally, use it in production, maintain private modifications and use it as infrastructure behind a separate commercial product.

Examples include operating Agents and Agent Networks for an internal product, exposing functionality through Runtime APIs, embedding ChatSurface inside a separate application, and charging for consulting or implementation around a customer's own permitted Core deployment.

## The commercial boundary

Woobe Core may power your product, but the Woobe system itself may not become the product or service you commercially supply without a separate written agreement.

| Scenario | Core license intent |
| --- | --- |
| Internal company deployment | Permitted |
| Private modified fork used internally | Permitted |
| Core powers a separate SaaS feature or product outcome | Permitted when customers buy the separate product/outcome |
| Customer-facing application uses Runtime APIs or ChatSurface | Permitted under the license conditions |
| Consultant installs or supports Core for the customer's own deployment | Permitted; professional services may be charged |
| Fork is renamed and sold as an AI-agent/control-plane product | Separate written commercial agreement required |
| Fork is white-labeled or OEM-resold | Separate written commercial agreement required |
| Customers pay for hosted access to the Woobe control plane itself | Separate written commercial agreement required |
| Core is commercially redistributed as the supplied product, image, package or appliance | Separate written commercial agreement required |

Changing the name, logo, colors, interface, packaging, domain or hosting model does not change this boundary. A rebranded copy remains subject to the Core software license.

## Brand and trademark boundary

The software license and trademark policy are separate.

The Woobe name, logo and distinctive brand assets identify official Woobe products and authorized services. The Core license does not grant the right to market a commercial hosted service, managed service, fork or derivative product under the Woobe brand.

Accurate nominative references such as “built with Woobe”, “compatible with Woobe” or “forked from Woobe” are permitted when truthful and when they do not imply sponsorship or official status.

See `TRADEMARKS.md`.

## Enterprise

`packages/woobe-ee` is the Enterprise boundary and is not part of the Core license grant.

At the current project stage the package is a reserved boundary. Enterprise implementation requires a valid Enterprise license or other written agreement from Woobe. See `LICENSE_EE.md`.

## Third-party software

Third-party dependencies remain governed by their original licenses. Woobe's software terms do not replace third-party obligations. See `THIRD_PARTY_NOTICES.md` and `NOTICE.md`.

## Contributions

External contributions are accepted under `CONTRIBUTOR_LICENSE_AGREEMENT.md`. The CLA allows Woobe to use and relicense contributed code across Core and separately licensed Enterprise distributions.

## Release status

The license and contribution documents are active pre-release candidates. Qualified legal review remains a release gate in `docs/PUBLIC_RELEASE_CHECKLIST.md`.
