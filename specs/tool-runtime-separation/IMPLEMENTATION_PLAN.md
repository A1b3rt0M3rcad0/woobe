# Plano de separação HTTP/MCP em tools

Branch base: `development-mvp`
Branch deste plano: `plan/separate-http-mcp-tools-20260623`
Escopo deste commit: documentação e plano de implementação. Nenhuma mudança de runtime, schema, API ou frontend foi implementada.

## 1. Diagnóstico do estado atual

Hoje o produto expõe tools como uma capacidade única dentro do bounded context `agent`, com persistência em `agent.tools` e `agent.tool_secrets`. O modelo de domínio possui metadata comum (`project_id`, `agent_id`, `name`, `description`, `type`, `config`, schemas, risk, timeout e status), mas o campo `type` mistura categorias genéricas com um valor híbrido `http_mcp`.

Na prática, `http_mcp` não representa dois runtimes. O fluxo real é HTTP:

- O frontend de criação chama a modal `Create MCP HTTP Tool`, exige URL, método, headers e body, e envia `type: 'http_mcp'`.
- O DTO backend aceita `type`, mas `config` é um `dict` genérico sem discriminação por protocolo.
- `ExecuteToolUseCase` ignora o `type` e lê sempre `url`, `method`, `headers`, `body` e `variables` de `config`.
- `ToolExecutionPort` é HTTP-specific: recebe `method`, `url`, `headers`, `body`, `timeout_ms`.
- A implementação concreta disponível é `HttpToolExecutor`, baseada em `httpx`, com validação SSRF, bloqueio de redirect, limite de timeout e limite de resposta.
- O conversor para OpenAI function definition também assume semântica HTTP, usando URL/body para inferir variáveis e gerando descrição `HTTP <method> <url>`.

Conclusão: o sistema tem uma tool HTTP funcional e parcialmente hardenizada, mas nomeada/registrada como `HTTP_MCP`. MCP, no sentido de tool remota com descoberta de capabilities e execução via protocolo MCP, ainda não existe como runtime separado.

## 2. Problema arquitetural

O acoplamento atual cria quatro problemas objetivos:

1. Ambiguidade de domínio: `HTTP_MCP` junta transporte HTTP simples com protocolo MCP, que têm contratos, ciclo de vida e semântica diferentes.
2. Porta errada: `ToolExecutionPort.execute(method, url, headers, body, timeout_ms)` impede plugar MCP sem forçar MCP a parecer HTTP.
3. UI/API enganosa: o usuário cria uma “MCP HTTP Tool”, mas a execução é apenas uma chamada HTTP templated.
4. Evolução ruim: adicionar MCP real exigiria condicionais no use case atual ou sobrecarga de `config`, aumentando dívida técnica.

## 3. Arquitetura ideal

Separar conceito de tool de runtime/transport. A entidade `Tool` continua sendo o aggregate/registro comum, mas o protocolo passa a ser discriminado explicitamente.

### 3.1 Modelo conceitual recomendado

Manter uma tabela única `agent.tools` no curto prazo, porque os campos comuns já existem e `config` em JSONB permite evolução compatível. Não vale criar tabelas separadas agora, salvo se houver necessidade forte de constraints SQL específicas por protocolo.

Campos comuns:

- `id`
- `project_id`
- `agent_id`
- `name`
- `description`
- `type` ou `protocol`
- `config`
- `input_schema`
- `output_schema`
- `risk_level`
- `timeout_ms`
- `status`

Valores alvo:

- `http`: chamada HTTP direta.
- `mcp`: chamada MCP por servidor/tool remota.
- `function`, `api`, `database_query`, `webhook`, etc. só devem permanecer se tiverem runtimes reais ou se forem explicitamente categorias futuras. Caso contrário, marcar como legacy/future para não poluir a arquitetura do MVP.

Compatibilidade:

- `http_mcp` deve virar alias deprecated para `http` durante uma janela de migração.
- Novas criações não devem mais gerar `http_mcp`.
- Registros existentes com `type='http_mcp'` devem continuar executando como HTTP até a migração de dados.

### 3.2 Configs discriminadas

Criar contratos explícitos por protocolo.

