---
name: root-folder-organization
description: Defines the root project folder structure, including src, shared, modules, workers, migrations, tests, and scripts.
---

# Organização de Pastas na Raiz do Projeto

## Objetivo

Definir a organização geral da raiz do backend.

Esta skill explica como as pastas principais se organizam acima dos módulos.

Não implementar regra de negócio nesta skill.

## Estrutura raiz esperada

```txt
project-root/
  src/
    main.py

    shared/
      domain/
      application/
      infra/
      presentation/
      workers/

    modules/
      identity/
      core/
      ai/
      knowledge/
      runtime/
      tools/
      metering/
      billing/
      observability/
      events/

    workers/

  migrations/

  tests/

  scripts/

  pyproject.toml
  README.md
  .env.example
```

## `src/`

Pasta principal da aplicação.

Tudo que pertence ao runtime do backend deve ficar dentro de `src`.

```txt
src/
  main.py
  shared/
  modules/
  workers/
```

## `src/main.py`

Arquivo de entrada da aplicação.

Responsabilidade:

```txt
criar app FastAPI
registrar routers
registrar middlewares
registrar exception handlers
configurar lifecycle da aplicação
```

Não deve conter regra de negócio.

Não deve conter queries.

Não deve instanciar manualmente todos os use cases.

## `src/shared/`

Código compartilhado entre módulos.

Só deve conter coisas genéricas, reutilizáveis e sem regra específica de um módulo.

Estrutura:

```txt
src/shared/
  domain/
    objects.py
    errors.py
    enums.py
    http.py

  application/
    pagination.py
    dtos.py

  infra/
    database/
      base.py
      session.py
      session_manager.py

    repositories/
      base_repository.py

    config.py
    crypto.py

  presentation/
    dependencies.py
    errors.py
    responses.py

  workers/
    base_worker.py
```

## Papel do `shared/domain`

Objetos puros e reutilizáveis.

Exemplos:

```txt
CursorPage
HttpRequest
HttpResponse
DomainError
```

Regra:

```txt
shared/domain não importa FastAPI
shared/domain não importa SQLAlchemy
shared/domain não conhece módulos específicos
```

## Papel do `shared/application`

Objetos e utilidades reutilizáveis pela camada de aplicação/serviço.

Exemplos:

```txt
paginação genérica
DTOs base
interfaces base
tipos comuns
```

Não deve conter regra específica de `identity`, `core`, `ai` etc.

## Papel do `shared/infra`

Infraestrutura genérica.

Exemplos:

```txt
Base SQLAlchemy
BaseModel
SessionManager
engine/session factory
BaseRepository
crypto
settings/config
```

Essa camada pode conter código técnico compartilhado.

Exemplo:

```txt
src/shared/infra/database/base.py
src/shared/infra/database/session_manager.py
src/shared/infra/repositories/base_repository.py
```

## Papel do `shared/presentation`

Itens HTTP globais.

Exemplos:

```txt
exception handlers globais
response helpers
dependencies comuns
CurrentUser
ProjectContext
```

Regra:

```txt
shared/presentation pode conhecer FastAPI
mas não deve ter regra de negócio específica
```

## Papel do `shared/workers`

Base para workers.

Exemplos:

```txt
BaseWorker
WorkerResult
WorkerStatus
retry helpers
```

Não deve conter worker concreto de domínio.

## `src/modules/`

Contém os módulos de negócio.

Cada módulo é isolado e segue a estrutura definida na Skill 1.

```txt
src/modules/<module_name>/
  application/
  presentation/
  service/
  domain/
  infra/
```

Módulos iniciais:

```txt
identity
core
ai
knowledge
runtime
tools
metering
billing
observability
events
```

## Regra dos módulos

Cada módulo deve concentrar sua própria regra, seus próprios models, seus próprios repositories e seus próprios controllers.

Regra:

```txt
um módulo não deve acessar infra de outro módulo diretamente
```

Exemplo ruim:

```txt
runtime importa ai.infra.repositories diretamente
```

Exemplo melhor:

```txt
runtime recebe uma interface/serviço necessário
ou reage a eventos
ou chama um use case público bem definido
```

## `src/workers/`

Workers concretos da aplicação.

Exemplos futuros:

```txt
src/workers/outbox_publisher_worker.py
src/workers/inbox_consumer_worker.py
src/workers/inbox_dispatcher_worker.py
src/workers/document_ingestion_worker.py
src/workers/embedding_worker.py
src/workers/usage_aggregation_worker.py
```

Regra:

```txt
workers controlam execução, loop, batch e retry
workers não devem conter regra de negócio principal
workers chamam services/use cases dos módulos
```

## `migrations/`

Pasta das migrações do banco.

Ela deve ficar fora de `src`.

Estrutura esperada:

```txt
migrations/
  versions/
```

As migrações devem refletir os schemas e models definidos nos módulos.

A pasta `migrations` não deve conter regra de negócio.

## `tests/`

Pasta de testes.

Estrutura recomendada:

```txt
tests/
  unit/
  integration/
  e2e/
```

Uso esperado:

```txt
unit = testa domain e service sem banco real
integration = testa repositories e banco
e2e = testa fluxos HTTP completos
```

## `scripts/`

Scripts auxiliares.

Exemplos:

```txt
scripts/create_initial_data.py
scripts/run_worker.py
scripts/seed_local.py
```

Scripts não devem virar parte central da aplicação.

## Regra de dependência

Direção esperada:

```txt
presentation → service → domain
infra → domain
application → service/infra wiring
workers → service/use cases
shared → não depende dos módulos
```

## Regra importante sobre `shared`

`shared` não pode virar lixeira.

Só entra em `shared` quando:

```txt
é usado por mais de um módulo
não pertence claramente a um módulo específico
não contém regra de negócio específica
```

Se o código pertence a um módulo, deve ficar no módulo.

## Resultado esperado

Depois desta skill, o projeto deve ter a estrutura raiz criada:

```txt
src/
  main.py
  shared/
  modules/
  workers/

migrations/
tests/
scripts/
```

Com arquivos base vazios ou com docstrings curtas explicando seu papel.

## Não fazer nesta skill

```txt
Não implementar endpoints.
Não implementar models reais.
Não implementar migrations reais.
Não implementar workers reais.
Não implementar regra de negócio.
Não implementar conexão real com banco.
```

Esta skill define apenas a organização macro de pastas.
