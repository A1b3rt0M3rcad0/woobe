---
name: session-manager-transactions
description: Defines how to use SessionManager to guarantee atomic transactions across repositories, outbox, inbox, use cases, and workers.
---

# Session Manager e Transações Atômicas

## Objetivo

Definir o padrão de uso do `SessionManager` para controlar transações no banco de dados.

A ideia central é:

```txt
ou tudo dentro da operação é salvo com sucesso
ou nada é salvo
```

Isso é essencial para:

```txt
outbox
inbox
casos de uso
workers
operações entre múltiplos repositories
```

## Problema que essa skill resolve

Sem controle transacional claro, pode acontecer:

```txt
1. O módulo salva o dado principal.
2. O sistema falha antes de salvar o evento na outbox.
3. O estado muda, mas o evento se perde.
```

Ou:

```txt
1. O dispatcher processa um inbox_event.
2. Aplica parte da mudança.
3. Falha antes de marcar inbox_event como processed.
4. O evento pode ser reprocessado e causar duplicação.
```

O `SessionManager` evita esse tipo de inconsistência quando usado corretamente.

## Código base do SessionManager

Criar este arquivo:

```txt
src/shared/infra/database/session_manager.py
```

Conteúdo:

```python
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker
from typing import Self, Optional


class SessionManager:

    def __init__(self, async_engine: AsyncEngine) -> None:
        self.__session: Optional[AsyncSession] = None
        self._async_engine = async_engine

    @property
    def session(self) -> AsyncSession:
        if self.__session:
            return self.__session
        raise RuntimeError("SessionManager not started")

    async def rollback(self) -> None:
        if self.__session:
            await self.__session.rollback()
            return
        raise RuntimeError("SessionManager not started")

    async def commit(self) -> None:
        if self.__session:
            await self.__session.commit()
            return
        raise RuntimeError("SessionManager not started")

    async def __aenter__(self) -> Self:
        async_session = async_sessionmaker(
            bind=self._async_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )()
        self.__session = async_session
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

        if self.__session:
            await self.__session.close()

        self.__session = None
```

## Regra principal

O `SessionManager` deve ser usado como contexto transacional:

```python
async with SessionManager(async_engine) as manager:
    session = manager.session

    # executar repositories e use cases usando esta mesma session
```

Se tudo der certo:

```txt
commit automático
```

Se qualquer erro acontecer:

```txt
rollback automático
```

## Regra crítica

Cada request, worker job ou operação transacional deve criar sua própria instância de `SessionManager`.

Não usar `SessionManager` como singleton global.

Correto:

```python
async with SessionManager(async_engine) as manager:
    ...
```

Errado:

```python
global_session_manager = SessionManager(async_engine)
```

Motivo:

```txt
AsyncSession não deve ser compartilhada entre requests, workers ou tarefas concorrentes.
```

## Como usar nos casos de uso

O service/use case deve receber repositories já criados com a mesma session.

Exemplo conceitual:

```python
async with SessionManager(async_engine) as manager:
    project_repository = SQLAlchemyProjectRepository(manager.session)
    outbox_repository = SQLAlchemyOutboxRepository(manager.session)

    use_case = CreateProjectUseCase(
        project_repository=project_repository,
        outbox_repository=outbox_repository,
    )

    result = await use_case.execute(input_data)
```

Assim, o caso de uso pode:

```txt
criar projeto
criar outbox_event
```

E ambos entram na mesma transação.

## Exemplo com outbox

Fluxo:

```txt
CreateProjectUseCase
→ cria core.projects
→ cria events.outbox_events
→ commit
```

Se falhar antes do commit:

```txt
nem projeto nem outbox_event são salvos
```

Exemplo:

```python
async with SessionManager(async_engine) as manager:
    project_repo = SQLAlchemyProjectRepository(manager.session)
    outbox_repo = SQLAlchemyOutboxRepository(manager.session)

    project = await project_repo.insert(project)

    await outbox_repo.insert(
        OutboxEvent(
            aggregate_type="project",
            aggregate_id=project.id,
            event_type="core.project_created",
            payload={
                "project_id": str(project.id),
                "organization_id": str(project.organization_id),
            },
        )
    )
```

Resultado esperado:

```txt
project + outbox_event salvam juntos
```

## Exemplo com inbox

Fluxo:

```txt
Dispatcher
→ lê inbox_event
→ executa handler
→ altera dados do módulo consumidor
→ marca inbox_event como processed
→ opcionalmente cria novo outbox_event
→ commit
```

Se falhar:

```txt
rollback em tudo
inbox_event não é marcado como processed
mudanças parciais não ficam salvas
```

Exemplo:

```python
async with SessionManager(async_engine) as manager:
    inbox_repo = SQLAlchemyInboxRepository(manager.session)
    billing_repo = SQLAlchemyBillingRepository(manager.session)
    outbox_repo = SQLAlchemyOutboxRepository(manager.session)

    inbox_event = await inbox_repo.get_pending_for_dispatch()

    await billing_repo.apply_event(inbox_event)

    await inbox_repo.mark_as_processed(inbox_event.id)

    await outbox_repo.insert(
        OutboxEvent(
            aggregate_type="billing",
            aggregate_id=inbox_event.id,
            event_type="billing.customer_created",
            payload={...},
        )
    )
```