`HttpToolConfig`:

- `protocol: 'http'`
- `url: string`
- `method: GET|POST|PUT|PATCH|DELETE|HEAD`
- `headers: [{ key, value, sensitive?, secret_ref? }]`
- `query?: Record<string, string>`
- `body?: string`
- `variables?: Record<string, string>`
- `auth?: { type, credentials/secret refs }`
- `timeout_ms?: number`

`McpToolConfig`:

- `protocol: 'mcp'`
- `server`: `{ transport, url?, command?, args?, env_secret_refs? }`
- `tool_name: string`
- `server_headers?: [{ key, value?, secret_ref? }]`
- `input_schema_source: 'discovered' | 'manual'`
- `discovered_input_schema?: object`
- `discovery_cache_ttl_seconds?: number`
- `timeout_ms?: number`

Transportes MCP a considerar em fases:

1. `streamable_http` / remote HTTP MCP: melhor para SaaS/multi-tenant.
2. `sse`: se houver dependência de servidores MCP legados.
3. `stdio`: evitar no MVP cloud multi-tenant, porque implica executar comandos por tenant e aumenta superfície de sandbox/RCE.

### 3.3 Portas e runtimes

Trocar a porta HTTP-specific por uma porta runtime-agnostic:

- `ToolRuntimePort.execute(tool: Tool, input_data: dict) -> ToolExecutionResult`
- `ToolRuntimePort.test(config: dict, input_data?: dict) -> ToolExecutionResult`
- `ToolRuntimePort.to_openai_definition(tool: Tool) -> dict`

Criar runtimes separados:

- `HttpToolRuntime`: encapsula o executor HTTP atual, template resolver, headers/secrets, SSRF e limites.
- `McpToolRuntime`: gerencia conexão/cliente MCP, descoberta opcional de ferramentas, schema e execução de `tool_name`.
- `ToolRuntimeRegistry`: resolve runtime por `tool.type`/`protocol`.

O `ExecuteToolUseCase` não deve mais construir URL/method/body. Ele deve apenas:

1. carregar a tool;
2. validar status;
3. resolver runtime pelo tipo/protocolo;
4. delegar execução;
5. normalizar resultado.

### 3.4 Conversão para OpenAI tools

Mover `agent_tool_to_openai_definition` para uma estratégia por runtime:

- HTTP: usar `input_schema` se informado; caso contrário inferir variáveis de URL/body como hoje.
- MCP: usar schema descoberto do servidor MCP ou schema manual persistido.

A descrição default não deve assumir HTTP. Ela deve vir do runtime:

- HTTP: `HTTP GET https://...`
- MCP: `MCP <server_alias>/<tool_name>` ou a descrição retornada pela discovery.

### 3.5 API e frontend

Opção preferida: manter endpoints de CRUD genéricos para tools e separar apenas os contratos de criação/teste por discriminated union.

Backend:

- `POST /tools/tools`: aceita `type: 'http' | 'mcp' | legacy aliases` e valida `config` conforme tipo.
- `POST /tools/tools/test`: aceita `{ type, config, input_data }`, não apenas `{ config }`.
- `POST /tools/http/test` e `POST /tools/mcp/test` são opcionais; úteis se quiser simplificar frontend e logs.

Frontend:

- Renomear a modal atual para `Create HTTP Tool`.
- Criar `Create MCP Tool` separada.
- No catálogo/lista, mostrar o protocolo explicitamente: `HTTP`, `MCP`, `Legacy HTTP_MCP`.
- Remover hardcode `type: 'http_mcp'`.

## 4. Plano de implementação

### Fase 0 — Guardrails e caracterização

Objetivo: congelar comportamento atual antes de refatorar.

Tarefas:

1. Criar testes de caracterização para HTTP existente:
   - criação com `type='http_mcp'` continua aceita;
   - execução com `url/method/headers/body/variables` funciona;
   - SSRF, redirect, timeout e response limit continuam cobertos;
   - conversão para OpenAI tool mantém schema inferido.
2. Criar teste explícito mostrando que `ExecuteToolUseCase` não deve depender de `config.url` diretamente após a refatoração.
3. Criar teste de frontend ou unit test de payload garantindo que novas HTTP tools usam `type='http'`.

