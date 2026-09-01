# Woobe Notices

Woobe is an API-first control plane and runtime for operating AI products.

## Product boundaries

**Woobe Core** is the source-available, self-hostable product surface distributed from this repository. Its first-party software is governed by `LICENSE.md` unless a file carries a different license notice.

**Woobe Enterprise** is a separately licensed boundary under `packages/woobe-ee`. The current repository contains only the Enterprise boundary marker and no Enterprise feature implementation. Enterprise rights are not granted by the Core license; see `LICENSE_EE.md`.

Woobe does not use a separate “Community” or “Cloud” product edition in the current product model.

## Brand

The Woobe name, logo and distinctive brand assets are not licensed by the Core software license. See `TRADEMARKS.md`.

## Third-party software

Third-party dependencies remain subject to their original license terms. `THIRD_PARTY_NOTICES.md` describes the dependency-inventory and notice process for released Woobe Core artifacts.

## Runtime independence

Woobe Core is self-hostable and does not require an external Woobe-hosted control-plane service to operate. Any future telemetry or external service dependency must be documented explicitly and must not silently redefine the Core licensing boundary.

## Pre-release status

The licensing, contribution and trademark documents remain subject to the legal review gate in `docs/PUBLIC_RELEASE_CHECKLIST.md` before public or commercial reliance.
