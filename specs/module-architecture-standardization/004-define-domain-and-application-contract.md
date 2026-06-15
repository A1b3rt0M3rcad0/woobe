# 004 — define-domain-and-application-contract

## Tipo

architecture

## Objetivo

Definir responsabilidades de domain, use cases, handlers, DTOs e composers.

## Contexto

Os módulos legados concentram DTOs/use cases em `service/`; a migração precisa impedir simples renomeação sem separação.

## Pré-condições

- 001-003 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules -path "*/service/*" -type f | sort
rg "class .*UseCase|class .*Handler|class .*DTO|BaseModel" src/modules -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- application/dtos
- application/use_cases
- application/handlers
- application/composers
- domain/*

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

1. Definir use case como orquestração transacional de domínio próprio.
2. Definir handler de Inbox como adapter de evento para use case.
3. Definir composer como assembly sem regra de negócio.
4. Definir DTO sem dependência de FastAPI/SQLAlchemy.
5. Definir domain services apenas para regra de domínio real.

## Contratos esperados

- Use cases recebem ports/interfaces.
- Composers podem instanciar infra própria.
- Controllers criam DTOs e mapeiam Response.
- Handlers nunca são chamados diretamente por outro módulo.

## Testes obrigatórios

- tests/architecture/test_application_boundaries.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- nenhum use case importa FastAPI ou SQLAlchemy
- nenhum composer contém decisão de domínio
- DTOs não ficam em shared

## Rollback

1. Restaurar imports/paths anteriores por shim temporário.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `004`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `005`.
