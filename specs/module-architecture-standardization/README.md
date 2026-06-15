# Padronização Arquitetural dos Módulos — ProjectRAI

## Objetivo

Este pacote operacional padroniza os módulos `identity`, `core`, `billing`, `metering`, `observability` e `tools` na arquitetura estabilizada do módulo `agent`, sem fundir bounded contexts e sem big bang.

## Diagnóstico

O diagnóstico inicial foi feito na baseline `project-rai-playground`. A implementação destas specs deve ocorrer exclusivamente em `project-rai-playground_module-architecture-standardization`. Na baseline, `agent` já adotava uma estrutura em camadas mais explícita. Os demais módulos ainda usam combinações como `service/`, `infra/models.py` e `infra/repositories.py`. A inconsistência não é apenas visual:

- composers de diferentes módulos usam UoW genérico;
- FKs cruzam schemas de módulos;
- `metering`, `observability` e `tools` ainda referenciam schemas legados `ai`/`runtime`;
- eventos não têm nomenclatura/versionamento uniforme;
- Outbox/Inbox existem, mas workers/registries não seguem um contrato único;
- copiar o agent sem estabilizá-lo replicaria inconsistências, como coexistência de `AgentUnitOfWork` e `PostgresUnitOfWork` nos composers.

## Estrutura final

```text
src/modules/<module>/
├── application
│   ├── composers
│   ├── dtos
│   ├── handlers
│   └── use_cases
├── domain
│   ├── entities.py
│   ├── enums.py
│   ├── errors.py
│   ├── events.py
│   ├── repositories.py
│   ├── services.py
│   └── value_objects.py
├── infra
│   ├── database
│   │   ├── mappers.py
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── unit_of_work.py
│   ├── messaging
│   │   ├── consumers.py
│   │   ├── event_mappers.py
│   │   └── publishers.py
│   └── workers
│       ├── inbox_consumer.py
│       ├── inbox_processor.py
│       ├── outbox_dispatcher.py
│       └── registry.py
└── presentation
    ├── controllers
    ├── mappers.py
    ├── routes.py
    └── schemas.py
```

Diretórios representam responsabilidades. Capacidades específicas continuam locais: `agent/infra/llm` não deve ser criado nos demais módulos nem movido para `shared`.

## Regras decisivas

1. Cada módulo continua sendo um bounded context independente.
2. A direção é `presentation -> application -> domain`; infra implementa ports.
3. Mudança de estado entre módulos ocorre somente por Outbox/RabbitMQ/Inbox.
4. FK física cross-module é proibida; IDs externos são opacos.
5. Cada módulo tem UoW próprio e não coordena repositories externos.
6. Workers concretos ficam no módulo e delegam para application.
7. `shared` não contém domínio, DTOs de domínio ou handlers de negócio.
8. Rotas e contratos públicos permanecem compatíveis durante a migração.

## Como executar

1. Garantir que a branch `project-rai-playground_module-architecture-standardization` exista e esteja baseada no commit correto de `project-rai-playground`.
2. Fazer checkout de `project-rai-playground_module-architecture-standardization` e executar o guard abaixo:

   ```bash
   test "$(git branch --show-current)" = "project-rai-playground_module-architecture-standardization"
   git rev-parse HEAD
   ```
3. Copiar a pasta `specs/module-architecture-standardization` para o repositório.
4. Executar as specs em ordem numérica.
5. Antes de cada spec, confirmar pré-condições e marcar `in_progress` no runtime.
6. Executar todos os comandos aplicáveis e registrar evidências.
7. Marcar `completed` somente quando todos os critérios objetivos forem satisfeitos.
8. Uma spec bloqueada não deve ser pulada silenciosamente.

## Ordem de módulos

`agent baseline -> identity -> core -> billing -> metering -> observability -> tools`.

A ordem reduz dependências de migração e trata primeiro os produtores de identificadores usados como referências opacas.

## Artefatos de execução

- `execution/runtime.md`: memória operacional;
- `execution/inventory/*.md`: inventários gerados;
- `SOURCE_ANALYSIS.md`: evidências da inspeção inicial;
- `MANIFEST.md`: dependências e ordem.

## Condição de conclusão

A padronização só termina quando a spec 108 passa integralmente e a 109 registra relatório final. Estrutura de pastas isoladamente não caracteriza conclusão.
