# Worker Inventory — spec 008

Data: 2026-06-13
Comandos executados: `grep class.*Worker|Dispatcher|Consumer|Processor src/**/*.py`, `read src/workers/`, `read src/shared/workers/`, `read src/modules/runtime/infra/ask_job_worker.py`

## Resumo

| Categoria | Quantidade | Localização |
|---|---|---|
| Base worker (ABC) | 1 | `src/shared/workers/base_worker.py` |
| Shared infrastructure workers | 3 | `src/shared/workers/` |
| Root runner/entrypoint | 1 | `src/workers/runner.py` |
| Root dispatcher (business handlers) | 1 | `src/workers/dispatcher.py` |
| Root re-export package | 1 | `src/workers/__init__.py` |
| Module concrete workers | 1 | `src/modules/runtime/infra/ask_job_worker.py` |
| Worker registries | 0 | nenhum |
| Per-module worker registries | 0 | nenhum |

## Inventário detalhado

### 1. Base worker abstrato

| Arquivo | Classe | Tipo | Módulo dono | Herda de | Responsabilidade |
|---|---|---|---|---|---|
| `src/shared/workers/base_worker.py:6` | `BaseWorker` | ABC | shared (infra genérica) | `ABC` | Contrato base: recebe `AsyncEngine`, expõe `async run()` |

Status: **permitido em shared** — infraestrutura genérica sem domínio.

### 2. Shared infrastructure workers

| Arquivo | Classe | Tipo | Módulo dono | Herda de | Responsabilidade |
|---|---|---|---|---|---|
| `src/shared/workers/outbox_publisher.py:10` | `OutboxPublisherWorker` | shared infra | shared | `BaseWorker` | Itera `MODULES`, importa dinamicamente `modules.{module}.infra.models.OutboxEventModel`, publica no RabbitMQ |
| `src/shared/workers/inbox_consumer.py:14` | `InboxConsumerWorker` | shared infra | shared | `BaseWorker` | Consome queue global `projectrai.inbox` com binding `#`, roteia para Inbox do módulo inferido por `event_type.split(".",1)[0]` |
| `src/shared/workers/inbox_dispatcher.py:12` | `InboxDispatcherWorker` | shared infra | shared | `BaseWorker` | Itera `MODULES`, importa dinamicamente `modules.{module}.infra.models.InboxEventModel`, despacha para handlers registrados |

Observações:
- `OutboxPublisherWorker.MODULES` = `["identity", "core", "ai", "knowledge", "runtime", "tools", "metering", "billing", "observability"]` (hardcoded, linha 12-15)
- `InboxDispatcherWorker.MODULES` = lista idêntica (hardcoded, linha 14-17)
- `InboxConsumerWorker` usa `_module_for_event_type()` que extrai o primeiro segmento do `event_type` — falha para event_types sem prefixo de módulo válido (19/27 event_types conhecidos não possuem prefixo de módulo válido, conforme inventário de eventos)
- Ambos usam `importlib.import_module(f"modules.{module}.infra.models")` — acoplamento implícito a naming convention de módulos

Status: **violação parcial** — infra genérica mas com lista hardcoded de módulos concretos e dynamic import de internals de módulo. Após migração, deve usar registries declarativos por módulo.

### 3. Root runner/entrypoint

| Arquivo | Função/Classe | Tipo | Módulo dono | Responsabilidade |
|---|---|---|---|---|
| `src/workers/runner.py:24` | `_build_engine()` | helper | root workers | Cria `AsyncEngine` + `Settings` |
| `src/workers/runner.py:29` | `run_once()` | runner | root workers | Executa `worker.run()` uma vez |
| `src/workers/runner.py:44` | `run_loop()` | runner | root workers | Loop com signal handling e intervalo |
| `src/workers/runner.py:78` | `run_all_workers()` | runner | root workers | Instancia publisher, consumer, dispatcher e executa sequencialmente |
| `src/workers/runner.py:94` | `run_publisher()` | runner | root workers | Executa apenas OutboxPublisherWorker |
| `src/workers/runner.py:104` | `run_consumer()` | runner | root workers | Executa apenas InboxConsumerWorker |
| `src/workers/runner.py:114` | `run_dispatcher()` | runner | root workers | Executa InboxDispatcherWorker via `build_dispatcher()` |
| `src/workers/runner.py:123` | `run_ask_jobs()` | runner | root workers | Executa AskJobWorker |
| `src/workers/runner.py:132` | `__main__` | CLI entry | root workers | `python -m workers.runner [publisher|consumer|dispatcher|ask_jobs|all]` |