Gate de saída:

- Testes atuais passam.
- Testes de caracterização falham de forma útil antes da refatoração ou passam documentando legado.

### Fase 1 — Introduzir tipos e configs discriminadas sem trocar execução

Objetivo: preparar contrato sem quebrar registros existentes.

Tarefas:

1. Atualizar `ToolType`:
   - adicionar `HTTP = 'http'`;
   - adicionar `MCP = 'mcp'`;
   - manter `HTTP_MCP = 'http_mcp'` como deprecated alias.
2. Criar DTOs Pydantic específicos:
   - `HttpToolConfigDTO`;
   - `McpToolConfigDTO`;
   - `CreateToolInput` com validação por `type`.
3. Criar helper `normalize_tool_type(type)`:
   - `http_mcp -> http` para runtime;
   - `http -> http`;
   - `mcp -> mcp`.
4. Atualizar validação de `TestToolInput` para exigir `type` no caminho novo, mas aceitar ausência como HTTP legacy.

Gate de saída:

- Nenhuma mudança funcional ainda.
- Tools existentes continuam listando/executando.
- Payloads novos podem usar `http`.

### Fase 2 — Extrair runtime HTTP

Objetivo: tirar lógica HTTP do use case e colocar em runtime específico.

Tarefas:

1. Criar `ToolExecutionResult` e `ToolRuntimePort` agnósticos.
2. Criar `HttpToolRuntime` usando internamente o `HttpToolExecutor` atual.
3. Mover para `HttpToolRuntime`:
   - resolução de variáveis de URL/body;
   - resolução de headers/secrets;
   - default de timeout;
   - normalização de output.
4. Alterar `ExecuteToolUseCase` para delegar ao registry.
5. Alterar `TestToolUseCase` para delegar ao runtime HTTP quando `type` ausente ou `http/http_mcp`.
6. Manter `HttpToolExecutor` como componente baixo nível HTTP, não como executor genérico de tools.

Gate de saída:

- Todos os testes HTTP existentes passam sem depender de `ExecuteToolUseCase` conhecer `url/method/body`.
- Cobertura nova verifica que `ExecuteToolUseCase` chama o registry/runtime correto.

### Fase 3 — Registry e conversor por runtime

Objetivo: eliminar suposições HTTP do fluxo LLM.

Tarefas:

1. Criar `ToolRuntimeRegistry` com mapeamento:
   - `http` e `http_mcp` -> `HttpToolRuntime`;
   - `mcp` -> inicialmente `McpToolRuntimeStub` se MCP ainda não for ativado.
2. Mover `agent_tool_to_openai_definition` para estratégia:
   - `HttpToolDefinitionBuilder`;
   - `McpToolDefinitionBuilder`.
3. Atualizar `AskAgentUseCase` para obter definitions via registry/builder, não via função HTTP-centric.
4. Manter limite de 5 tool rounds e registro de `ToolCallInfo` inalterados.

Gate de saída:

- Ask flow com HTTP tool continua funcionando.
- Converter não cita HTTP para tools MCP.
- Teste garante que tool MCP sem schema válido falha de forma explícita antes de bindar ao LLM.

### Fase 4 — Implementar MCP runtime real

Objetivo: adicionar MCP sem contaminar HTTP.

Tarefas:

1. Definir cliente MCP suportado no backend Python.
2. Implementar `McpToolRuntime`:
   - inicialização por config;
   - resolução de secrets para headers/env;
   - chamada de `tool_name` com `input_data`;
   - timeout e normalização de erro;
   - redaction de dados sensíveis.
3. Implementar discovery opcional:
   - endpoint interno/application use case para listar tools de um servidor MCP;
   - cache de schemas descobertos em `config.discovered_input_schema` ou tabela futura.
4. Impor política de transporte:
   - MVP recomendado: remote HTTP/SSE apenas;
   - stdio bloqueado por padrão.
5. Validar multi-tenant:
   - nenhuma conexão/cache compartilhado entre projects com secrets diferentes;
   - logs sem secrets;
   - timeouts e limites de resposta equivalentes ao HTTP.

