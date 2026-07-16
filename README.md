# ProjectRAI

ProjectRAI é uma plataforma de runtime e control plane para produtos de IA. O objetivo é permitir que uma organização crie, versiona, teste, publique, monitore e opere agentes de IA com mais previsibilidade do que um protótipo isolado.

Na prática, o ProjectRAI centraliza o ciclo operacional de aplicações com IA: organizações, projetos, credenciais de provedores, agentes, prompts, contratos de entrada e saída, configurações de modelo, versões de conhecimento, releases, sessões de runtime, ferramentas HTTP/MCP, rastreabilidade, medição de uso e billing.

## O que o ProjectRAI resolve

Produtos de IA em produção costumam ter problemas recorrentes: prompts sem versão, mudanças sem histórico, agentes sem contrato de saída, ferramentas externas acopladas de forma frágil, custo difícil de rastrear, ausência de observabilidade e dificuldade para saber exatamente o que está rodando em produção.

O ProjectRAI foi desenhado para tratar agentes como unidades operacionais versionadas. Um agente pode ter diferentes versões de prompt, contrato, conhecimento e configuração de modelo. Essas partes podem ser agrupadas em releases, promovidas, testadas e usadas no runtime de forma rastreável.

## Principais capacidades

- Gestão de organizações, membros, convites e autenticação.
- Gestão de projetos e API keys por projeto.
- Cadastro de credenciais de provedores de IA.
- Criação e operação de agentes.
- Versionamento de prompts, contratos, configurações de modelo e conhecimento.
- Releases com promoção, rollback e testes associados.
- Execução de agentes via runtime síncrono, stream e jobs assíncronos.
- Sessões e mensagens para conversas stateful.
- Knowledge base com coleções, documentos, chunks e busca.
- Tools HTTP e MCP, com segredos criptografados, permissões e risk level.
- Descoberta de ferramentas MCP, permissões por tool remota e OAuth/device-code para providers protegidos.
- Observabilidade de traces e eventos de execução.
- Metering de uso por projeto e agente.
- Billing com planos e assinaturas por organização.

## Arquitetura em alto nível

O backend é uma aplicação FastAPI em Python, com arquitetura modular por bounded context. Cada módulo segue uma separação em camadas:

```text
src/modules/<module>/
├── domain          # entidades, enums, eventos, erros, contratos de repositório
├── application     # DTOs, use cases, handlers e composers
├── infra           # banco, mensageria, adapters, workers e implementações técnicas
└── presentation    # rotas HTTP, controllers, schemas e mapeamento de request/response
```

A camada `domain` concentra regras e contratos do próprio módulo. A camada `application` orquestra casos de uso e define o comportamento de negócio. A camada `infra` implementa persistência, mensageria e integrações técnicas. A camada `presentation` expõe o módulo por HTTP e traduz requests para os casos de uso.

O diretório `src/shared` contém infraestrutura e contratos técnicos reutilizáveis: configuração, sessão de banco, segurança HTTP, JWT/API keys, RabbitMQ, workers, observabilidade, adapters de apresentação e erros compartilhados. Ele não deve conter regra de negócio específica de um módulo.

## Módulos

### `identity`

Responsável por usuários, autenticação, refresh token, organizações, membros e convites. É o módulo que define a identidade operacional de quem acessa a plataforma e em qual organização atua.

### `core`

Responsável por projetos e API keys. Um projeto é a unidade prática de isolamento dentro da plataforma: agentes, tools, conhecimento, credenciais e uso ficam associados a um projeto.

### `agent`

É o módulo principal do runtime de IA. Ele concentra agentes, credenciais de provedores, prompts versionados, contratos, configurações de modelo, knowledge versions, releases, sessões, mensagens, execução, tools, secrets e integração MCP.

Dentro de `agent`, os principais conceitos são:

- `Agent`: definição operacional do agente.
- `AgentPrompt`: versões de prompt.
- `AgentContract`: contrato de entrada/saída e validação.
- `AgentModelConfig`: configuração versionada de provider/modelo.
- `KnowledgeVersion`: snapshot de coleções/documentos usados por uma release.
- `AgentRelease`: pacote versionado que combina prompt, contrato, modelo, conhecimento e runtime config.
- `Tool`: ferramenta HTTP ou MCP disponível para o agente.
- `Secret`: credencial criptografada usada por tools.
- `Session` e `Message`: estado conversacional do runtime.
- `AskJob`: execução assíncrona de perguntas ao agente.

