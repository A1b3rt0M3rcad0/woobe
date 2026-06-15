# 000 — architecture-decision-record-conversation-continuity

## Tipo

architecture

## Objetivo

Registrar a decisão canônica para memória de conversação e impedir que falhas de histórico sejam silenciosamente convertidas em execução sem contexto.

## Contexto

O módulo agent persiste sessões e mensagens localmente, mas a reconstrução de histórico está duplicada nos fluxos sync e stream. Ambos podem descartar todo o histórico sem erro. A plataforma suporta múltiplos providers; memória dependente do provider criaria semântica inconsistente.

## Pré-condições

- branch `development` acessível;
- nenhuma alteração de implementação nesta spec.

## Estado atual a detectar

```bash
git branch --show-current
git rev-parse HEAD
rg "def _load_history|def _resolve_session|def _build_messages" src/modules/agent -g "*.py"
rg "previous_response_id|conversation_id|thread_id" src web -g "*.py" -g "*.ts" -g "*.tsx"
```

Registrar o SHA e a saída relevante em `execution/runtime.md`.

## Alterações permitidas

- `specs/session-conversation-continuity/**`

## Alterações proibidas

- alterar código de produção;
- introduzir memória específica de um provider;
- mover dados de conversação para `shared`;
- modificar contratos HTTP nesta spec.

## Decisão

1. `session_id` do ProjectRAI é a identidade canônica de uma conversa.
2. O banco do módulo agent é a fonte de verdade do histórico.
3. `stateful` significa persistir e reutilizar histórico da mesma sessão.
4. `stateless` significa não criar sessão e não persistir turnos.
5. Falha ao carregar histórico em execução stateful deve falhar explicitamente; nunca retornar lista vazia como fallback silencioso.
6. Sync e stream devem usar o mesmo componente de resolução e montagem de contexto.
7. Estado de conversa do provider, quando futuramente usado, será otimização subordinada ao histórico local, nunca fonte exclusiva.

## Contratos esperados

- comportamento independente do provider;
- replay auditável a partir de `agent.sessions` e `agent.messages`;
- erro de histórico distinguível de “sessão sem mensagens”;
- paridade entre `/runtime/ask` e `/runtime/ask/stream`.

## Testes obrigatórios

- teste de arquitetura que proíba implementação divergente de reconstrução de histórico nos dois fluxos após a spec 007.

## Comandos de validação

```bash
test -f specs/session-conversation-continuity/000-architecture-decision-record-conversation-continuity.md
rg "fonte de verdade|fallback silencioso|Sync e stream" specs/session-conversation-continuity/000-architecture-decision-record-conversation-continuity.md
```

## Critérios de aceite objetivos

- decisão contém os sete itens acima;
- baseline e branch alvo registradas;
- nenhuma alteração fora da pasta de specs.

## Rollback

Remover somente este documento antes de qualquer implementação dependente.

## Atualização obrigatória de runtime.md

Registrar status, data, SHA, decisão e próxima spec `001`.
