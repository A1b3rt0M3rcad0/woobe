# 002 — define-canonical-module-directory-contract

## Tipo

architecture

## Objetivo

Definir a árvore canônica e distinguir diretórios obrigatórios de capacidades opcionais.

## Contexto

Copiar todos os subpacotes do agent para todo módulo criaria abstrações vazias; o contrato deve padronizar responsabilidades.

## Pré-condições

- 000-001 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/agent -maxdepth 4 -type f | sort
find src/modules/{identity,core,billing,metering,observability,tools} -maxdepth 4 -type f | sort
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- documentação de estrutura
- tests/architecture/test_module_structure.py

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

1. Publicar árvore canônica.
2. Marcar database como obrigatório para módulos persistentes.
3. Marcar messaging/workers como obrigatório quando há Outbox/Inbox.
4. Permitir subpacotes específicos, como agent/infra/llm.
5. Proibir arquivos vazios usados apenas para satisfazer estética.

## Contratos esperados

- src/modules/<module>/ | ├── application | │   ├── composers | │   ├── dtos | │   ├── handlers | │   └── use_cases | ├── domain | │   ├── entities.py | │   ├── enums.py | │   ├── errors.py | │   ├── events.py | │   ├── repositories.py | │   ├── services.py | │   └── value_objects.py | ├── infra | │   ├── database | │   │   ├── mappers.py | │   │   ├── models.py | │   │   ├── repositories.py | │   │   └── unit_of_work.py | │   ├── messaging | │   │   ├── consumers.py | │   │   ├── event_mappers.py | │   │   └── publishers.py | │   └── workers | │       ├── inbox_consumer.py | │       ├── inbox_processor.py | │       ├── outbox_dispatcher.py | │       └── registry.py | └── presentation |     ├── controllers |     ├── mappers.py |     ├── routes.py |     └── schemas.py
- service/ é legado e será removido
- infra/models.py e infra/repositories.py planos são legados

## Testes obrigatórios

- tests/architecture/test_module_structure.py::test_persisted_modules_follow_canonical_structure

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- estrutura alvo documentada
- teste distingue obrigatório/condicional
- agent-specific infra não vira shared

## Rollback

1. Reverter teste e documento sem mover arquivos.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `002`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `003`.