### `metering`

Registra eventos de uso e consulta uso diário por projeto ou agente. É a base para análise de custo, consumo e cobrança.

### `billing`

Gerencia planos e assinaturas de organizações. O módulo separa regras comerciais de cobrança do runtime de agentes.

### `observability`

Armazena traces e eventos de trace. Serve para investigar execuções, falhas, latência, etapas de runtime e comportamento operacional.

## Comunicação entre módulos

O ProjectRAI usa dois estilos principais de comunicação.

### 1. Comunicação síncrona via HTTP

A API FastAPI monta os routers de cada módulo no bootstrap da aplicação. As rotas públicas são a fronteira síncrona do sistema. Exemplos:

- `/identity/*` para autenticação, usuários e organizações.
- `/core/*` para projetos e API keys.
- `/agent/ai/*` para agentes, prompts, contratos, configs, releases e testes.
- `/agent/knowledge/*` para coleções, documentos e busca.
- `/agent/runtime/*` para sessões, mensagens, ask, stream e jobs.
- `/agent/tools/*` para tools, secrets e execução de tools.
- `/tools/mcp/*` para descoberta, refresh, permissões e OAuth MCP.
- `/metering/*` para uso.
- `/billing/*` para planos e assinaturas.
- `/observability/*` para traces.

A camada HTTP não acessa banco diretamente. Cada rota usa um composer, que cria Unit of Work, repositories, adapters e controller. O controller chama o use case e devolve uma resposta padronizada.

### 2. Comunicação assíncrona via eventos

Para comunicação assíncrona, o projeto usa eventos de domínio, Outbox/Inbox e RabbitMQ. Cada módulo pode publicar eventos com `routing_key` versionada. O worker central descobre os registries dos módulos, registra consumidores e processa filas por módulo.

O fluxo esperado é:

```text
Use case
  -> altera estado dentro de uma Unit of Work
  -> grava evento na Outbox do módulo
  -> worker publica no RabbitMQ
  -> consumers de outros módulos recebem via Inbox/handler
  -> use cases locais reagem ao evento
```

Esse desenho reduz acoplamento direto entre módulos. O estado de um bounded context não deve depender de foreign keys físicas para tabelas de outro módulo. Quando um módulo precisa referenciar algo externo, ele armazena o UUID como identificador opaco e reage a eventos ou chamadas públicas.

## Runtime de agentes

O runtime permite executar agentes por diferentes modos:

- `POST /agent/runtime/ask` para execução síncrona.
- `POST /agent/runtime/ask/stream` para resposta em streaming.
- `POST /agent/runtime/ask/jobs` para execução assíncrona.
- Sessões e mensagens para manter histórico conversacional.

Durante a preparação da execução, o runtime resolve a release/configuração do agente, monta definições de tools, carrega conhecimento associado e aplica instrumentação. As execuções podem registrar eventos de LLM, tools, custos, latência e traces para observabilidade.

## Tools HTTP e MCP

O ProjectRAI diferencia tools HTTP de providers MCP.

### HTTP tools

São chamadas HTTP configuradas pelo usuário. Podem ter método, URL, headers, body, variáveis, schema de entrada/saída, timeout, risk level e secrets. São úteis para webhooks, APIs internas e integrações simples.

### MCP tools

MCP providers são servidores compatíveis com Model Context Protocol. Eles podem expor várias ferramentas remotas. O ProjectRAI consegue:

- carregar tools públicas/authless via discovery;
- descobrir tools remotas via `initialize` + `tools/list`;
- armazenar tools descobertas no config do provider;
- permitir, bloquear ou colocar em revisão cada tool remota;
- conectar providers protegidos por OAuth;
- lidar com OAuth PKCE, protected resource metadata e device-code quando o provider exigir.

A regra de UX esperada é simples: MCP público começa com `Load tools`; MCP protegido por autenticação muda para `Connect`; MCP com tools descobertas exige permissões antes de expor ao agente.

## Estrutura do repositório