Gate de saída:

- MCP tool consegue ser testada e executada por `ExecuteToolUseCase` via registry.
- Ask flow consegue bindar MCP tool com schema correto.
- MCP errors retornam `success=false` sem quebrar o loop LLM.

### Fase 5 — Frontend separado

Objetivo: remover ambiguidade operacional para o usuário.

Tarefas:

1. Renomear modal atual para `Create HTTP Tool`.
2. Criar `CreateMcpToolModal` com campos MCP:
   - transport;
   - server URL/headers;
   - tool name;
   - discovery/test connection;
   - input schema preview.
3. Atualizar `Tool`/`CreateToolRequest` TypeScript para discriminated union.
4. Atualizar listagem para badges de protocolo.
5. Atualizar importação/associação com agent sem depender do protocolo.

Gate de saída:

- HTTP e MCP aparecem como opções distintas.
- Criação HTTP nunca envia `http_mcp`.
- Usuário não vê mais “MCP HTTP Tool”.

### Fase 6 — Migração de dados e limpeza de legado

Objetivo: remover alias híbrido depois de compatibilidade.

Tarefas:

1. Criar migration ou script seguro:
   - `UPDATE agent.tools SET type='http' WHERE type='http_mcp'`.
2. Manter compatibilidade de leitura por uma release.
3. Adicionar métrica/log para detectar uso residual de `http_mcp`.
4. Remover `HTTP_MCP` do enum apenas depois de confirmar zero registros e zero payloads legados.
5. Atualizar testes que hoje esperam `ToolType.HTTP_MCP == 'http_mcp'`.

Gate de saída:

- Banco sem `http_mcp`.
- Frontend e backend sem payload novo `http_mcp`.
- Compatibilidade removida de forma controlada.

## 5. Sequência de PRs recomendada

1. `refactor/tools-type-contracts`
   - enum, DTOs, normalização e testes de caracterização.
2. `refactor/http-tool-runtime`
   - registry, `HttpToolRuntime`, use cases delegando ao runtime.
3. `refactor/tool-definition-builders`
   - conversão OpenAI por runtime.
4. `feat/mcp-tool-runtime`
   - runtime MCP real, discovery e testes backend.
5. `feat/separate-tool-creation-ui`
   - modais HTTP/MCP separadas e payloads TS discriminados.
6. `chore/migrate-http-mcp-alias`
   - migração de dados e remoção gradual de alias.

## 6. Critérios de aceite finais

- `ExecuteToolUseCase` não conhece `url`, `method`, `headers` ou `body`.
- `ToolExecutionPort` atual HTTP-specific deixa de ser porta genérica de tool.
- HTTP e MCP têm configs Pydantic/TypeScript separadas.
- `http_mcp` não é usado em novas criações.
- Tool HTTP existente continua executando durante a janela de compatibilidade.
- Tool MCP real executa via runtime próprio, com timeout, redaction, secrets e schema isolados.
- `AskAgentUseCase` obtém OpenAI tool definitions via builder/registry, não por função HTTP-centric.
- UI mostra HTTP e MCP como conceitos distintos.
- Testes cobrem criação, teste, execução direta e execução via ask para HTTP e MCP.

## 7. Riscos e decisões pendentes

1. Transporte MCP: decidir se MVP aceita apenas remote HTTP/SSE. Recomendação: bloquear stdio inicialmente.
2. Discovery cache: decidir se fica em `config` ou em tabela dedicada. Recomendação: começar em `config` e extrair depois se houver histórico/versionamento.
3. Migração de `http_mcp`: decidir se altera dados imediatamente ou mantém alias por uma release. Recomendação: alias primeiro, migration depois.
4. Secrets em MCP: definir padrão de `secret_ref` comum para HTTP headers e MCP server headers/env.
5. Naming público: expor `HTTP Tool` e `MCP Tool`; não usar “MCP HTTP”.

## 8. Fora de escopo neste plano

- Implementar runtime MCP.
- Alterar tabelas, enums ou endpoints.
- Modificar frontend.
- Abrir PR automaticamente.
- Executar migração de dados.
