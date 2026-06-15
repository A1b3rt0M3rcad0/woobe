# Manifesto das Specs

Branch alvo: `development_session-conversation-continuity`.

Baseline: `development` no SHA registrado durante a spec 001.

| Ordem | Spec | Tipo | Dependência | Fase |
|---:|---|---|---|---|
| 000 | `000-architecture-decision-record-conversation-continuity.md` | architecture | - | decisão |
| 001 | `001-reproduce-and-inventory-session-history-failure.md` | discovery | 000 | diagnóstico |
| 002 | `002-define-stateful-stateless-and-session-reuse-contract.md` | architecture | 001 | contrato |
| 003 | `003-fix-history-message-reconstruction.md` | refactor | 002 | correção crítica |
| 004 | `004-fix-current-turn-persistence-and-prompt-order.md` | refactor | 003 | correção crítica |
| 005 | `005-harden-session-resolution-and-ownership.md` | refactor | 002 | sessão |
| 006 | `006-add-recent-deterministic-history-window.md` | database/refactor | 003,005 | histórico |
| 007 | `007-unify-sync-and-stream-conversation-context.md` | refactor | 003-006 | paridade |
| 008 | `008-preserve-playground-session-lifecycle.md` | frontend | 002,005,007 | playground |
| 009 | `009-align-runtime-controls-with-effective-execution-mode.md` | frontend/contract | 002,008 | playground |
| 010 | `010-add-history-session-observability.md` | observability | 003-007 | diagnóstico operacional |
| 011 | `011-add-backend-unit-integration-and-contract-tests.md` | test | 003-010 | testes backend |
| 012 | `012-add-playground-session-continuity-tests.md` | test | 008-009 | testes frontend |
| 013 | `013-execute-final-validation-and-generate-report.md` | validation/report | 011-012 | conclusão |