```text
.
├── src/
│   ├── main.py                 # bootstrap FastAPI da API HTTP
│   ├── worker_main.py          # bootstrap do runtime de workers
│   ├── modules/                # bounded contexts da aplicação
│   │   ├── identity/
│   │   ├── core/
│   │   ├── agent/
│   │   ├── metering/
│   │   ├── billing/
│   │   └── observability/
│   └── shared/                 # infraestrutura e contratos técnicos compartilhados
├── web/                        # frontend React/Vite
├── migrations/                 # migrations Alembic
├── scripts/                    # scripts operacionais e seed
├── specs/                      # ADRs, specs e inventários arquiteturais
├── tests/                      # testes unitários, integração, contrato e arquitetura
├── Dockerfile                  # imagem da API/workers
├── docker-compose.yml          # stack local completa
├── pyproject.toml              # dependências e tooling Python
└── README.md
```

## Stack principal

Backend:

- Python 3.14
- FastAPI
- Pydantic / Pydantic Settings
- SQLAlchemy async
- Alembic
- PostgreSQL com pgvector
- RabbitMQ via `aio-pika`
- Redis para cache de sessão MCP
- LangChain / LangChain OpenAI
- Ruff, Pyright e Pytest

Frontend:

- React 19
- Vite
- TypeScript
- React Query
- React Router
- React Hook Form
- Zod
- Tailwind CSS
- Vitest

Infra local:

- PostgreSQL/pgvector
- PgBouncer
- RabbitMQ Management
- Redis
- API
- Workers
- Web

## Configuração local

Crie um `.env` na raiz. Os nomes seguem o prefixo `PROJECTRAI_`.

Variáveis essenciais:

```env
PROJECTRAI_DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/projectrai
PROJECTRAI_SECRET_KEY=dev-docker-secret-key-32chars!!
PROJECTRAI_ENCRYPTION_KEY=dev-docker-enc-key-32chars!!
PROJECTRAI_RABBITMQ_URL=amqp://projectrai:projectrai@rabbitmq:5672/
PROJECTRAI_RABBITMQ_EXCHANGE=domain.events
PROJECTRAI_REDIS_URL=redis://redis:6379/0
PROJECTRAI_DEBUG=true
PROJECTRAI_LOG_LEVEL=INFO
```

Para produção, o `Settings` valida requisitos mínimos de segurança: `DEBUG=false`, secrets fortes, CORS com origens exatas HTTPS, trusted hosts definidos, cookies seguros, logs JSON e ausência de credenciais padrão em PostgreSQL/RabbitMQ.

## Rodando com Docker Compose

```bash
docker compose up --build
```

Serviços principais:

- API: `http://localhost:8000`
- Web: `http://localhost:5173`
- PostgreSQL: `localhost:5432`
- PgBouncer: `localhost:6432`
- RabbitMQ: `localhost:15672`

O compose executa migrations com Alembic antes de subir API e workers. A API expõe healthcheck em `/health` e liveness em `/live`.

## Rodando backend sem Docker

Instale as dependências:

```bash
uv sync
```

Execute migrations:

```bash
uv run alembic upgrade head
```

Suba a API:

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Suba os workers:

```bash
uv run python -m src.worker_main
```

## Rodando frontend

```bash
cd web
npm install
npm run dev
```

Build de produção:

```bash
cd web
npm run build
```

## Qualidade e testes

Backend:

```bash
ruff check .
pyright
pytest
```

Frontend:

```bash
cd web
npm run build
npm run test:run
```

## Convenções arquiteturais

- Cada módulo é dono do próprio domínio, banco, repositories, Unit of Work, workers e eventos.
- `presentation` não acessa models ou repositories diretamente.
- `application` orquestra use cases e depende de contratos, não de detalhes HTTP.
- `infra` implementa persistência, mensageria e adapters técnicos.
- Comunicação entre módulos deve ocorrer por contratos públicos ou eventos.
- Eventos devem ser versionados e roteáveis.
- Secrets sensíveis devem ser criptografados antes de persistir.
- Tools devem ter risk level e permissões explícitas quando expõem capacidades externas.
- MCP público deve carregar tools antes de exigir OAuth.
- MCP protegido só deve usar OAuth quando o provider anunciar protected resource metadata ou responder challenge.

## Estado do projeto

ProjectRAI está em fase ativa de desenvolvimento. A arquitetura modular, o runtime de agentes, o suporte a releases, tools, MCP, metering, billing e observability já existem no código, mas a plataforma ainda deve ser tratada como produto em evolução. Antes de produção, valide migrations, testes, segurança de ambiente, controle de custos, autenticação, permissões e observabilidade operacional.
