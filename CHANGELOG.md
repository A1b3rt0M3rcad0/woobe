# Changelog

All notable changes to ProjectRAI are documented in this file.

## [Unreleased]

### Added

- deterministic two-tenant release fixture with controlled projects, agents, usage and traces;
- local OpenAI-compatible fake provider for streaming, fallback, tool calls, failures, latency and cancellation;
- Chromium E2E coverage for onboarding, workspace selection, dashboard, agent creation, playground session reload, API-key creation and cross-tenant denial;
- release load runner producing latency p50/p95/p99, TTFT, throughput and error-rate evidence;
- migration rollback/re-upgrade, PostgreSQL backup/restore and production-image smoke gates;
- OWASP-oriented release configuration contracts and explicit release-readiness documentation.

### Changed

- release qualification is now performed by dedicated, non-retrying GitHub Actions workflows targeting `development-mvp`.

### Security

- tenant isolation remains fail-closed across organizations, projects, API keys, credentials, agents, prompt versions, collections, documents, tools, sessions, messages and traces;
- the production proxy contract requires CSP, clickjacking protection, content-type protection, referrer policy and restricted browser capabilities;
- deterministic release fixtures contain no external API keys or production secrets.

## Contract freeze

The MVP HTTP and SSE contracts are frozen for the release-candidate gate. Changes to endpoint paths, authorization semantics, envelope shapes or SSE protocol v1 require an explicit compatibility review and changelog entry.
