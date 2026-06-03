---
name: models-schemas-migrations
description: Defines how SQLAlchemy models are organized by database schema per module and how migrations should follow model changes.
---

# Models por Schema e Organização das Migrations

## Objetivo

Definir o padrão de models e organização de banco para o projeto.

Cada módulo terá suas tabelas dentro de um schema próprio no banco de dados.

A pasta `migrations/` será usada para controlar a evolução estrutural do banco.

Esta skill não precisa explicar ferramenta de migration em detalhe.

## Ideia principal

O backend será um monólito modular.

No código, cada módulo fica separado.

No banco, cada módulo também fica separado por schema.

Exemplo:

```txt
identity.users
identity.organizations

core.projects
core.api_keys

ai.agents
ai.provider_credentials

knowledge.documents
knowledge.document_chunks
```

## Schemas do banco

Schemas esperados:

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

Cada schema representa uma área modular do sistema.

## Regra central

Cada módulo deve criar e manter seus próprios models dentro de:

```txt
src/modules/<module_name>/infra/models.py
```

Exemplo:

```txt
src/modules/identity/infra/models.py
src/modules/core/infra/models.py
src/modules/ai/infra/models.py
```

## BaseModel compartilhado

O `Base` e o `BaseModel` devem ficar em:

```txt
src/shared/infra/database/base.py
```

Esse arquivo deve conter a base comum para todos os models.

Exemplo esperado:

```python
from datetime import datetime, UTC
from uuid import UUID
import uuid6

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BaseModel(Base):
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid6.uuid7)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        server_onupdate=func.now(),
    )
```

Todos os models concretos devem herdar de `BaseModel`.

## Como definir schema no model

Cada model deve declarar seu schema usando `__table_args__`.

Exemplo:

```python
class ProjectModel(BaseModel):
    __tablename__ = "projects"
    __table_args__ = {"schema": "core"}
```

Isso significa que a tabela real será:

```txt
core.projects
```

## Exemplo por módulo

### Identity

```python
class UserModel(BaseModel):
    __tablename__ = "users"
    __table_args__ = {"schema": "identity"}
```

Tabela real:

```txt
identity.users
```

### Core

```python
class ApiKeyModel(BaseModel):
    __tablename__ = "api_keys"
    __table_args__ = {"schema": "core"}
```

Tabela real:

```txt
core.api_keys
```

### AI

```python
class AgentModel(BaseModel):
    __tablename__ = "agents"
    __table_args__ = {"schema": "ai"}
```

Tabela real:

```txt
ai.agents
```

## Nomenclatura dos models

Models SQLAlchemy devem usar sufixo `Model`.

Exemplos:

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

Entidades de domínio não usam esse sufixo.

Exemplo:

```txt
Project = entidade de domínio
ProjectModel = model SQLAlchemy
```

## Regra de separação entre Entity e Model

Entity pertence ao domínio.

Model pertence à infra.

Exemplo:

```txt
src/modules/core/domain/entities.py
  Project

src/modules/core/infra/models.py
  ProjectModel
```

Não misturar os dois.

## Mappers

Conversão entre model e entity deve ficar em:

```txt
src/modules/<module_name>/infra/mappers.py
```

Exemplo:

```txt
ProjectModel → Project
Project → ProjectModel
```

Não colocar conversão dentro do controller.

Não colocar conversão dentro da entity.

## Repositories

Repositories concretos devem usar os models do próprio módulo.

Exemplo:

```txt
src/modules/core/infra/repositories.py
  SQLAlchemyProjectRepository
```

Esse repository manipula:

```txt
core.projects
```

A interface do repository fica no domínio:

```txt
src/modules/core/domain/repositories.py
```

## Relação entre schemas

É permitido ter foreign keys entre schemas quando fizer sentido.

Exemplo:

```txt
core.projects.organization_id → identity.organizations.id
ai.agents.project_id → core.projects.id
runtime.messages.session_id → runtime.sessions.id
```

Mas a regra arquitetural permanece:

```txt
um módulo não deve manipular diretamente as tabelas internas de outro módulo
```

