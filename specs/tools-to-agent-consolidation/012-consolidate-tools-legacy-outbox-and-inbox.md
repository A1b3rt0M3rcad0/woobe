# 012 — Consolidar Outbox e Inbox legadas de tools

**Status:** pending  
**Tipo:** database-migration  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Drenar/transformar `tools.outbox_events` e `tools.inbox_events` para tabelas canônicas agent.

## Contexto observado

Mensageria homônima não deve ser movida diretamente porque agent já tem envelope, locks e idempotência próprios.

## Pré-condições

- spec 010 concluída
- spec 011 aplicada
- status/volumes disponíveis

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
psql "$PROJECTRAI_DATABASE_URL" -c "SELECT 'outbox' t,status,count(*) FROM tools.outbox_events GROUP BY status UNION ALL SELECT 'inbox',status,count(*) FROM tools.inbox_events GROUP BY status;" || true
rg -n "class .*Outbox|class .*Inbox" src/modules/tools src/modules/agent
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- migration append-only
- data migration scripts
- tests/migrations/**

## Alterações proibidas

- drop com pendentes
- nova idempotency para processado
- payload com segredo

## Regras invariantes

- O estado final possui apenas `src/modules/agent` como proprietário das capacidades de ferramentas usadas por agentes.
- Não manter `tools` como bounded context independente no estado final.
- Não criar chamadas síncronas entre módulos para alteração de estado.
- Não criar Unit of Work que atravesse módulos distintos.
- Não criar Foreign Key física entre tabelas de módulos diferentes.
- Referências a `project_id`, `organization_id`, `user_id` ou IDs externos permanecem UUIDs opacos e indexados, sem FK cross-module.
- FKs internas dentro de `agent.*` são permitidas.
- Escritas de domínio e Outbox devem ocorrer na mesma transação do `AgentUnitOfWork`.
- Inbox/Outbox legadas de `tools` não podem ser descartadas com eventos pendentes.
- Rotas HTTP atuais devem permanecer compatíveis durante o cutover.
- Segredos nunca podem aparecer em logs, eventos, respostas HTTP, fixtures, snapshots ou mensagens de erro.
- Não editar migrations históricas já aplicadas; usar migrations append-only após o head observado.
- Não usar `DROP SCHEMA ... CASCADE`.
- Não marcar a spec como concluída sem evidências de validação e atualização de `execution/runtime.md`.


## Plano de implementação

1. Mapear envelope legado.
2. Copiar pending/retryable preservando identidade/correlação.
3. Arquivar completed/processed/dead conforme retenção.
4. Deduplicar.
5. Bloquear linhas não classificadas.
6. Remover tabelas após zero pendências.
7. Documentar downgrade/backup.

## Testes obrigatórios

- idempotência
- preservação pendentes
- duplicados
- redaction
- blocker

## Validação

```bash
pytest tests/migrations -q
pytest tests/integration/agent -q
alembic upgrade head
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- zero perda
- zero duplicação lógica
- sem sensível
- fonte única agent

## Rollback

- restaurar backup e registry antes de downgrade

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
