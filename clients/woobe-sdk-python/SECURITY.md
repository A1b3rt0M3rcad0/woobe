# Security Policy

## Supported versions

Until Woobe SDK reaches a stable 1.0 release, security fixes target the current supported pre-release line and the `master` integration branch.

After stable release lines exist, this section should be updated with an explicit supported-version matrix.

## Reporting a vulnerability

Do not open a public issue containing an exploit, Runtime Key, credential, private endpoint, customer data or unpatched vulnerability details.

Prefer GitHub private vulnerability reporting/security advisories when available. If that channel is not enabled, contact the repository owner privately and include the affected SDK version, impact, reproduction steps and any suggested mitigation.

Redact real Runtime Keys and tokens. Reproduce with synthetic credentials whenever possible.

## SDK security boundaries

Important SDK trust boundaries include:

- Runtime Keys and authorization headers;
- base URL configuration and outbound HTTP requests;
- External Context values that applications send to the Runtime;
- SSE/event parsing and protocol validation;
- Run/Session identity continuity across reconnects;
- duplicate-Run prevention;
- error messages and exceptions that must not leak credentials.

A Runtime alias, Run ID or Session ID is not treated as authorization by itself.

## Dependency security

Runtime dependencies should remain minimal. Security-impacting dependency changes require explicit review.

The scheduled security workflow provides dependency auditing, but release decisions must still consider whether a reported advisory is reachable or relevant to the SDK.

## Deployment responsibility

Applications embedding the SDK are responsible for protecting Runtime Keys, configuring trusted endpoints, controlling logs and telemetry, and upgrading the SDK when fixes are released.

The SDK must not silently weaken TLS verification or expose credentials in exceptions for convenience.
