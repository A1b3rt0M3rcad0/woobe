# 010 — create-module-file-inventory

## Tipo

discovery

## Objetivo

Produzir mapa completo de arquivos e diretórios por módulo.

## Contexto

Nenhuma movimentação física pode ocorrer sem inventário atual da branch.

## Pré-condições

- 000-009 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules -type f | sort
find tests -type f | sort
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- specs/module-architecture-standardization/execution/inventory/files.md
- execution/runtime.md

## Alterações proibidas

- não fundir bounded contexts apenas para igualar diretórios
- não criar base repository/UoW genérico com semântica de domínio
- não executar rename destrutivo de tabela ou coluna sem expand-migrate-contract
- não mover, renomear ou editar código de produção
- não alterar comportamento
- não alterar regra de negócio de outro módulo
- não importar internals de outro módulo
- não mover domínio para shared
- não colocar worker concreto em src/workers ou shared/workers
- não alterar contrato público sem shim/deprecation e teste de compatibilidade
- não criar comunicação síncrona direta entre módulos para mudança de estado
- não criar Foreign Key física para tabela pertencente a outro módulo

## Plano de implementação

1. Executar os comandos e persistir resultados em `files.md`.
2. Classificar cada item por módulo, camada, owner e risco.
3. Registrar informação ausente, comando necessário e risco de prosseguir.
4. Revisar divergências contra SOURCE_ANALYSIS.md.
5. Atualizar riscos e próxima spec.

## Contratos esperados

- Arquivo `files.md` com data, branch e SHA.
- Entradas devem citar paths concretos.
- Nenhuma conclusão baseada somente no nome do diretório.

## Testes obrigatórios

- tests/architecture/test_inventory_artifacts.py::test_files_md_exists

## Comandos de validação

```bash
test -s specs/module-architecture-standardization/execution/inventory/files.md
ruff check src tests
pytest tests/architecture -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- `files.md` existe e não está vazio
- SHA do inventário registrado
- lacunas possuem comando e risco explícitos

## Rollback

1. Remover somente o arquivo de inventário criado e restaurar runtime.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `010`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `011`.
