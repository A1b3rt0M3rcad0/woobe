# 007 — Consolidar execução de ferramentas e resolução segura de segredos

**Status:** pending  
**Tipo:** implementation  
**Branch de execução:** `development_tools-to-agent-consolidation`  
**Baseline obrigatória:** `development` em `209cf8147f87a2e9949fec33a34429ab70f166b5`

## Objetivo

Criar adapters agent para HTTP, templates, timeout, risco e resolução assíncrona de segredos.

## Contexto observado

O executor atual está no use case. `_resolve_headers` é síncrono, mas `SecretRepository.get_by_name` é assíncrono e exige project_id/name; a chamada atual não fornece esses argumentos.

## Pré-condições

- spec 006 concluída

## Estado atual a detectar

Execute a partir da raiz do repositório:

```bash
test "$(git branch --show-current)" = "development_tools-to-agent-consolidation"
git merge-base --is-ancestor 209cf8147f87a2e9949fec33a34429ab70f166b5 HEAD
git status --short
sed -n "240,380p" src/modules/tools/application/use_cases/tools_use_cases.py
rg -n "get_by_name\(|decrypt_secret|\{\{secret:" src/modules/tools src/modules/agent tests
```

Persistir as descobertas em `specs/tools-to-agent-consolidation/execution/inventory/`. Não substituir evidência por suposição.

## Alterações permitidas

- src/modules/agent/infra/adapters/**
- src/modules/agent/application/ports/**
- tests/unit/agent/**
- tests/integration/agent/**

## Alterações proibidas

- resolver segredo síncrono
- logar headers
- network sem policy
- writes cross-module

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

1. Implementar HttpToolExecutor.
2. Resolver segredo async por project_id+name.
3. Centralizar templates/inputs.
4. Preservar timeout/parsing.
5. Aplicar risco/allowlist/SSRF existente ou bloquear gap.
6. Sanitizar logs/erros/traces.
7. Usar ports/eventos para efeitos externos.

## Testes obrigatórios

- secret async
- timeout/request error
- redaction
- template
- SSRF/policy

## Validação

```bash
ruff check src/modules/agent/infra/adapters src/modules/agent/application/ports tests
pytest tests/unit/agent -q
pytest tests/integration/agent -q
```

Registrar comandos, códigos de saída e resultados em `execution/runtime.md`.

## Critérios de aceitação

- sem plaintext
- bug get_by_name corrigido
- executor fora de use case
- HTTP compatível

## Rollback

- feature flag/composer pode voltar ao executor legado

## Atualização obrigatória do runtime

Registrar status final, arquivos alterados, discovery, validações, códigos de saída, critérios comprovados, riscos residuais e próxima spec recomendada.
