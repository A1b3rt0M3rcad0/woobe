---
name: modular-architecture-standard
description: Defines the internal folder structure and layer responsibilities for each backend module.
---

# Modular Module Architecture Standard

## Objetivo

Criar e padronizar a estrutura interna de cada módulo do backend.

Esta skill **não deve implementar regra de negócio**, **não deve criar models reais**, **não deve criar endpoints reais** e **não deve criar tabelas reais**.

O objetivo é apenas criar a organização arquitetural base dos módulos.

## Stack

- Python
- FastAPI
- SQLAlchemy async
- Pydantic
- Modular Monolith
- Repository Pattern
- PostgreSQL schemas por módulo

## Módulos base

Criar a estrutura para os módulos:

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

## Estrutura obrigatória de cada módulo

Para cada módulo, criar:

```txt
src/modules/<module_name>/
  application/
    __init__.py
    dependencies.py
    adapters.py
    providers.py
    config.py

  presentation/
    __init__.py
    controllers.py
    schemas.py

  service/
    __init__.py
    dtos.py
    use_cases.py

  domain/
    __init__.py
    entities.py
    objects.py
    services.py
    errors.py
    enums.py
    repositories.py

  infra/
    __init__.py
    models.py
    repositories.py
    mappers.py

  __init__.py
```

## Responsabilidade das camadas

### application/

Camada relacionada à integração da aplicação com FastAPI, conexões, adapters, providers e wiring técnico.

Aqui ficam:

```txt
FastAPI dependencies
adapters
providers
configurações técnicas do módulo
injeção de dependência
wiring entre service e infra
```

Pode importar FastAPI.

Pode importar services/use cases.

Pode importar adapters técnicos.

Não deve conter regra de negócio principal.

Não deve acessar banco diretamente para executar regra de negócio.

---

### presentation/

Camada de controladores HTTP.

Aqui ficam:

```txt
controllers.py
schemas.py
```

Responsabilidade:

```txt
receber HTTP request
validar entrada com schemas
chamar service/use case
retornar response
```

Pode importar FastAPI.

Pode importar schemas.

Pode importar services/use cases.

Não acessa banco diretamente.

Não implementa regra de negócio.

---

### service/

Camada dos casos de uso e application services.

Aqui ficam:

```txt
dtos.py
use_cases.py
```

Responsabilidade:

```txt
orquestrar regra de aplicação
executar casos de uso
chamar repositories por interfaces
chamar domain services quando necessário
emitir eventos via ports/repositories
```

Exemplos futuros:

```txt
CreateProjectUseCase
CreateApiKeyUseCase
CreateAgentUseCase
UploadDocumentUseCase
AskAgentUseCase
CreateToolUseCase
RecordUsageUseCase
```

Pode importar domain.

Pode importar interfaces de repositories.

Não deve importar FastAPI.

Não deve importar SQLAlchemy models.

Não deve depender diretamente de banco.

---

### domain/

Camada do núcleo do módulo.

Aqui ficam:

```txt
entities.py
objects.py
services.py
errors.py
enums.py
repositories.py
```

Responsabilidade:

```txt
entidades do domínio
value objects
enums
erros de domínio
services puros de domínio
interfaces/contratos de repositories
```

Não importa FastAPI.

Não importa SQLAlchemy.

Não acessa banco.

Não importa infra.

---

### infra/

Camada de implementação técnica persistente.

Aqui ficam:

```txt
models.py
repositories.py
mappers.py
```

Responsabilidade:

```txt
SQLAlchemy models
repositories concretos
mappers Model ↔ Entity
implementação real de persistência
```

Pode importar SQLAlchemy.

Pode importar domain.

Implementa interfaces definidas em `domain/repositories.py`.

## Fluxo padrão

```txt
HTTP request
→ presentation/controllers.py
→ service/use_cases.py
→ domain/repositories.py interface
→ infra/repositories.py implementação
→ infra/models.py
→ infra/mappers.py
→ retorna DTO
→ presentation/schemas.py response
```

## Regras obrigatórias

```txt
1. Controller não acessa banco diretamente.
2. Controller chama service/use case.
3. Service não importa FastAPI.
4. Service não importa SQLAlchemy model.
5. Domain não importa FastAPI.
6. Domain não importa SQLAlchemy.
7. Domain não importa infra.
8. Infra implementa repositories do domain.
9. Mappers ficam em infra/mappers.py.
10. Application faz dependencies, adapters, providers e wiring técnico.
11. Cada módulo escreve apenas no próprio schema.
12. Comunicação entre módulos deve acontecer por use case explícito ou events/outbox.
13. Evitar import circular.
14. Evitar dependência direta entre infra de módulos diferentes.
15. Não criar regra de negócio nesta skill.
16. Não criar endpoints reais nesta skill.
17. Não criar models reais nesta skill.
```

## Padrão de nomenclatura

### Entidades de domínio

```txt
User
Organization
Project
ApiKey
Agent
Document
Tool
UsageEvent
```

### SQLAlchemy models

```txt
UserModel
OrganizationModel
ProjectModel
ApiKeyModel
AgentModel
DocumentModel
ToolModel
UsageEventModel
```

### Interfaces de repositories

```txt
UserRepository
OrganizationRepository
ProjectRepository
ApiKeyRepository
AgentRepository
```

### Repositories concretos

```txt
SQLAlchemyUserRepository
SQLAlchemyOrganizationRepository
SQLAlchemyProjectRepository
SQLAlchemyApiKeyRepository
SQLAlchemyAgentRepository
```

### Use cases

```txt
CreateUserUseCase
CreateProjectUseCase
CreateApiKeyUseCase
CreateAgentUseCase
UpdateAgentUseCase
```

### DTOs

```txt
CreateProjectInput
CreateProjectOutput
CreateAgentInput
CreateAgentOutput
```

### Schemas HTTP

```txt
CreateProjectRequest
ProjectResponse
CreateAgentRequest
AgentResponse
```

## Resultado esperado

Depois desta skill, o projeto deve ter apenas a estrutura base:

```txt
src/modules/identity/
src/modules/core/
src/modules/ai/
src/modules/knowledge/
src/modules/runtime/
src/modules/tools/
src/modules/metering/
src/modules/billing/
src/modules/observability/
src/modules/events/
```

Cada módulo deve conter:

```txt
application/
presentation/
service/
domain/
infra/
__init__.py
```

Cada pasta deve conter seus arquivos base com docstrings curtas explicando sua responsabilidade.

## Não fazer nesta skill

```txt
Não implementar autenticação.
Não implementar projetos.
Não implementar agentes.
Não implementar banco real.
Não implementar endpoints reais.
Não implementar workers.
Não implementar outbox/inbox.
Não implementar repository base ainda.
Não implementar SQLAlchemy BaseModel ainda.
```

Esta skill é somente para padronizar a arquitetura interna dos módulos.
