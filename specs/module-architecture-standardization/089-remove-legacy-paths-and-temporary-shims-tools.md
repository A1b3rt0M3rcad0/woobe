# 089 — remove-legacy-paths-and-temporary-shims-tools

## Tipo

cleanup

## Objetivo

Remover paths legados e shims temporários de `tools` após comprovar migração.

## Contexto

O módulo `tools` será padronizado sem perder ownership de domínio. Estado conhecido: Tool, Secret; tabelas tools.tools, tools.secrets; cross-FKs: tools.tools.project_id -> core.projects.id; tools.tools.agent_id -> ai.agents.id (legada); tools.secrets.project_id -> core.projects.id.

## Pré-condições

- 088 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/tools -maxdepth 5 -type f | sort
rg "modules\.tools|from modules\.|ForeignKey\(|event_type|UnitOfWork" src/modules/tools tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/tools/**
- tests/modules/tools/**
- tests/architecture/**
- migrations/versions/* apenas quando explicitamente necessário
- execution/runtime.md

## Alterações proibidas

- não fundir bounded contexts apenas para igualar diretórios
- não criar base repository/UoW genérico com semântica de domínio
- não executar rename destrutivo de tabela ou coluna sem expand-migrate-contract
- não modificar tabelas de outro módulo
- não usar o agent como repository/service remoto
- não alterar regra de negócio de outro módulo
- não importar internals de outro módulo
- não mover domínio para shared
- não colocar worker concreto em src/workers ou shared/workers
- não alterar contrato público sem shim/deprecation e teste de compatibilidade
- não criar comunicação síncrona direta entre módulos para mudança de estado
- não criar Foreign Key física para tabela pertencente a outro módulo

## Plano de implementação

1. Executar rg por service/ e infra paths planos.
2. Remover shims sem consumidores.
3. Remover arquivos antigos.
4. Atualizar exports e migrations/env.py.
5. Remover allowlist do módulo.
6. Executar suíte completa.

## Contratos esperados

- Bounded context `tools` continua independente.
- Entidades conhecidas: Tool, Secret.
- Tabelas conhecidas: tools.tools, tools.secrets.
- Referências cross-module a tratar: tools.tools.project_id -> core.projects.id; tools.tools.agent_id -> ai.agents.id (legada); tools.secrets.project_id -> core.projects.id.
- Rotas a preservar: rotas de tools e secrets, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- `src/modules/tools/service` ausente.
- `src/modules/{mod}/infra/models.py` e repositories.py ausentes.

## Testes obrigatórios

- tests/architecture/test_no_legacy_tools_paths.py
- tests/modules/tools/**

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules/tools -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- rg por imports legados retorna vazio
- allowlist do módulo vazia
- suíte completa passa
- nenhuma rota removida

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `089`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `090`.
