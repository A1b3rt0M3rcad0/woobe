# 023 — normalize-agent-composers-and-controllers

## Tipo

refactor

## Objetivo

Garantir composers somente para assembly e controllers somente para transporte.

## Contexto

O agent é a referência, porém a branch mostra coexistência de AgentUnitOfWork e PostgresUnitOfWork genérico e arquivos herdados com nomenclatura antiga.

## Pré-condições

- 022 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/agent -maxdepth 5 -type f -print -exec wc -l {} \;
rg "PostgresUnitOfWork|modules\.(ai|knowledge|runtime)" src/modules/agent tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/agent/**
- tests/modules/agent/**
- tests/architecture/**
- execution/runtime.md

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

1. Comparar estado atual com a estrutura canônica e inventários 010-019.
2. Aplicar somente mudanças pertencentes ao objetivo desta spec.
3. Preservar comportamento e contratos HTTP; criar shim explícito quando path público mudar.
4. Eliminar imports legados ai/knowledge/runtime no escopo migrado.
5. Adicionar testes antes de remover compatibilidade.
6. Registrar gaps restantes e bloquear replicação quando houver violação crítica.

## Contratos esperados

- AgentUnitOfWork coordena somente repositories do agent, Inbox e Outbox.
- Composers não instanciam repository de outro módulo.
- Arquivos de domínio não dependem de SQLAlchemy/FastAPI.
- Subpacote infra/llm permanece específico do agent.

## Testes obrigatórios

- tests/modules/agent/test_normalize_agent_composers_and_controllers.py
- tests/architecture/test_agent_reference_architecture.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules/agent -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- objetivo `Garantir composers somente para assembly e controllers somente para transporte.` coberto por código e teste
- nenhum import modules.ai/knowledge/runtime no agent
- rotas existentes continuam registradas
- runtime atualizado

## Rollback

1. Restaurar arquivos do agent ao commit anterior.
2. Reativar shims removidos nesta spec.
3. Não reverter migrations já utilizadas sem executar downgrade validado.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `023`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `024`.