Foreign key pode existir no banco.

Acesso direto entre infra de módulos deve ser evitado.

## Models e migrations

As migrations devem refletir os models.

Toda mudança estrutural em model deve ter migration correspondente.

Exemplos de mudanças que exigem migration:

```txt
criar schema
criar tabela
adicionar coluna
remover coluna
alterar tipo
criar índice
criar constraint
criar foreign key
```

## Organização da pasta migrations

A pasta deve ficar na raiz:

```txt
migrations/
  versions/
```

Uso esperado:

```txt
migrations/versions/
  cria_schemas_iniciais
  cria_identity_tables
  cria_core_tables
  cria_ai_tables
  cria_knowledge_tables
  cria_runtime_tables
  cria_tools_tables
  cria_metering_tables
  cria_billing_tables
  cria_observability_tables
  cria_events_tables
```

## Ordem recomendada das migrations iniciais

A ordem deve respeitar dependências entre schemas.

Ordem inicial recomendada:

```txt
1. criar schemas
2. criar identity
3. criar core
4. criar ai
5. criar knowledge
6. criar runtime
7. criar tools
8. criar metering
9. criar billing
10. criar observability
11. criar events
```

Motivo:

```txt
core depende de identity
ai depende de core
knowledge depende de core e ai
runtime depende de core e ai
tools depende de core e ai
metering depende de core e ai
billing depende de identity
observability depende de core, ai e runtime
events pode ser independente, mas pode ser criado no início também
```

Se preferir, `events` pode ser criado logo depois dos schemas, porque será usado por todos.

Ordem alternativa aceitável:

```txt
1. criar schemas
2. criar events
3. criar identity
4. criar core
5. criar ai
6. criar knowledge
7. criar runtime
8. criar tools
9. criar metering
10. criar billing
11. criar observability
```

## Migration inicial de schemas

A primeira migration deve criar os schemas:

```sql
CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS ai;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS runtime;
CREATE SCHEMA IF NOT EXISTS tools;
CREATE SCHEMA IF NOT EXISTS metering;
CREATE SCHEMA IF NOT EXISTS billing;
CREATE SCHEMA IF NOT EXISTS observability;
CREATE SCHEMA IF NOT EXISTS events;
```

## Regra sobre nomes de tabelas

Dentro do model, usar nomes no plural.

Exemplos:

```txt
users
organizations
projects
api_keys
agents
documents
document_chunks
sessions
messages
tools
usage_events
subscriptions
outbox_events
inbox_events
```

Não usar prefixo do módulo no nome da tabela, porque o schema já cumpre esse papel.

Correto:

```txt
core.projects
```

Errado:

```txt
core.core_projects
```

## Regra sobre índices e constraints

Índices e constraints devem ter nomes explícitos.

Exemplos:

```txt
idx_core_projects_organization_id
idx_ai_agents_project_id
idx_runtime_messages_session_id
uq_core_projects_organization_slug
uq_identity_users_email
```

## Regra sobre JSON

Campos flexíveis podem usar JSON/JSONB em models técnicos.

Exemplos:

```txt
metadata
settings
config
input_schema
output_schema
payload
```

Mas não usar JSON para tudo.

Campos importantes para busca, filtro, status e relacionamento devem ser colunas explícitas.

## Regra sobre UUID

Todas as tabelas principais devem usar UUID como primary key.

Preferência:

```txt
UUIDv7
```

Motivo:

```txt
ordenação temporal melhor
boa distribuição
adequado para sistemas distribuídos
```

## Resultado esperado

Depois desta skill, o projeto deve ter o padrão claro:

```txt
shared define Base e BaseModel
cada módulo define seus models em infra/models.py
cada model declara seu schema
migrations ficam na raiz
migrations criam schemas e tabelas em ordem
models e migrations evoluem juntos
```

## Não fazer nesta skill

```txt
Não implementar todos os models reais ainda.
Não criar todas as migrations reais ainda.
Não criar repositories.
Não criar controllers.
Não criar use cases.
Não criar regra de negócio.
```

Esta skill define apenas o padrão de models por schema e organização das migrations.
