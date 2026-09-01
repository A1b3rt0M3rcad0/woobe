# Woobe licensing model

Woobe has two product boundaries: **Core** and **Enterprise**.

There is no separate Woobe Cloud edition in this model. Woobe Core is the source-available, self-hostable product surface in this repository. Enterprise is a separately licensed extension boundary.

`LICENSE.md` is the controlling legal text for Woobe Core. This document explains the intended boundary in practical terms and does not replace the license.

## Woobe Core

Core includes the first-party product packages:

- `packages/woobe-core`
- `packages/woobe-api`
- `packages/woobe-workers`
- `packages/woobe-frontend`
- `packages/woobe-embed`

Core is intended for real production use. A person or company may self-host it, run it internally, modify it privately and use it as infrastructure behind a separate commercial product.

Examples of permitted Core use include operating Agents and Agent Networks for an internal product, exposing product functionality through Runtime APIs, embedding ChatSurface inside a separate application, maintaining a private fork for internal needs, and charging for consulting or implementation around a customer's own permitted deployment.

## The commercial boundary

The central rule is that Woobe Core may power your product, but Woobe itself may not be repackaged as the product you sell without a separate written commercial agreement.

| Scenario | Core license intent |
| --- | --- |
| Internal company deployment | Permitted |
| Private modified fork used internally | Permitted |
| Woobe Core powers a separate SaaS feature or product outcome | Permitted when customers are buying the separate product/outcome |
| Customer-facing application uses Runtime APIs or ChatSurface | Permitted under the license conditions |
| Consultant installs or supports Core for the customer's own deployment | Permitted; professional services may be charged |
| Fork is renamed and sold as an AI-agent/control-plane product | Separate written commercial agreement required |
| Fork is white-labeled or OEM-resold | Separate written commercial agreement required |
| Customers pay for hosted access to the Woobe control plane itself | Separate written commercial agreement required |
| Woobe Core is commercially redistributed as the supplied product, image, package or appliance | Separate written commercial agreement required |

Changing the name, logo, colors, interface, packaging, domain or hosting model does not change this boundary. A rebranded copy is still subject to the Core software license.

## Brand and trademark boundary

The software license and trademark policy are separate.

The Woobe name, logo and distinctive brand assets identify the official Woobe product. The Core license does not grant the right to market a commercial hosted service, managed service, fork or derivative product under the Woobe name.

Accurate nominative references such as “built with Woobe”, “compatible with Woobe” or “forked from Woobe” are allowed when truthful and when they do not imply sponsorship or official status.

See `TRADEMARKS.md`.

## Enterprise

`packages/woobe-ee` is the Enterprise boundary. It is not part of the Core license grant.

At the current project stage the package is only a reserved boundary and contains no Enterprise feature implementation. Future Enterprise implementation requires a valid Enterprise license or other written agreement from Woobe. See `LICENSE_EE.md`.

## Third-party software

Third-party dependencies remain governed by their original licenses. Woobe's Core or Enterprise terms do not replace third-party obligations. See `THIRD_PARTY_NOTICES.md` and `NOTICE.md`.

## Contributions

External contributions are accepted under `CONTRIBUTOR_LICENSE_AGREEMENT.md`. The CLA allows Woobe to use and relicense contributed code so Core can remain source-available while Enterprise can remain separately licensed.

## Release status

The license and contribution documents are active pre-release candidates. Qualified legal review remains a release gate in `docs/PUBLIC_RELEASE_CHECKLIST.md`.
