# 010 — add-history-session-observability

## Tipo

observability

## Objetivo

Permitir diagnosticar continuidade de sessão sem registrar conteúdo sensível da conversa.

## Contexto

A falha atual é invisível porque `_load_history` retorna `[]`. Trace e logs não distinguem sessão vazia de erro de reconstrução.

## Pré-condições

- 003 a 007 completed.

## Alterações permitidas

- portas/adapters de trace do agent;
- eventos de trace;
- logs estruturados;
- painel DebugView/TraceDetails;
- testes.

## Alterações proibidas

- logar conteúdo integral de mensagens;
- logar secrets, prompts privados ou dados de tool output por padrão;
- mascarar erro como `history_count=0`;
- criar dependência direta da aplicação em módulo de observability.

## Eventos mínimos

### `conversation.session_resolved`

- `session_id`;
- `created` boolean;
- `mode`;
- `project_id` e `agent_id`;
- sem conteúdo.

### `conversation.history_loaded`

- `session_id`;
- `message_count`;
- `turn_count`;
- `truncated`;
- `window_limit`;
- `contains_tool_calls`.

### `conversation.history_failed`

- `session_id`;
- classe/código do erro;
- estágio `query|mapping|validation`;
- sem conteúdo.

### `conversation.session_ignored_stateless`

- indicador de que um ID recebido foi ignorado por compatibilidade.

## Plano de implementação

1. Emitir eventos via `TraceRecorder`/port existente.
2. Logar falhas com `logger.exception` e campos estruturados.
3. Expor contadores no DebugView e TraceDetails.
4. Garantir que erro de histórico produza SSE `error` ou resposta HTTP, não resposta do LLM sem contexto.
5. Adicionar métrica/contador para `history_failed` se infraestrutura suportar.

## Testes obrigatórios

- evento loaded em sucesso;
- evento failed em erro;
- nenhum conteúdo sensível no payload;
- stream encerra com erro explícito;
- debug view renderiza contadores.

## Comandos de validação

```bash
pytest tests/modules/agent -q
cd web && npm run test:run -- history-observability
```

## Critérios de aceite objetivos

- falha e histórico vazio são distinguíveis;
- logs não expõem conteúdo;
- trace contém sessão e contagens.

## Rollback

Remover eventos e UI em conjunto, preservando a correção funcional.

## Atualização obrigatória de runtime.md

Registrar esquema dos eventos e próxima spec `011`.
