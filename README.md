# Woobe

**Control Plane for AI Products.**

Woobe é uma plataforma self-hostable para criar, configurar, versionar, publicar, executar e observar produtos de IA baseados em Agents e Agent Networks.

O produto trata configuração e runtime como partes do mesmo ciclo operacional: Draft é editável; Staging serve para validação; Production executa releases imutáveis e permite rollback. Runs, Traces, Sessions, Knowledge, Tools e bindings de runtime preservam a versão efetivamente usada por cada execução.

## Capacidades do core

- Organizations e Projects como fronteiras comercial e técnica.
- Agents configuráveis e versionáveis.
- Agent Networks versionadas.
- Draft, Staging, Production, releases imutáveis e rollback.
- Runtime API síncrona, streaming e jobs assíncronos.
- Sessions e histórico conversacional.
- ChatSurface para publicar Agent Releases e Network Releases em aplicações web.
- Knowledge/RAG com Collections, Documents, chunks e Vector Snapshots.
- Tools HTTP e MCP.
- Provider credentials e BYOK.
- Agent Runs, Network Runs, Traces, Usage e Metering.

## Community e Cloud

`WOOBE_EDITION=community` executa o core self-hosted sem cobrança da Woobe por Run e sem dependência obrigatória da Woobe Cloud. O operador arca com sua própria infraestrutura, provedores de modelo e serviços externos usados por Tools.

`WOOBE_EDITION=cloud` executa o mesmo core e adiciona capacidades comerciais gerenciadas pela Woobe, como Billing. O core operacional não é duplicado por edição.

O código Cloud pode permanecer visível no mesmo repositório para transparência e revisão, mas fica fisicamente e juridicamente separado do Community/Core. Consulte `LICENSE.md` e `LICENSE-CLOUD.md`.

## Quick start self-hosted

Requisitos: Docker com Docker Compose.

```bash
cp .env.example .env
python scripts/generate_self_host_env.py --force
docker compose -f docker-compose.community.yml up -d --build
```

Depois, abra a interface web configurada em `VITE_WEB_URL`/porta do Compose e faça o bootstrap da primeira instalação. O primeiro usuário de uma instalação Community nova torna-se o Instance Owner; depois disso o cadastro público é fechado e novos membros entram por convite.

Consulte `docs/SELF_HOSTING.md` antes de expor uma instalação na internet.

## Deployment completo

`docker-compose.yml` é o topology de desenvolvimento/integrado, incluindo PostgreSQL, PgBouncer, RabbitMQ, Redis e MinIO. `docker-compose.prod.yml` é a referência application-only para deployments em que banco, broker, cache e object storage são serviços externos.

Toda configuração da aplicação usa o prefixo `WOOBE_`. Variáveis públicas de build do frontend usam `VITE_*`.

## Arquitetura

O backend compartilha o core entre todas as edições e isola código comercial específico:

```text
src/
├── modules/                  # Woobe Community/Core compartilhado
│   ├── identity/
│   ├── core/
│   ├── agent/
│   ├── network/
│   ├── chat_surface/
│   ├── metering/
│   └── observability/
├── editions/
│   └── cloud/
│       └── billing/          # Woobe Cloud; licença separada
└── shared/                   # infraestrutura transversal
```

O frontend segue a mesma fronteira: funcionalidades Cloud específicas ficam em `web/src/editions/cloud/**`. Não existe uma cópia `community/` do core; Community é o core compartilhado sem os módulos comerciais de edição.

## Segurança operacional

- Produção exige secrets fortes e distintos para autenticação e ChatSurface.
- Cookies de autenticação precisam ser `Secure` em produção.
- CORS e Trusted Hosts devem usar allowlists explícitas.
- ChatSurface Access Keys são server-to-server; o navegador recebe somente Session Access Tokens efêmeros.
- Runtime Keys e credenciais de provider não devem ser expostas ao frontend.

Consulte `SECURITY.md` para reporte de vulnerabilidades.

## Contribuição

Leia `CONTRIBUTING.md` antes de abrir uma alteração. A branch de integração do projeto é `development`; branches de feature/fix devem abrir PR para `development`.

## Licença

Woobe Community/Core é distribuída como software **source-available/fair-code e self-hostable**, não como software Open Source segundo a definição OSI. O uso interno e a construção de produtos próprios sobre o core são permitidos nos termos de `LICENSE.md`; oferecer o próprio control plane Woobe como serviço hospedado, white-label ou OEM exige acordo comercial separado.

Código sob `src/editions/**` e `web/src/editions/**` não herda automaticamente a licença Community/Core. O código Woobe Cloud atualmente presente nesses diretórios é regido por `LICENSE-CLOUD.md`.

Os arquivos de licença incluídos nesta branch de preparação pública precisam de revisão jurídica antes da mudança de visibilidade do repositório.