Imports diretos do runner:
- `from shared.infra.config import Settings` — permitido
- `from shared.infra.database.session import create_engine` — permitido
- `from shared.infra.rabbitmq import RabbitMQManager` — permitido
- `from shared.workers.base_worker import BaseWorker` — permitido
- `from modules.runtime.infra.ask_job_worker import AskJobWorker` — **cross-module import de infra interna**
- `from workers import InboxConsumerWorker, InboxDispatcherWorker, OutboxPublisherWorker` — via local __init__
- `from workers.dispatcher import build_dispatcher` — local

Status: **violação** — runner conhece worker concreto de módulo (`AskJobWorker`) e importa diretamente. No estado final, runner deve apenas descobrir registries de módulos e executar workers registrados.

### 4. Root dispatcher (business handlers)

| Arquivo | Função/Classe | Tipo | Módulo dono | Responsabilidade |
|---|---|---|---|---|
| `src/workers/dispatcher.py:32` | `build_dispatcher()` | factory | root workers | Instancia `InboxDispatcherWorker` e registra 5 handlers de negócio |
| `src/workers/dispatcher.py:8` | `handle_project_created()` | handler | nenhum (global) | Loga "Project created" — corpo é TODO |
| `src/workers/dispatcher.py:13` | `handle_organization_created()` | handler | nenhum (global) | Loga "Organization created" — corpo é TODO |
| `src/workers/dispatcher.py:18` | `handle_agent_created()` | handler | nenhum (global) | Loga "Agent created" |
| `src/workers/dispatcher.py:22` | `handle_document_uploaded()` | handler | nenhum (global) | Loga "Document uploaded" — corpo é TODO |
| `src/workers/dispatcher.py:27` | `handle_usage_recorded()` | handler | nenhum (global) | Loga "Usage recorded" — corpo é TODO |

Handler keys registrados:
- `"identity.organization_created"` → `handle_organization_created`
- `"core.project_created"` → `handle_project_created`
- `"ai.agent_created"` → `handle_agent_created`
- `"knowledge.document.uploaded"` → `handle_document_uploaded`
- `"metering.usage_recorded"` → `handle_usage_recorded`

Status: **violação grave** — handlers de negócio em pacote global `src/workers/`. Estes devem pertencer a `src/modules/<module>/infra/workers/` do módulo consumidor. Adicionalmente, as handler keys não correspondem aos event_types produzidos (conforme inventário de eventos spec 007).

### 5. Root re-export package

| Arquivo | Tipo | Responsabilidade |
|---|---|---|
| `src/workers/__init__.py` | re-export | Importa `OutboxPublisherWorker`, `InboxConsumerWorker`, `InboxDispatcherWorker` de `shared.workers` e re-exporta |

Status: **desnecessário no estado final** — após migração, runner descobre workers via registries de módulos.

### 6. Module concrete workers

| Arquivo | Classe | Tipo | Módulo dono | Herda de | Responsabilidade |
|---|---|---|---|---|---|
| `src/modules/runtime/infra/ask_job_worker.py:35` | `AskJobWorker` | worker concreto | runtime (→ agent) | nenhum (não herda BaseWorker) | Busca jobs pendentes, monta UoW cross-module, executa AskAgentUseCase |

Cross-module imports do AskJobWorker:
- `from modules.ai.infra.repositories import SQLAlchemyAgentRepository, SQLAlchemyProviderCredentialRepository`
- `from modules.knowledge.infra.repositories import SQLAlchemyAgentCollectionRepository, SQLAlchemyDocumentChunkRepository`
- `from modules.metering.infra.repositories import SQLAlchemyUsageEventRepository`
- `from modules.observability.infra.repositories import SQLAlchemyTraceEventRepository, SQLAlchemyTraceRepository`
- `from modules.runtime.infra.repositories import SQLAlchemyAskJobRepository, SQLAlchemyMessageRepository, SQLAlchemyOutboxEventWriter, SQLAlchemySessionRepository`
- `from modules.runtime.service.ask_use_case import AskAgentUseCase`
- `from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork`

UoW cross-module: `PostgresUnitOfWork(session_factory)` coordena repositories de 5 módulos (ai, knowledge, runtime, metering, observability) em uma única session.

