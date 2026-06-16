# 009 — define-incremental-migration-and-runtime-protocol

## Tipo

architecture

## Objetivo

Definir protocolo operacional, shims, allowlist, rollback e atualização obrigatória do runtime.

## Contexto

A refatoração afeta muitos imports e rotas; execução sem memória operacional aumenta risco de big bang.

## Pré-condições

- 000-008 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
test -f specs/module-architecture-standardization/execution/runtime.md
git status --short
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- execution/runtime.md
- allowlists temporárias
- shims de import/rota

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

1. Definir pending/in_progress/completed/blocked/skipped.
2. Exigir uma spec por commit ou lote atomicamente reversível.
3. Exigir shim junto com spec de remoção.
4. Proibir remoção de path antigo antes de rg e testes.
5. Registrar SHA, comandos e riscos.

## Contratos esperados

- Runtime é fonte operacional.
- Allowlist tem path, motivo, owner e expiry spec.
- Shim não contém regra de negócio.

## Testes obrigatórios

- tests/architecture/test_runtime_manifest_consistency.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- runtime contém 000-109
- cada shim aponta para spec de remoção
- nenhuma spec física precede discovery

## Rollback

1. Restaurar runtime inicial e remover protocolo sem tocar código.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `009`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `010`.
