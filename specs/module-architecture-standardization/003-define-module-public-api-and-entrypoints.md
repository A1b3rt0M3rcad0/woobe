# 003 — define-module-public-api-and-entrypoints

## Tipo

architecture

## Objetivo

Definir como bootstrap, rotas, workers e testes podem acessar um módulo sem importar internals.

## Contexto

A ausência de API pública explícita incentiva imports arbitrários entre bounded contexts.

## Pré-condições

- 001-002 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
rg "modules\.[a-z_]+\.(domain|application|infra|presentation)" src/modules tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/<module>/__init__.py
- event contracts publicados por envelope

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

1. Definir que rotas são registradas pelo bootstrap.
2. Definir registries de workers como entrypoint técnico.
3. Definir eventos como contratos de integração, sem expor entities.
4. Definir que IDs externos são opacos.
5. Criar teste para imports públicos.

## Contratos esperados

- Nenhum módulo consumidor importa application/domain/infra/presentation de outro.
- Bootstrap pode importar presentation.routes e infra.workers.registry.

## Testes obrigatórios

- tests/architecture/test_public_module_entrypoints.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- teste lista apenas exceções de composição no bootstrap
- nenhum import cross-module de internals permanece no estado final

## Rollback

1. Remover entrypoints criados e restaurar imports anteriores enquanto a allowlist permanecer.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `003`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `004`.
