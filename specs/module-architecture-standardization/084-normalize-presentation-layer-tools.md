# 084 — normalize-presentation-layer-tools

## Tipo

refactor

## Objetivo

Normalizar presentation de `tools` em routes, controllers, schemas e mappers.

## Contexto

O módulo `tools` será padronizado sem perder ownership de domínio. Estado conhecido: Tool, Secret; tabelas tools.tools, tools.secrets; cross-FKs: tools.tools.project_id -> core.projects.id; tools.tools.agent_id -> ai.agents.id (legada); tools.secrets.project_id -> core.projects.id.

## Pré-condições

- 083 completed

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

1. Congelar OpenAPI/contratos atuais.
2. Atualizar controllers para application DTOs/use cases.
3. Manter routes finas.
4. Mover schemas/mappers para paths canônicos.
5. Adicionar testes HTTP de compatibilidade.

## Contratos esperados

- Bounded context `tools` continua independente.
- Entidades conhecidas: Tool, Secret.
- Tabelas conhecidas: tools.tools, tools.secrets.
- Referências cross-module a tratar: tools.tools.project_id -> core.projects.id; tools.tools.agent_id -> ai.agents.id (legada); tools.secrets.project_id -> core.projects.id.
- Rotas a preservar: rotas de tools e secrets, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- Controllers implementam Controller.handle(Request)->Response.
- Routes apenas chamam composer/adapters.
- Prefixos/status/body preservados.

## Testes obrigatórios

- tests/modules/tools/contract/test_routes.py
- tests/modules/tools/unit/presentation/test_controllers.py

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

- OpenAPI não perde operações
- controller não importa repository/model
- rotas registradas uma vez

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `084`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `085`.
