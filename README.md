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
├── docker-compose.yml          # stack local completa / integration harness
├── docker-compose.prod.yml     # referência application-only endurecida
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
- S3-compatible object storage para Knowledge
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

Infra do harness local:

- PostgreSQL/pgvector
- PgBouncer
- RabbitMQ Management
- Redis
- MinIO
- API
- Workers
- Web

## Configuração

Existe um único contrato de ambiente para Development, Staging e Production:

```bash
cp .env.example .env
```

O `.env` é organizado por serviço e funciona como manifesto da topologia. Comunicação entre serviços usa URLs explícitas:

```text
PROJECTRAI_POSTGRES_URL    -> PostgreSQL direto; Migration/PgBouncer
PROJECTRAI_DATABASE_URL    -> endpoint pooled; API/Workers
PROJECTRAI_RABBITMQ_URL    -> RabbitMQ; Workers
PROJECTRAI_REDIS_URL       -> Redis
PROJECTRAI_S3_ENDPOINT_URL -> object storage
VITE_API_URL               -> API pública consumida pelo browser
```

`POSTGRES_*` e `RABBITMQ_*` existem somente para bootstrap dos containers de infraestrutura do harness local. Aplicação e workers não derivam URLs a partir deles.

O mesmo `.env.example` é usado em Production; altere `PROJECTRAI_ENVIRONMENT`, URLs, secrets, domínios e credenciais. Não existe um schema separado de variáveis para Production.

Cada serviço deve receber somente seu subconjunto de variáveis. O Compose faz essa separação explicitamente; deployments em Kubernetes/ECS/VMs devem seguir a mesma regra.

## Rodando com Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Serviços principais:

- API: `http://localhost:8000`
- Web: `http://localhost:5173`
- PostgreSQL: `localhost:5432`
- PgBouncer: `localhost:6432`
- RabbitMQ Management: `http://localhost:15672`
- Redis: `localhost:6379`
- MinIO: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`

O Compose é um harness all-in-one. A aplicação continua usando URLs explícitas, portanto qualquer dependência pode ser movida para outro host sem alterar código.

Migration conecta por `PROJECTRAI_POSTGRES_URL` diretamente ao PostgreSQL. API e Workers usam `PROJECTRAI_DATABASE_URL`, normalmente apontando para PgBouncer.

## Production / deployment distribuído

`docker-compose.prod.yml` contém apenas `migrate`, `api`, `workers` e `web`. PostgreSQL, PgBouncer, RabbitMQ, Redis e object storage são endpoints externos definidos no mesmo `.env`.

```bash
docker compose -f docker-compose.prod.yml run --rm migrate
docker compose -f docker-compose.prod.yml up -d api workers web
```

Os mesmos containers podem ser executados separadamente em servidores/orquestradores diferentes. Consulte `docs/runbooks/production-deployment.md` para a matriz de dependências por serviço.

## Rodando backend sem Docker

Instale as dependências:

```bash
uv sync
```

Use URLs alcançáveis a partir do host onde cada processo roda. Para migration:

```bash
export PROJECTRAI_POSTGRES_URL='postgresql://user:pass@host:5432/projectrai'
uv run alembic upgrade head
```

Para API, configure as variáveis do bloco `API` e as dependências compartilhadas do manifesto e execute:

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Para Workers, configure as variáveis do bloco `WORKERS` e suas dependências e execute:

```bash
uv run python -m src.worker_main
```

API e Worker fixam internamente seus próprios papéis de runtime; não existe `PROJECTRAI_SERVICE_ROLE` no contrato de deployment.

## Rodando frontend

O Vite lê `VITE_API_URL` do `.env` na raiz usando o modo neutro `manifest`, evitando arquivos legados `.env.web`/`.env.production`:

```bash
cd web
npm install
npm run dev
```

No Docker, somente `VITE_API_URL` é passado ao build; o arquivo `.env` completo não entra no frontend builder.

Build:

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
