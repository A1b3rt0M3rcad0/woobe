# Woobe Sustainable Use License 1.0 — pre-release candidate

Copyright (c) 2026 Woobe. All rights reserved except for the permissions expressly granted below.

This license is the pre-release licensing candidate for the Woobe Community/Core source. It is intentionally source-available/fair-code rather than an OSI Open Source license. It must receive qualified legal review before the repository is made public.

## 1. Scope

This license applies to the Woobe Community/Core source in this repository except for edition-specific source.

The following paths are expressly excluded from this license:

- `src/editions/**`
- `web/src/editions/**`

Edition-specific source is governed only by the license expressly identified for that edition. Woobe Cloud source under `src/editions/cloud/**` and `web/src/editions/cloud/**` is governed by `LICENSE-CLOUD.md`.

A future edition path does not automatically receive rights under this license. If edition-specific source has no applicable license granting a right, no such right is granted by this license.

Compatibility/import shims outside `src/editions/**` do not change the license of the edition-specific implementation they reference.

## 2. Permission

Subject to this license, you may use, copy and modify the covered Woobe Community/Core source for:

- personal and non-commercial purposes;
- internal business purposes, including production use inside your organization;
- building and operating your own products and services that use Woobe as an internal AI control plane or runtime;
- exposing AI functionality created with Woobe to your own customers, including through Runtime APIs and ChatSurface, when those customers are consuming your product rather than receiving the Woobe control plane itself as the product.

You may redistribute copies or modified copies of the covered Community/Core source without charge when the redistribution is non-commercial, retains this license and all required notices, and does not imply endorsement by Woobe.

## 3. Restricted commercial uses

Without a separate written commercial license from Woobe, you may not:

- charge third parties for hosted access to the Woobe control plane;
- offer Woobe itself as a managed service, hosted platform or competing "Woobe as a Service";
- white-label the Woobe control plane for third parties;
- resell, sublicense or distribute Woobe as an OEM product for a fee;
- remove or obscure copyright, attribution, license or trademark notices in a way that suggests an unofficial distribution is official Woobe.

A service is not restricted merely because it is commercial. The restriction applies when the commercial offering is substantially the Woobe control plane itself rather than a separate product that uses Woobe internally.

## 4. Modifications

You may modify the covered Community/Core source for permitted uses. If you redistribute a modified copy under this license, you must clearly state that it is modified and must not represent it as an official Woobe build unless authorized in writing.

## 5. No trademark license

This license grants no rights to the Woobe name, logos or other trademarks except the limited nominative use necessary to describe compatibility or origin. See `TRADEMARKS.md`.

## 6. No warranty

Woobe is provided as-is, without warranties or conditions of any kind, express or implied. To the maximum extent permitted by law, the copyright holders and contributors are not liable for claims, damages or other liability arising from use of the software.

## 7. Commercial licensing

Uses restricted by Section 3, and production/commercial rights for separately licensed edition source, require the applicable license or a separate written commercial agreement. See `COMMERCIAL-LICENSE.md`.

## 8. Termination

Your rights under this license terminate if you materially violate its terms and do not cure the violation within thirty days after receiving written notice, when cure is possible. Rights may be reinstated by written agreement.

## 9. Entire permission

No rights are granted except those expressly stated in this license, an applicable edition-specific license, or a separate written agreement with Woobe.