Status: **violação crítica** — worker concreto localizado corretamente em módulo, porém monta UoW cross-module com repositories de 5 módulos diferentes. Após migração para `agent`, ai/knowledge/runtime serão internos ao módulo; metering e observability devem ser comunicados via Outbox/Inbox. AskJobWorker também não herda `BaseWorker`.

### 7. Worker registries

Nenhum registry pattern detectado no repositório. Workers são instanciados diretamente no runner.

Destino esperado: cada módulo terá um `WorkerRegistry` em `src/modules/<module>/infra/workers/registry.py` que declara seus workers. O runner central apenas descobre registries e executa.

## Destinos esperados após migração

| Item atual | Destino | Spec responsável |
|---|---|---|
| `src/shared/workers/base_worker.py` | permanece em `src/shared/workers/` | 050 |
| `src/shared/workers/outbox_publisher.py` | refatorar para usar registries em vez de MODULES hardcoded | 050-055, 060 |
| `src/shared/workers/inbox_consumer.py` | refatorar para per-module queues ou registry-based routing | 050-055, 060 |
| `src/shared/workers/inbox_dispatcher.py` | refatorar para usar registries em vez de MODULES hardcoded | 050-055, 060 |
| `src/workers/runner.py` | migrar para runner genérico que descobre registries de módulos | 054, 063 |
| `src/workers/dispatcher.py` | remover; handlers movem para `src/modules/<module>/infra/workers/` do consumidor | 061, 062, 080-085 |
| `src/workers/__init__.py` | remover após migração | 152 |
| `src/modules/runtime/infra/ask_job_worker.py` | migrar para `src/modules/agent/infra/workers/ask_job_worker.py`; eliminar UoW cross-module | 040-045, 074, 085 |

## Riscos identificados

| Risco | Severidade | Evidência | Mitigação | Specs afetadas |
|---|---|---|---|---|
| Runner importa `AskJobWorker` diretamente de `modules.runtime.infra` | alta | `src/workers/runner.py:13` | Mover para registry pattern; runner não conhece workers concretos | 054, 063 |
| MODULES hardcoded em OutboxPublisherWorker e InboxDispatcherWorker | alta | `src/shared/workers/outbox_publisher.py:12-15`, `src/shared/workers/inbox_dispatcher.py:14-17` | Substituir por registry declarativo por módulo | 050-055, 060 |
| Business handlers em `src/workers/dispatcher.py` | alta | `src/workers/dispatcher.py:8-30` | Mover handlers para módulo consumidor; cada módulo registra seus handlers | 061, 062, 080-085 |
| AskJobWorker UoW cross-module com 5 módulos | crítica | `src/modules/runtime/infra/ask_job_worker.py:64-74` | Após consolidação em agent, ai/knowledge/runtime são internos; metering/observability via eventos | 040-045, 074 |
| AskJobWorker não herda BaseWorker | média | `src/modules/runtime/infra/ask_job_worker.py:35` | Alinhar com BaseWorker ou novo contrato | 085 |
| InboxConsumerWorker usa queue global `projectrai.inbox` com binding `#` | alta | `src/shared/workers/inbox_consumer.py:16` | Migrar para queues per-module com bindings específicos | 050-055, 106 |
| InboxConsumerWorker routing falha para 19/27 event_types | crítica | `src/shared/workers/inbox_consumer.py:10-11` (`_module_for_event_type`) | Padronizar event_types com prefixo de módulo ou lookup table | 100-109 |
| Handler keys no dispatcher não correspondem a event_types produzidos | alta | `src/workers/dispatcher.py:35-39` vs inventário de eventos | Alinhar keys com event_types reais ou remover dispatcher global | 100-109 |

## Inconsistências

- `AskJobWorker` não herda `BaseWorker` — não é descoberto por typing genérico.
- `src/workers/dispatcher.py` é o único local que conecta handlers a event_types, mas as keys estão desalinhadas com os event_types reais produzidos.
- `OutboxPublisherWorker` e `InboxDispatcherWorker` usam a mesma lista `MODULES` hardcoded mas sem validação se o módulo possui `OutboxEventModel`/`InboxEventModel`.
- `InboxConsumerWorker` silencia `ImportError`/`AttributeError` quando módulo não possui `InboxEventModel` — eventos são perdidos sem log.
- Não existe nenhum teste unitário ou de integração para workers no repositório atual.
