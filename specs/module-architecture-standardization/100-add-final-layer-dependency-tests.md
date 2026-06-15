# 100 — add-final-layer-dependency-tests

## Tipo

test

## Objetivo

Consolidar testes finais de direção de dependências por camada.

## Contexto

Fase final de enforcement e encerramento operacional.

## Pré-condições

- 090-099 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
git status --short
rg "modules\.[a-z_]+\.(service|infra\.(models|repositories|mappers))" src tests -g "*.py"
rg "ForeignKey\("(identity|core|agent|billing|metering|observability|tools)\." src/modules -g "*.py"
find src/modules -maxdepth 5 -type f | sort
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- tests/**
- src/main.py
- migrations/env.py
- src/modules/**
- src/shared/**
- specs/module-architecture-standardization/**

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

1. Executar testes específicos antes da suíte completa.
2. Remover allowlists apenas quando rg/AST estiver limpo.
3. Validar Alembic em banco descartável.
4. Validar startup FastAPI e OpenAPI.
5. Validar workers registráveis.
6. Persistir evidências no relatório final.

## Contratos esperados

- Todos os módulos seguem o contrato canônico.
- Nenhum path service/ legado permanece.
- Nenhuma FK cross-module permanece.
- Nenhum worker concreto está em shared/src/workers.
- Runtime e manifesto refletem estado real.

## Testes obrigatórios

- tests/architecture/**
- tests/modules/**
- tests/integration/messaging/**
- tests/contract/**

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules -q
pytest tests/integration -q
pytest tests/contract -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
python -c "from src.main import create_app; app=create_app(); print(len(app.routes))"
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- Consolidar testes finais de direção de dependências por camada.
- todos os comandos executados têm exit code 0 ou pendência bloqueadora registrada
- allowlist final vazia
- relatório final existe

## Rollback

1. Restaurar somente a última alteração estrutural.
2. Reativar shim apenas se contrato público quebrar.
3. Marcar migração como blocked; nunca declarar completed com validação falha.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `100`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `101`.
