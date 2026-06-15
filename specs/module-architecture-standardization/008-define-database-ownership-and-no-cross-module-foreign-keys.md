# 008 — define-database-ownership-and-no-cross-module-foreign-keys

## Tipo

database

## Objetivo

Tornar explícita e testável a proibição de FKs físicas entre módulos.

## Contexto

A branch contém FKs de core/billing/metering/observability/tools para tabelas de outros módulos e referências legadas a ai/runtime.

## Pré-condições

- 005 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
rg "ForeignKey\(" src/modules -g "*.py"
rg "create_foreign_key|FOREIGN KEY" migrations -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- tests/architecture/test_database_boundaries.py
- inventário database-ownership.md

## Alterações proibidas

- não fundir bounded contexts apenas para igualar diretórios
- não criar base repository/UoW genérico com semântica de domínio
- não executar rename destrutivo de tabela ou coluna sem expand-migrate-contract
- não alterar regra de negócio de outro módulo
- não importar internals de outro módulo
- não mover domínio para shared
- não colocar worker concreto em src/workers ou shared/workers
- não alterar contrato público sem shim/deprecation e teste de compatibilidade
- não criar comunicação síncrona direta entre módulos para mudança de estado
- não criar Foreign Key física para tabela pertencente a outro módulo

## Plano de implementação

1. Classificar cada FK como intra-module ou cross-module.
2. Permitir apenas intra-module no estado final.
3. Definir UUID externo opaco e índice local.
4. Definir projeção local alimentada por Inbox quando integridade semântica for necessária.
5. Definir consulta pg_constraint para validação.

## Contratos esperados

- FK intra-module permitida.
- FK cross-module bloqueia conclusão.
- Coluna externa não cria relationship SQLAlchemy cross-module.

## Testes obrigatórios

- tests/architecture/test_no_cross_module_foreign_keys.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- inventário lista todas as FKs
- teste detecta models e migrations
- referências ai/runtime classificadas críticas

## Rollback

1. Reverter apenas testes/documentação; não remover constraints nesta spec.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `008`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `009`.
