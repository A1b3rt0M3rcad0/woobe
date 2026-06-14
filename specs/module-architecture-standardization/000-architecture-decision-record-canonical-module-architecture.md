# 000 — architecture-decision-record-canonical-module-architecture

## Tipo

architecture

## Objetivo

Registrar a decisão mandatória de usar uma arquitetura canônica em todos os módulos de domínio, tomando `agent` como referência a ser estabilizada.

## Contexto

A branch possui um `agent` estruturalmente mais avançado e módulos legados com `service/` e `infra` planos. Sem ADR, a padronização tende a virar apenas movimentação de arquivos.

## Pré-condições

- branch project-rai-playground_module-architecture-standardization disponível
- nenhuma spec anterior

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
find src/modules -maxdepth 4 -type d | sort
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- specs/module-architecture-standardization/000-*.md
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

1. Documentar contexto, decisão, status accepted e consequências.
2. Definir que cada módulo continua sendo bounded context independente.
3. Definir agent como referência estrutural, não como código a copiar cegamente.
4. Rejeitar microservices, shared domain e acesso cross-module.
5. Registrar ordem de migração.

## Contratos esperados

- Camadas canônicas: domain, application, infra, presentation.
- Direção: presentation -> application -> domain; infra implementa ports.
- Integração cross-module somente Outbox/RabbitMQ/Inbox.
- FK cross-module proibida.

## Testes obrigatórios

- tests/architecture/test_adr_presence.py::test_canonical_module_adr_exists

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- arquivo ADR existe e contém status accepted
- ADR cita todos os módulos-alvo
- ADR proíbe FK e imports cross-module

## Rollback

1. Reverter somente o ADR e a linha correspondente em runtime.md; nenhuma alteração de código deve existir.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `000`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `001`.
