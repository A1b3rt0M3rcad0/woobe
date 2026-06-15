# 006 — add-recent-deterministic-history-window

## Tipo

database/refactor

## Objetivo

Carregar os turnos mais recentes em ordem cronológica estável e evitar que sessões longas percam o contexto novo.

## Contexto

`list_by_session` ordena por `created_at ASC` e aplica `limit=100`, retornando os 100 registros mais antigos. A ordenação sem desempate pode variar quando timestamps coincidem.

## Pré-condições

- 003 e 005 completed.

## Alterações permitidas

- `src/modules/agent/domain/repositories.py`;
- `src/modules/agent/infra/database/repositories.py`;
- application handler de contexto;
- configuração técnica do agent;
- testes unitários e integração.

## Alterações proibidas

- alterar semântica do endpoint público de listagem paginada sem teste de compatibilidade;
- carregar histórico ilimitado;
- usar offset crescente para contexto de LLM;
- ordenar apenas por conteúdo ou role.

## Plano de implementação

1. Adicionar método explícito `list_recent_by_session` ao port de mensagens.
2. Consultar em ordem `created_at DESC, id DESC`, limitar e reverter em memória para ordem cronológica.
3. Manter `list_by_session` para API de listagem, evitando quebra pública.
4. Definir limite padrão técnico, inicialmente 100 mensagens, configurável em `runtime_config.history_max_messages` dentro de faixa segura.
5. Preservar pares de tool call/tool result; a janela não pode iniciar em tool result órfão.
6. Registrar `history_message_count` e `history_truncated`.
7. Não implementar sumarização nesta entrega; deixar extensão futura documentada.

## Testes obrigatórios

- 150 mensagens retornam as 100 mais recentes;
- resultado final está cronológico;
- timestamps iguais são ordenados por ID;
- janela não produz tool result órfão;
- limite inválido é normalizado/rejeitado conforme contrato.

## Comandos de validação

```bash
pytest tests/modules/agent/unit/application/test_conversation_history_window.py -q
pytest tests/modules/agent/integration/test_message_repository_recent_history.py -q
```

## Critérios de aceite objetivos

- query recente possui ordenação dupla;
- contexto nunca usa automaticamente os registros mais antigos em detrimento dos novos;
- API existente permanece compatível.

## Rollback

Remover o novo método e restaurar consumidores; não alterar a listagem pública durante rollback.

## Atualização obrigatória de runtime.md

Registrar limite escolhido, SQL observado e próxima spec `007`.