Resultado esperado:

```txt
ou o handler inteiro conclui
ou nada é persistido
```

## Relação com Repository Pattern

Repositories não devem criar session própria.

Repositories devem receber a session de fora.

Correto:

```python
class SQLAlchemyProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
```

Errado:

```python
class SQLAlchemyProjectRepository:
    def __init__(self):
        self.session = create_new_session()
```

Motivo:

```txt
se cada repository cria sua própria session, não existe transação única.
```

## Regra de ouro para repositories

```txt
Repository não controla commit.
Repository não controla rollback.
Repository apenas usa a session recebida.
SessionManager controla commit e rollback.
```

O repository pode usar:

```txt
add
flush
execute
delete
```

Mas não deve chamar:

```txt
commit
rollback
close
```

## Onde usar SessionManager

Usar em:

```txt
FastAPI dependencies
workers
dispatchers
outbox publisher
inbox consumer
batch processors
scripts internos
```

## Onde não usar SessionManager

Não usar dentro de:

```txt
domain entities
domain services puros
repository methods
mappers
schemas
DTOs
```

## Uso em FastAPI

A camada `application/dependencies.py` pode criar o contexto transacional.

Exemplo conceitual:

```python
async def get_session_manager() -> AsyncIterator[SessionManager]:
    async with SessionManager(async_engine) as manager:
        yield manager
```

Controllers podem receber o manager por dependency e montar os use cases.

Mas a regra continua:

```txt
controller não acessa banco diretamente
controller monta/chama service/use case
repositories recebem manager.session
```

## Uso em workers

Workers também devem usar `SessionManager`.

Exemplo:

```python
async def run_outbox_worker() -> None:
    async with SessionManager(async_engine) as manager:
        outbox_repo = SQLAlchemyOutboxRepository(manager.session)
        events = await outbox_repo.get_pending_batch()
        ...
```

Para batches, cada lote deve ter uma transação clara.

Exemplo:

```txt
pega 100 eventos
publica
marca como published
commit
```

Se falhar:

```txt
rollback do lote
eventos continuam disponíveis para retry
```

## Cuidados importantes

### 1. Não abrir transação longa

Evitar:

```txt
abrir SessionManager
chamar API externa lenta
esperar resposta
salvar banco
commit
```

Isso segura conexão e piora concorrência.

Preferível:

```txt
buscar dados necessários
fechar transação
chamar API externa
abrir nova transação curta para persistir resultado
```

Exceção:

```txt
quando a consistência exigir que tudo seja salvo junto.
```

### 2. Não compartilhar SessionManager entre tarefas concorrentes

Errado:

```python
manager = SessionManager(async_engine)

await asyncio.gather(
    task_a(manager),
    task_b(manager),
)
```

Correto:

```txt
cada task cria seu próprio SessionManager
```

### 3. Não chamar commit dentro do repository

Commit deve ficar no `SessionManager`.

### 4. Usar flush quando precisar do ID antes do commit

Exemplo:

```python
self.session.add(model)
await self.session.flush()
```

Isso permite obter `model.id` antes do commit.

## Padrão esperado nos use cases

Use cases devem ser transacionais quando executados dentro de um `SessionManager`.

Exemplo:

```txt
CreateProjectUseCase
- cria Project
- cria OutboxEvent
- retorna DTO
- não chama commit
```

O commit acontece fora, pelo `SessionManager`.

## Padrão esperado nos workers

Workers devem processar unidades claras:

```txt
um evento por transação
ou
um batch por transação
```

Para eventos críticos, preferir:

```txt
um evento por transação
```

Para eventos simples e volumosos, pode usar:

```txt
batch por transação
```

## Padrão para outbox

```txt
1. Use case cria dado de domínio.
2. Use case cria outbox_event na mesma session.
3. SessionManager faz commit.
4. Se erro, SessionManager faz rollback.
```

## Padrão para inbox

```txt
1. Dispatcher carrega inbox_event pendente.
2. Handler executa reação.
3. Handler altera dados necessários.
4. Handler marca inbox_event como processed.
5. Handler pode criar novo outbox_event.
6. SessionManager faz commit.
7. Se erro, SessionManager faz rollback.
```

## Resultado esperado

Depois desta skill, o projeto deve ter:

```txt
src/shared/infra/database/session_manager.py
```

E todos os módulos devem seguir a regra:

```txt
uma operação de negócio = uma session transacional
repositories usam a mesma session
commit/rollback ficam no SessionManager
outbox/inbox usam a mesma transação dos efeitos que precisam garantir
```

## Não fazer nesta skill

```txt
Não implementar models reais.
Não implementar repositories reais.
Não implementar endpoints reais.
Não implementar workers reais.
Não implementar outbox completo.
Não implementar inbox completo.
```

Esta skill define apenas o padrão de controle transacional com `SessionManager`.
