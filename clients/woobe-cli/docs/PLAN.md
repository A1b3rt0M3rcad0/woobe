# Woobe CLI — planejamento completo de implantação

**Data:** 4 de outubro de 2026  
**Status:** especificação proposta para implementação; não representa funcionalidades já entregues.  
**Objetivo:** oferecer manipulação completa da Woobe por terminal, com organização por Workspace e Project, autoridade granular, categorias personalizadas e operação consistente em uso humano, CI/CD e ferramentas de desenvolvimento.

**Decisão de implementação:** o CLI será desenvolvido em **Go**, como cliente externo e agent-friendly. O protótipo Python encontrado é referência histórica de comportamento e contratos, não a base de implementação do novo CLI.

## Assistant skill delivery addendum — 2026-10-08

The native client embeds the portable skill and provides offline
`woobe skill install/status/uninstall/agents`. The separate `woobe-cli-skill`
npm distribution is optional and shares the same payload/receipts.
It bundles portable Agent Skills instructions and offline references, not runtime
Woobe Skill resources. The explicit installer supports project/user scope for
Codex, legacy .codex, Claude Code, Copilot, Cursor and custom skills directories.
It preserves edited/unmanaged files and configuration, uses managed receipts,
locks and rollback, and does not perform authentication/API operations.

Both npm packages share calculated release version/source SHA; all six native
runners install their actual tarballs offline. Skill npm publication is gated
until its own first-publication/Trusted Publisher setup. The CLI publisher stays
independent. See [AGENT_SKILL.md](AGENT_SKILL.md), [CI.md](CI.md) and
[INDEX.md](INDEX.md). The original 101-item roadmap below remains an independent
historical plan; this addendum does not alter its acceptance ledger.

## 1. Decisão central

Construir um cliente do control plane da Woobe que permita executar todas as operações administrativas públicas suportadas pelo servidor, desde a consulta mínima até a administração máxima dos escopos explicitamente autorizados.

A capacidade máxima do CLI e a autoridade da credencial são conceitos independentes:

- **Cobertura máxima:** o CLI consegue expressar todas as operações públicas suportadas, com comandos específicos, documentos de configuração e acesso HTTP genérico.
- **Autoridade mínima:** uma credencial pode receber somente uma operação, sobre um Project determinado, sem acesso aos demais Projects ou à administração do Workspace.
- **Autoridade máxima:** uma credencial recebe o conjunto explicitamente concedido de permissões do Workspace e dos Projects selecionados. Isso não concede acesso a outros Workspaces, a Projects futuros nem a operações internas.
- **Manipulação mínima:** comandos simples, parâmetros essenciais e contexto previamente selecionado.
- **Manipulação avançada:** controle de configurações, bindings, contratos, versões, releases, ambientes, credenciais, grants, importação, exportação e aplicação declarativa.

Não criar um segundo mecanismo de autorização no CLI. O servidor autentica, resolve o proprietário do recurso e decide cada operação. As verificações locais servem para antecipar erros e melhorar a experiência.

## 2. Base efetivamente estudada

### 2.1. Repositórios e referências

| Fonte | Referência observada | Conclusão |
| --- | --- | --- |
| `A1b3rt0M3rcad0/woobe`, antiga ProjectRAI | `master` em `42e6667008db4e1306c05714af7a0df5b3ce7dd2` | Base atual do domínio, API e runtime. |
| Mesmo repositório, `feat/cli-control-plane` | `177d580eaaca4ee8743e1125c440cc3a25f0d76e` | Possui Control Keys, grants por Project, catálogo granular e CLI mínimo em Python. |
| `A1b3rt0M3rcad0/woobe-cli` | Repositório sem conteúdo retornado na descoberta | Destino reservado; não presumir CLI implementado nesse repositório. |
| `A1b3rt0M3rcad0/woobe-sdk-go` | `master` em `5a78817a64dc5dcb15aa1d38ec54d4c289f7f56c` | SDK Go de runtime, não cliente administrativo completo. |
| `A1b3rt0M3rcad0/woobe-sdk` | `master` em `70265537d2ac3eddd2738c56d671b189794c5e5b` | SDK Python de runtime, separado do control plane. |

A avaliação foi estática: documentação, código, rotas, contratos e testes existentes. Não foi realizada execução da stack, validação de CI nem smoke em uma instalação Woobe. Existência de rota não comprova funcionamento com todos os tipos de principal.

**Confiança:** alta sobre os contratos encontrados nessas referências; implementação de categorias em outra branch ou alterações posteriores precisam ser reconciliadas na etapa inicial.

### 2.2. O que já existe

| Item | Situação |
| --- | --- |
| Workspace e membros | `identity` possui Workspace, WorkspaceMember, WorkspaceInvite e UserSession. |
| Papéis humanos | Enum com `owner`, `admin`, `member` e `viewer`. |
| Project | Boundary técnico com identificação do Workspace proprietário. |
| Acesso humano a Projects | Owner possui acesso implícito; os demais usam vínculos explícitos para acesso operacional, com caminhos administrativos específicos. |
| Múltiplas Networks | Cada Project pode possuir várias Agent Networks. |
| Chaves na master | Project API Keys, Runtime Keys e ChatSurface Access Keys. |
| Escopos de Project API Key | `runtime:execute`, `traces:read` e `usage:read`. |
| Runtime Keys | Target Agent ou Network, ambiente staging/production e interfaces permitidas. |
| Control Keys | Implementadas na branch do CLI; pertencem a um Workspace e possuem grants por Project. |
| Catálogo de controle | Branch do CLI contém **7 permissões de Workspace e 43 de Project**, totalizando **50**. |
| CLI inicial | `packages/woobe-cli` na branch: Python ≥ 3.11, argparse, transporte HTTP e comandos `request` e `control-key`. |
| Delegação de Control Keys | Concessão por subconjunto e impedimento de manipular a própria linhagem de credencial. |
| Ferramentas agentic | HTTP e MCP; permissões de ferramentas são distintas da autorização administrativa. |
| Execução | Runs e Sessions distintos; produção resolve snapshots/releases imutáveis. |

### 2.3. Categorias de autoridade: requisito informado e evidência encontrada

O usuário informa que já criou categorias de autoridade e a possibilidade de criar novas. Esse requisito deve ser preservado.

Nas duas referências inspecionadas, o que foi identificado concretamente é:

1. Enum de papéis humanos.
2. Catálogo estático de permissões do control plane.
3. Grants por Project nas Control Keys.
4. Normalização que rejeita identificadores de permissão fora das listas conhecidas.

Não foi encontrada nessas referências uma entidade persistida de categoria personalizável, nem um CRUD HTTP correspondente. Portanto, este plano especifica o contrato que o CLI precisa consumir, sem afirmar que essa parte já esteja na master.

Na implementação, localizar a definição existente citada pelo usuário. Se estiver em outra branch, reutilizar sua entidade, nomes, IDs e contratos. Somente implementar a extensão descrita aqui quando ela estiver realmente ausente. Não criar um segundo cadastro concorrente.

### 2.4. Dependências concretas da integração

A comparação entre master e a branch do CLI retornou **132 commits à frente e 214 atrás**. A branch está divergente; não deve ser tratada como continuação direta da master.

Também existe colisão de migrações:

| Master | Branch do CLI |
| --- | --- |
| `0072_provider_model_specs.py` | `0072_workspace_control_keys.py` |
| `0073_agent_release_model_specs.py` | Migração de Control Keys declara `revision = "0072"` e `down_revision = "0071"`. |

**Procedimento:** abrir uma branch nova a partir da master atual e portar seletivamente o trabalho do control plane. Gerar uma revisão Alembic livre a partir do head efetivo; não copiar o identificador `0072` da branch nem reescrever migrações já integradas.

## 3. Escopo e boundaries

| Camada | Responsabilidade |
| --- | --- |
| CLI | Comandos, seleção de contexto, leitura de arquivos, apresentação, composição de operações e recuperação de transporte. |
| Control Plane HTTP | Autorização de operações administrativas e contratos de recursos. |
| Core | Regras de domínio, tenancy, grants, categorias, credenciais, versões e persistência. |
| Runtime HTTP/SDK | Executar e acompanhar Runs de targets publicados. |
| Workers | Execução assíncrona e demais tarefas da Woobe. |
| Observer | Captura e exportação passiva dos eventos do runtime. |

O CLI comunica-se pela API pública. Não importa o Core Python para manipular entidades, não abre PostgreSQL/Redis/MongoDB, não publica mensagens diretamente no RabbitMQ e não reconstrói releases fora do servidor.

WOS, WKS e WOSIS não se tornam cadastros internos do CLI da Woobe. O CLI poderá configurar uma Tool HTTP/MCP ou uma estratégia suportada pela Woobe para consumir esses serviços. A administração dos serviços independentes pertence aos respectivos contratos.

O plano contempla identidade, Workspaces, Projects, Agents, Networks, releases, environments, Tools, Knowledge, providers, models, Skills, chaves, Sessions, Runs, traces, uso e ChatSurfaces. Bootstrap da instância é um fluxo administrativo separado. Emissão de eventos internos de metering e fabricação de traces não fazem parte da administração funcional.

## 4. Arquitetura recomendada do cliente

### 4.1. Implementação e localização

**Decisão obrigatória:** implementar o CLI em Go, no repositório `A1b3rt0M3rcad0/woobe-cli`, com executável `woobe`. Esse repositório passa a ser a fonte canônica do novo cliente. A API/Core da plataforma mantém sua implementação atual; a linguagem do servidor não determina a linguagem do cliente externo.

| Elemento | Decisão | Uso |
| --- | --- | --- |
| Linguagem | Go, com versão suportada fixada em `go.mod` e no CI na Fase 0. | Cliente completo e binário distribuível. |
| Framework de comandos | Cobra, com versão fixada em `go.mod`/`go.sum`. | Subcomandos, flags, help e completion; metadados para agentes são definidos pelo próprio CLI. |
| Cliente administrativo | Implementação própria sobre `net/http`. | Workspaces, Projects, categorias, grants, Agents, Networks e demais operações de controle. |
| Runtime | Adapter para `woobe-sdk-go`, com versão fixada. | Executar e acompanhar Runs nos contratos efetivamente suportados pelo SDK. |
| Protótipo Python | Referência dos comandos `request`/`control-key`, variáveis e contratos observados. | Portar comportamento selecionado para Go; não executar Python para operar o CLI. |
| SDK Python | Referência comparativa de contratos de runtime. | Não é dependência do novo CLI. |

Control Keys, grants, guards e categorias pertencem ao backend da Woobe e devem ser integrados no repositório da plataforma `woobe`. O CLI Go, no repositório `woobe-cli`, os consome pela API pública. Não presumir que `woobe-sdk-go` já ofereça CRUD administrativo nem ampliar sua responsabilidade como pré-requisito para construir o CLI.

`packages/woobe-cli` da branch estudada permanece identificado como protótipo histórico. Planejar sua depreciação após o CLI Go cobrir os comportamentos compatíveis documentados. Não publicar duas implementações concorrentes sob o mesmo executável; definir migração de instalação, contextos e credenciais protegidas.

As escolhas de Cobra e organização de módulos foram verificadas nas fontes oficiais: [Cobra](https://github.com/spf13/cobra) e [Organizing a Go module](https://go.dev/doc/modules/layout). As versões concretas serão fixadas no início da implementação; este documento não declara uma versão mais recente sem verificação naquela etapa.

### 4.2. Divisão interna proposta

| Caminho no repositório `woobe-cli` | Conteúdo |
| --- | --- |
| `go.mod`, `go.sum` | Module, versão de Go e dependências fixadas. |
| `cmd/woobe/main.go` | Entrada mínima, sinais, composição e único ponto de aplicação do exit code. |
| `internal/cli/root.go` | Árvore Cobra, flags globais e injeção de dependências. |
| `internal/cli/auth.go` | Autenticação, credenciais e convites do usuário. |
| `internal/cli/context.go` | Perfis e seleção local de escopos. |
| `internal/cli/workspace.go` | Workspace, membros, convites e autoridade. |
| `internal/cli/project.go` | Project, acesso, overview e environment keys. |
| `internal/cli/keys.go` | Control Keys, Project API Keys, Runtime Keys e Surface Keys. |
| `internal/cli/agent.go` | Definição, prompts, contratos, modelos, bindings e releases. |
| `internal/cli/network.go` | Networks, draft, versões, ativações e composição. |
| `internal/cli/tool.go` | HTTP/MCP, descoberta, permissões e autenticação suportada. |
| `internal/cli/knowledge.go` | Collections, Documents, pesquisa e snapshots. |
| `internal/cli/catalog.go` | Catálogos de providers, modelos e estratégias. |
| `internal/cli/runtime.go` | Runs, Sessions, streams, cancelamento e reattach. |
| `internal/cli/observability.go` | Traces, diagnósticos e uso. |
| `internal/cli/surface.go` | ChatSurface e suas Access Keys. |
| `internal/cli/manifest.go` | Validate, diff, plan, apply e export. |
| `internal/application/` | Composição de fluxos do cliente; nenhuma autorização definitiva. |
| `internal/controlplane/` | Cliente administrativo, transport, envelopes, upload e paginação. |
| `internal/identity/` | Sessão humana, cookie jar, CSRF e renovação. |
| `internal/runtime/` | Adapter para SDK Go de runtime e endpoints necessários. |
| `internal/contracts/` | DTOs administrativos e representação explícita de campos presentes/null/omitidos. |
| `internal/config/` | Contextos locais, referências de credenciais e precedência. |
| `internal/credentials/` | Interfaces e adapters para armazenamento protegido por plataforma. |
| `internal/output/` | Table, JSON, JSONL, erros tipados e mapeamento de exit codes. |
| `internal/operations/` | Registro único de comandos, efeitos, capacidades, schemas e compatibilidade. |
| `internal/manifest/` | Validação, grafo de dependências, diff, plano, apply e checkpoints. |
| `schemas/` | Schemas versionados de entrada, saída e manifestos distribuídos com o binário. |
| `testdata/` | Fixtures sanitizadas de contratos, streams e cenários. |
| `tests/e2e/` | Testes do executável contra instalação de teste da Woobe. |
| `docs/`, `.github/workflows/` | Documentação e pipelines de validação/distribuição. |

Handlers Cobra chamam serviços do cliente; esses serviços chamam adapters HTTP ou o adapter do SDK Go. Interfaces pequenas ficam próximas dos consumidores e permitem fake transport, relógio e provedores de credenciais nos testes. Os nomes de arquivos acima orientam a divisão inicial; famílias grandes podem ser separadas em mais arquivos dentro do mesmo pacote.

### 4.3. Requisitos técnicos da implementação Go

- Propagar `context.Context` por chamadas HTTP, SDK e fluxos compostos. Usar `signal.NotifyContext` na entrada; interrupção local do acompanhamento não cancela uma Run remota implicitamente.
- Reutilizar `http.Client`/transport configurados, definir timeouts por operação, fechar response bodies e respeitar cancelamento. Upload e streaming devem evitar carregar todo o conteúdo em memória.
- Usar `net/http/cookiejar` para a sessão em memória; persistência protegida e restauração de cookies exigem implementação explícita, não são fornecidas automaticamente pelo jar padrão.
- Preferir biblioteca padrão para HTTP, JSON, context, sinais e erros. Evitar dependências adicionais para comportamentos já cobertos; não introduzir Viper como segunda fonte implícita de precedência.
- Usar `encoding/json` com preservação contratada de campos extensíveis. DTOs de PATCH devem distinguir campo ausente, `null` e valor vazio; `omitempty` isoladamente não resolve essa distinção.
- Definir erros tipados com `errors.Is`/`errors.As`, request ID, status e resultado conhecido/desconhecido. A camada de comando não produz erro textual como único contrato para agentes.
- Injetar `io.Reader`/`io.Writer` para stdin/stdout/stderr. Desabilitar duplicação automática de usage/erro no modo estruturado; toda renderização passa pelo contrato de output.
- Schemas e metadados estáticos podem ser distribuídos por `go:embed`; capabilities e permissões efetivas continuam vindo do servidor.
- Fixar dependências e toolchain; impedir dependência operacional de Python, de bibliotecas internas do Core ou de acesso direto a bancos da plataforma.

### 4.4. Caminho de autorização

~~~mermaid
flowchart TD
    CLI["CLI ou cliente HTTP"] --> API["API Woobe"]
    API --> AUTH["Autenticação do principal"]
    AUTH --> SCOPE["Workspace e Project do recurso"]
    SCOPE --> POLICY["Permissão e condições da operação"]
    POLICY --> DOMAIN["Regra do domínio"]
    DOMAIN --> RESULT["Resultado e auditoria"]
~~~

Uma chamada feita por `woobe request` deve passar exatamente pela mesma autorização de uma chamada feita por um comando específico.

## 5. Modelo de contexto e hierarquia de comandos

### 5.1. Gramática pública

~~~text
woobe <grupo> <recurso ou ação> [identificadores] [opções]
~~~

Grupos canônicos:

| Grupo | Escopo |
| --- | --- |
| `auth` | Identidade humana, importação de chave e estado da credencial. |
| `context` | Configuração local do cliente. |
| `workspace` | Workspace, membros, convites, Control Keys e categorias de autoridade. |
| `project` | Project e todos os recursos administrativos internos. |
| `runtime` | Execução e acompanhamento de targets. |
| `permission` | Catálogo, consulta de autoridade efetiva e explicação de acesso. |
| `manifest` | Gestão declarativa e operações compostas. |
| `request` | Acesso HTTP genérico autorizado. |
| `doctor` | Diagnóstico de conectividade, versão e capabilities. |
| `help` / `schema` | Descoberta de comandos e schemas legíveis por humanos e agentes. |
| `completion` | Autocompletar suportado pela distribuição. |
| `version` | Versão do cliente e compatibilidade. |

Exemplos:

~~~bash
woobe workspace list
woobe project list --workspace <workspace-id>
woobe project agent list --workspace <workspace-id> --project <project-id>
woobe project network draft update <network-id> --file network.json
woobe workspace control-key create --file control-key.json
woobe workspace authority category create --file publisher.json
~~~

Os comandos de Project aceitam `--workspace` e `--project`. Após selecionar um contexto, esses flags podem ser omitidos nas operações em que o contexto é suficiente.

Aliases curtos como `woobe agent`, `woobe network` e `woobe control-key` podem apontar para a mesma implementação canônica. Preservar `woobe control-key` e `woobe request` do protótipo existente. Não duplicar handlers.

### 5.2. Identificação dos recursos subordinados

Uma ação sobre prompt, contrato, release ou ambiente precisa identificar o Agent/Network pai. Não usar o primeiro target do Project nem interpretar o ID da release como ID do target.

Convenção alvo:

- Ações de Network recebem `<network-id>`; versões usam `--version <version-id>`.
- Ações de Agent subordinadas a releases recebem `--agent <agent-id>` além do ID da release.
- List/create de prompt, contrato ou model-config exigem `--agent <agent-id>`.
- Comandos de Tool/Collection/Surface recebem ID do recurso ou documento com essa referência explícita.

~~~bash
woobe project agent release get <release-id> --agent <agent-id>
woobe project agent release activate <release-id> --agent <agent-id> --environment production
woobe project network release get <network-id> --version <version-id>
~~~

As tabelas de comandos abreviam opções comuns. Help e schema publicados devem mostrar todos os IDs exigidos pela operação.

### 5.3. Seleção local

~~~bash
woobe context create local --api-url http://localhost:8000
woobe context credential attach local --credential dev-control
woobe context use local
woobe context set --workspace <workspace-id> --project <project-id>
woobe context show
~~~

Cada contexto contém:

- Origem da API.
- Referência local da credencial administrativa.
- Workspace selecionado.
- Project selecionado, quando aplicável.
- Referências de Runtime Keys por target e ambiente.
- Formato padrão de apresentação.
- Preferências locais como readonly e limites de paginação.

As referências locais não constituem grants. Alterar o contexto não altera o servidor.

### 5.4. Precedência e integridade

Ordem: **flag explícito → variável de ambiente → contexto ativo → default documentado**.

- Manter compatibilidade com `WOOBE_API_URL` e `WOOBE_API_KEY` do CLI inicial.
- Aceitar `WOOBE_BASE_URL` como alias documentado; valores diferentes configurados simultaneamente geram erro.
- Introduzir `WOOBE_WORKSPACE_ID`, `WOOBE_PROJECT_ID` e referências de Runtime Keys com namespace próprio.
- Não escolher automaticamente o primeiro Workspace ou Project de uma lista.
- Se nome/slug não identificar exatamente um recurso visível, retornar ambiguidade e exigir ID.
- O CLI pode exigir contexto mais explícito para ergonomia; o servidor sempre verifica os IDs efetivos.
- Não trocar automaticamente de credencial após `403` ou `404`.
- Payload e contexto que especificam Projects diferentes devem gerar conflito.
- Configuração local persistente deve excluir segredos; arquivos de manifesto não incluem credenciais em texto puro.

### 5.5. Opções transversais

| Opção | Semântica |
| --- | --- |
| `--context` | Perfil local usado nesta invocação. |
| `--workspace` / `--project` | Escopo explícito. |
| `--output table\|json\|jsonl` | Representação determinística. |
| `--file` / `--stdin` | Entrada de documento JSON; YAML opcional após parser definido. |
| `--limit` / `--cursor` / `--all` | Paginação conforme capacidade do endpoint. |
| `--timeout` | Deadline de operação; não impor duração total curta a SSE. |
| `--read-only` | Bloqueio local adicional de operações com efeito; não concede permissões. |
| `--dry-run` | Validação/planejamento sem executar a mutação. |
| `--yes` | Confirmação não interativa de uma ação já especificada. |
| `--expected-revision` | Controle de concorrência quando suportado pelo servidor. |
| `--idempotency-key` | Identidade de uma operação quando o endpoint oferece esse contrato. |
| `--debug` | Diagnóstico sanitizado em stderr. |

`--all` não inventa paginação ausente. Endpoints que retornam apenas um limite fixo precisam de extensão antes de prometer exportação completa.

## 6. Principals, credenciais e limites

| Principal/credencial | Finalidade | Boundary |
| --- | --- | --- |
| Sessão humana | Operações autorizadas por membership e política de papéis. | Workspaces e Projects acessíveis ao usuário. |
| Control Key | Administração por CLI, CI/CD ou ferramentas. | Exatamente um Workspace e grants explícitos por Project. |
| Project API Key | Capacidades atuais de execução/observação/uso. | Um Project e scopes suportados. |
| Runtime Key | Consumir um Agent ou Network publicado. | Um target, ambiente e interfaces. |
| ChatSurface Access Key/token | Acesso à superfície e sua sessão pública. | Contrato da ChatSurface. |

**Regras obrigatórias:**

1. Control Key não substitui Runtime Key para executar `/v1/run`.
2. Runtime Key não cria Project, Agent, Network ou permissões.
3. Identificador de target/alias no CLI não sobrepõe o binding da Runtime Key.
4. A CLI pode manter múltiplas credenciais, mas cada chamada informa claramente qual tipo usa.
5. O segredo é retornado somente em emissão/rotação; list/get mostram metadados.
6. A linhagem `credential_id` continua estável após rotação.
7. Chave não altera, revoga nem rotaciona a própria linhagem quando essa operação é proibida pelo contrato de Control Keys.
8. Autoridade máxima de uma Control Key continua subordinada à tenancy, às condições do recurso e aos contratos de domínio.

### 6.1. Autenticação humana inicial

A master retorna access/refresh tokens em cookies, não como bearer público no corpo de login. O CLI deverá manter cookie jar, respeitar expiração e enviar CSRF para operações feitas com autenticação por cookie.

Implementar:

- Login com senha por entrada protegida, sem argumento de senha no histórico.
- Renovação de sessão respeitando a rotação existente.
- Exclusão do estado local e logout remoto.
- Importação de Control Key por stdin ou provedor de credenciais.
- Estado da credencial sem expor valor.
- Armazenamento protegido da sessão; configuração comum contém somente referência.

Login por device flow próprio da Woobe é uma extensão futura. Os endpoints de device flow encontrados para MCP autenticam o servidor MCP; não são login da conta Woobe.

### 6.2. Armazenamento e emissão de segredos

Preferir credenciais externas/armazenamento do sistema operacional; permitir arquivos protegidos quando esse provider não estiver disponível.

A criação/rotação deve aceitar `--secret-file <path>` ou importação imediata em um provider. A resposta JSON comum contém ID, prefixo, escopo e expiração, sem segredo. Revelação em stdout exige opção explícita, documentada para pipelines.

Não enviar bearer/cookies a outra origem em redirects. `request` aceita somente caminhos da origem configurada. Logs de debug removem Authorization, cookies, segredos de providers e environment keys.

## 7. Catálogo existente de permissões

Os identificadores abaixo são os encontrados na branch `feat/cli-control-plane`. Devem ser preservados na integração; extensões novas precisam de migração/compatibilidade explícita.

### 7.1. Workspace — 7 permissões

| Permissão | Capacidade |
| --- | --- |
| `workspace:read` | Descoberta administrativa prevista para o Workspace, incluindo listagem de Projects concedidos. |
| `projects:create` | Criar Project no Workspace. |
| `keys:read` | Consultar metadados de Control Keys. |
| `keys:create` | Emitir Control Key dentro da autoridade delegável. |
| `keys:update` | Alterar metadados, permissões e grants permitidos. |
| `keys:revoke` | Revogar outra credencial gerenciável. |
| `keys:rotate` | Rotacionar outra credencial gerenciável. |

`workspace:read` não prova que as rotas humanas `/identity/workspaces` estejam acessíveis a Control Keys: esse acesso precisa ser implementado explicitamente.

### 7.2. Project — 43 permissões

| Família | Identificadores existentes |
| --- | --- |
| Project | `project:read`, `project:update` |
| Environment keys | `project:environment:read`, `project:environment:write` |
| Acesso ao Project | `project:access:read`, `project:access:write` |
| API/Runtime Keys | `api_key:read`, `api_key:write` |
| Agent | `agent:read`, `agent:write`, `agent:delete`, `agent:version`, `agent:production` |
| Network | `network:read`, `network:write`, `network:delete`, `network:version`, `network:production` |
| Tool | `tool:read`, `tool:write`, `tool:delete`, `tool:execute` |
| Knowledge | `knowledge:read`, `knowledge:write`, `knowledge:delete` |
| Provider | `provider:read`, `provider:write`, `provider:delete`, `provider:credential:rotate`, `provider:credential:revoke` |
| Model | `model:read`, `model:write`, `model:delete` |
| Skill | `skill:read`, `skill:write`, `skill:version` |
| ChatSurface | `chat_surface:read`, `chat_surface:write`, `chat_surface:release`, `chat_surface:keys` |
| Run | `run:read` |
| Observability | `observability:read` |
| Uso | `usage:read` |

### 7.3. Extensões propostas

| Necessidade | Contrato a adicionar |
| --- | --- |
| Gerenciar metadados do Workspace com Control Key | `workspace:update`. |
| Ler/gerenciar membros e convites | Permissões explícitas de `workspace:members:*` e `workspace:invites:*`. |
| Catálogos de estratégias/provider capabilities | `catalog:read`, limitado aos dados de catálogo publicáveis. |
| CRUD/versionamento de categorias | `authority:read`, `authority:create`, `authority:update`, `authority:delete`. |
| Ambientes de execução | Permissões por target e operação, com separação de staging/production. |
| Consultar Sessions e mensagens | `session:read` e projeções de dados autorizadas. |
| Criar/resetar Sessions pelo control plane | Permissões próprias; não inferir autorização de `agent:write`/`network:write`. |
| Acompanhar/cancelar/rerun administrativo | `run:observe`, `run:cancel` e `run:rerun`; runtime continua com suas chaves. |
| Separar leitura e emissão de Surface Keys | Desagregar `chat_surface:keys` em permissões distintas, com compatibilidade. |
| Auditoria administrativa | `audit:read`, diferente de tracing de execução. |

Não inventar novos scopes dentro da credencial em tempo de execução. Uma permissão nova só existe quando o backend registra sua semântica e a associa a operações reais.

## 8. Categorias de autoridade personalizáveis

### 8.1. Semântica

Uma categoria é um **perfil reutilizável e versionado de permissões**. Ela facilita conceder autoridade conhecida; não cria comportamento novo no servidor.

Separar:

| Conceito | Exemplo | Responsabilidade |
| --- | --- | --- |
| Papel humano | `owner` / `admin` | Membership e regras estruturais existentes. |
| Categoria de autoridade | `study-content-editor` | Perfil versionado com operações permitidas. |
| Permissão | `agent:write` | Operação reconhecida pelo backend. |
| Grant | Categoria aplicada ao Project A | Vinculação da autoridade ao escopo concreto. |
| Binding de execução de Tool | MCP `allow` / `deny` / `review` | Capacidade disponível ao Agent durante execução. |
| Preferência local do CLI | `--read-only` | Limite adicional de interação do cliente. |

Criar a categoria `owner` ou `admin` não transforma seu usuário em proprietário do Workspace. Transferência de ownership exige use case próprio.

### 8.2. Contrato de categoria

Modelo lógico proposto; adaptar ao modelo já existente se localizado:

~~~json
{
  "api_version": "woobe.io/v1alpha1",
  "kind": "AuthorityCategory",
  "workspace_id": "<workspace-id>",
  "name": "study-content-editor",
  "description": "Editar configuração pedagógica sem publicar em produção",
  "revision": 1,
  "scope": "project",
  "permissions": [
    "project:read",
    "agent:read",
    "agent:write",
    "network:read",
    "network:write",
    "knowledge:read",
    "knowledge:write",
    "skill:read",
    "skill:write",
    "skill:version"
  ],
  "status": "active",
  "system": false
}
~~~

Campos persistidos: ID, Workspace proprietário, slug/nome, descrição, tipo de escopo, revisão, conjunto normalizado de permissões, status, autoria e timestamps.

Regras:

1. Categorias de usuário pertencem a exatamente um Workspace.
2. Categoria de Project usa permissões de Project; categoria de Workspace usa permissões de Workspace.
3. Quando for necessário um perfil combinado, usar composição explícita dos dois escopos, sem misturar namespaces em um grant.
4. Categorias do sistema podem ser consultadas e clonadas; sua semântica é versionada.
5. Nome único por Workspace e tipo de escopo.
6. IDs de permissões desconhecidos ou de escopo incompatível são rejeitados.
7. Primeira versão usa conjuntos allow-only. A ausência de concessão significa negar.
8. Não introduzir herança recursiva ou precedência allow/deny sem necessidade comprovada.
9. Wildcards são expandidos pelo servidor para uma lista finita usando uma revisão explícita do catálogo.
10. Atualizar uma categoria cria nova revisão; credenciais existentes não ganham permissões automaticamente.

### 8.3. Aplicação de uma categoria

Na concessão, o servidor:

1. Resolve categoria e revisão.
2. Valida que pertencem ao Workspace correto.
3. Expande a lista concreta de permissões.
4. Verifica a autoridade delegável do ator para aquele Project.
5. Persiste as permissões concretas do grant e a referência da revisão aplicada.
6. Registra evento de concessão.

A autorização de cada chamada continua usando o grant efetivo. A categoria é a origem auditável da concessão, não uma consulta mutável que amplia autoridade silenciosamente.

A atualização dos grants após editar a categoria exige operação explícita de reconciliação, com diff. Redução emergencial de acesso deve poder ocorrer por revogação da credencial/grant; não depender da alteração da categoria.

### 8.4. Perfis iniciais propostos

| Categoria | Autoridade |
| --- | --- |
| `project-reader` | Consultas administrativas do Project, sem execução, emissão de keys ou leitura de segredos. |
| `agent-editor` | `agent:read` e `agent:write` no Project concedido. |
| `network-editor` | `network:read` e `network:write` no Project concedido. |
| `knowledge-editor` | Consultar e alterar Knowledge; exclusão somente quando concedida separadamente. |
| `version-builder` | Criar e testar versões em staging dos targets explicitamente autorizados. |
| `production-publisher` | Publicação/rollback de releases; não recebe edição de draft por inferência. |
| `runtime-observer` | Consultar Runs/traces/uso com projeção adequada. |
| `project-administrator` | Todas as permissões de Project da revisão selecionada, apenas nos Projects vinculados. |
| `workspace-key-manager` | Gerenciar Control Keys dentro da autoridade delegável. |
| `custom` | Conjunto explícito escolhido pelo administrador autorizado. |

O conjunto exato de cada perfil deve ser devolvido pelo servidor, com ID/revisão. O CLI não mantém listas autoritativas hardcoded.

### 8.5. Autoridade mínima e máxima

~~~json
{
  "name": "agent-read-only",
  "permissions": [],
  "project_grants": [
    {
      "project_id": "<project-a-id>",
      "permissions": ["agent:read"]
    }
  ]
}
~~~

Esse grant é válido para leitura direta de Agents do Project A. Não pressupõe permissão para listar todos os Projects; a navegação poderá exigir `workspace:read`/`project:read` adicionais explicitamente selecionadas.

Para uma credencial máxima:

- Selecionar o Workspace.
- Selecionar a revisão de catálogo.
- Selecionar cada Project.
- Expandir todas as permissões autorizadas para esses escopos.
- Definir expiração e demais condições.
- Mostrar o resultado concreto antes da emissão.

“Máximo” nunca significa `*` irrestrito, outro Workspace, todos os Projects futuros ou acesso interno ao banco.

## 9. Autorização efetiva e delegação

### 9.1. Regra de decisão

Uma operação é permitida somente se forem verdadeiros:

- Principal autenticado e ativo.
- Credencial/sessão válida e não expirada.
- Workspace correto.
- Project/recurso resolvido ao proprietário correto.
- Membership/grant aplicável.
- Permissão da operação e condições de ambiente/target.
- Regra de domínio satisfeita.
- Projeção de campos autorizada.

Para Control Keys, a união de permissões de categorias nunca ultrapassa o grant materializado. Para uma credencial derivada, o conjunto concedido precisa caber na autoridade delegável do ator para cada escopo.

### 9.2. Regras de delegação preservadas e complementadas

**Preservar da branch:**

- Concessões apenas a Projects do mesmo Workspace.
- Subconjunto de permissões do ator.
- Não gerenciar credencial com grants mais amplos que os próprios.
- Não manipular a própria linhagem.
- Segredos somente na emissão/rotação.

**Complementar antes da entrega:**

- Expiração derivada não ultrapassa o teto de delegação aprovado; não permitir remover esse teto por rotação.
- Uma categoria ampla não permite contornar a comparação de subconjunto.
- Um ator humano passa por sua política efetiva; o enum `admin` não deve servir como autorização universal de delegação.
- Emissão de Project/Runtime Keys considera também target, ambiente, interfaces e expiração. Comparar strings de Control Permissions com Runtime scopes não resolve essa delegação.
- Operações sobre permissões e credenciais precisam de controle de concorrência para evitar sobrescrita de grants.
- Revalidação de permissões ocorre no servidor, inclusive após revogação e mudança de estado.

A branch concede todas as 43 permissões de Project à Control Key que possui `projects:create` quando cria um Project. Esse comportamento está implementado e precisa ser explícito.

Para suportar criação com autoridade mínima, adicionar política de permissões recebidas pelo criador, por exemplo `on_project_create_permissions`. O conjunto deve ser validado na emissão da chave e limitado ao teto de criação delegável. Uma chave derivada não pode escolher um teto maior. Esse campo é extensão proposta, não contrato atual.

### 9.3. Papéis humanos

O enum contém `viewer`, mas sua existência não prova enforcement de leitura em todos os endpoints. Nos caminhos estudados, tenancy valida ownership/membership, e várias mutações continuam precisando de classificação por operação.

A política alvo deve definir e testar:

| Papel | Política alvo |
| --- | --- |
| Owner | Ownership e administração do Workspace; autoridade operacional conforme regras estruturais. |
| Admin | Administração delegada; sem promover usuários a owner e respeitando teto de concessão. |
| Member | Operações concedidas nos Projects vinculados. |
| Viewer | Somente leitura autorizada nos Projects vinculados. |

Preservar a distinção entre listar Projects para administração de acesso e possuir acesso operacional aos seus recursos. Na master, somente owner tem acesso implícito no caminho geral do TenantAuthorizer.

O endpoint atual de criação de convite aceita apenas `member` e `admin`, embora `viewer` exista no domínio. Suporte a convite viewer precisa de alteração explícita da API.

### 9.4. API de capacidades e explicação

Extensões propostas:

| Endpoint lógico | Responsabilidade |
| --- | --- |
| `GET /identity/access/me` | Principal atual, escopos visíveis e autoridade efetiva; nenhuma chave secreta. |
| `GET /identity/permissions` | Catálogo versionado e metadados dos identificadores. |
| `POST /identity/access/check` | Verificar uma operação sobre um recurso, sem executar a mutação. |
| `GET /identity/workspaces/{workspace_id}/authority-categories` | Catálogo de categorias visíveis no Workspace. |

Os nomes são propostas. Se existirem contratos equivalentes, reutilizá-los.

Introspecção do próprio principal é uma capacidade autenticada explícita, não depende de `keys:read` e não permite consultar outra credencial. Falta de acesso a um recurso continua retornando a resposta genérica definida pelo servidor; `explain` não revela recursos de outros tenants.

## 10. Inventário de comandos e contratos

Legenda:

| Marca | Significado |
| --- | --- |
| **M** | Rota/contrato localizado na master. |
| **F** | Implementação localizada na branch do CLI; requer integração seletiva. |
| **N** | Extensão necessária/proposta. |
| **L** | Operação local ou composição de leituras autorizadas. |
| **R** | Contrato público de runtime, com credencial adequada. |

As permissões indicadas para M são as do catálogo de Control Keys da branch, quando existe mapeamento. Isso não significa que a master já aceite Control Keys nessa rota.

Todos os caminhos abreviados nos próximos tópicos são caminhos HTTP, não comandos executados no banco.

## 10.1. Comandos locais e de autenticação

| Comando | Contrato | Situação |
| --- | --- | --- |
| `woobe version` | Versão, build e versões de protocolo suportadas. | L |
| `woobe doctor` | Verificar origem, TLS, health/readiness, autenticação e capabilities disponíveis. | M/L; capabilities N |
| `woobe help [command-path] --output json` | Descrever comandos, parâmetros, efeitos, permissões e compatibilidade a partir do registro local. | L |
| `woobe schema --command <command-path> --kind input\|output --output json` | Exportar schema versionado do contrato publicado pelo cliente; compatibilidade efetiva consultada no servidor. | L/N |
| `woobe completion <shell>` | Gerar script de completion da versão instalada. | L |
| `woobe context list/create/show/use/update/delete` | Gerenciar perfis locais. | L |
| `woobe context set --workspace ... --project ...` | Seleção local, validando referências visíveis quando houver conexão. | L |
| `woobe context credential attach/detach` | Vincular referência protegida, sem imprimir segredo. | L |
| `woobe auth login` | `POST /identity/auth/login`; cookies e CSRF. | M |
| `woobe auth logout` | `POST /identity/auth/logout` e limpeza local. | M/L |
| `woobe auth status` | Sessão: `GET /identity/users/me`; Control Key: introspecção própria. | M/N |
| `woobe auth refresh` | `POST /identity/auth/refresh`, respeitando rotação. | M |
| `woobe auth credential import/list/remove` | Referências locais de chaves; importação por stdin/provider. | L |
| `woobe auth invite list` | `GET /identity/invites/pending`. | M |
| `woobe auth invite accept <invite-id>` | `POST /identity/invites/{invite_id}/accept`. | M |
| `woobe auth register` | `POST /identity/auth/register`, somente quando a instância permitir. | M |
| `woobe instance status` | `GET /identity/instance/status`. | M |
| `woobe instance bootstrap` | `POST /identity/instance/bootstrap`; fluxo inicial separado e explícito. | M |

Registration e bootstrap não são pré-requisitos para uma automação já autenticada.

## 10.2. Workspace, membros e convites

| Comando | HTTP/efeito | Autoridade | Situação |
| --- | --- | --- | --- |
| `workspace list` | `GET /identity/workspaces`. | Sessão humana; descoberta própria para Control Key exige adaptação. | M/N |
| `workspace get <id>` | `GET /identity/workspaces/{workspace_id}`. | Membership; futura `workspace:read`. | M/N |
| `workspace create` | `POST /identity/workspaces`. | Usuário e política da instância. | M |
| `workspace update <id>` | `PATCH /identity/workspaces/{workspace_id}`. | Owner/admin; futura `workspace:update`. | M/N |
| `workspace member list` | `GET /identity/workspaces/{workspace_id}/members`. | Política de membership; permission explícita para Control Key. | M/N |
| `workspace member remove <user-id>` | `DELETE /identity/workspaces/{workspace_id}/members/{target_user_id}`. | Owner/admin e restrições sobre o alvo. | M/N |
| `workspace member role set <user-id>` | Use case de mudança de papel, com política de delegação. | Gestão de membros e teto do ator. | N |
| `workspace invite create` | `POST /identity/workspaces/{workspace_id}/invites`. | Regras atuais de papel; `project_ids` explícitos. | M/N |
| `workspace invite list` | `GET /identity/workspaces/{workspace_id}/invites`. | Owner/admin; permission explícita para Control Key. | M/N |
| `workspace invite cancel <invite-id>` | `DELETE /identity/workspaces/{workspace_id}/invites/{invite_id}`. | Restrições atuais sobre quem pode cancelar convite admin. | M/N |
| `workspace ownership transfer` | Fluxo específico, sem usar convite ou role genérico. | Owner e política própria. | N; posterior ao núcleo |

A remoção de membro deve apresentar o efeito retornado pelo servidor: membership removido, acessos a Projects removidos e concessões pendentes canceladas.

Não implementar `member add` como chamada ao endpoint legado: a master proíbe criação direta de membership e exige aceitação de convite.

Workspace não possui DELETE funcional localizado. Suspensão, fechamento ou exclusão do Workspace precisam de contrato próprio; não criar um comando que faça exclusão local ou SQL.

## 10.3. Autoridade, permissões e categorias

| Comando | Comportamento | Situação |
| --- | --- | --- |
| `permission list --scope workspace\|project` | Catálogo oficial, efeitos e revisão. | N |
| `permission get <permission-id>` | Operações associadas e condições. | N |
| `permission effective` | Autoridade do principal atual no contexto. | N |
| `permission check <operation-id> --resource <id>` | Avaliação sem executar a operação. | N |
| `permission explain <operation-id> --resource <id>` | Razões permitidas pelo contrato; não revela outro tenant. | N |
| `workspace authority category list/get` | Perfis visíveis e revisão. | N ou reutilização do cadastro existente |
| `workspace authority category create --file <path>` | Criar perfil com permissões reconhecidas. | N ou reutilização |
| `workspace authority category update <id> --file <path>` | Criar revisão com controle de concorrência. | N ou reutilização |
| `workspace authority category clone <id> --name <name>` | Criar categoria própria a partir de uma revisão. | N/L |
| `workspace authority category history <id>` | Revisões e autoria. | N |
| `workspace authority category diff <id> --from <rev> --to <rev>` | Diferença de permissões e condições. | N/L |
| `workspace authority category archive <id>` | Impedir novas concessões; preservar histórico. | N |
| `workspace authority category delete <id>` | Somente quando regra de referências permitir. | N |
| `workspace authority category export/import` | Documento versionado, sem grants ou credenciais implícitos. | N/L |
| `workspace authority assignment plan/apply` | Reconciliar revisão aplicada e grants selecionados. | N |

**Definição de completo:** categorias podem ser consultadas, criadas, atualizadas, clonadas e aplicadas sem mudança no código do CLI. A criação de novos comportamentos/permissões primitivas continua dependente do backend.

## 10.4. Control Keys e grants por Project

Base HTTP da branch: `/core/workspaces/{workspace_id}/control-keys`.

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `workspace control-key list` | GET da base. | `keys:read` | F |
| `workspace control-key get <key-id>` | Filtrar listagem autorizada inicialmente; GET próprio pode ser adicionado. | `keys:read` | L/N |
| `workspace control-key create --file <path>` | POST com permissions e project_grants. | `keys:create` + delegação | F |
| `workspace control-key update <key-id>` | PATCH; campos omitidos não são apagados. | `keys:update` + alvo gerenciável | F |
| `workspace control-key rotate <key-id>` | POST `/{control_key_id}/rotate`. | `keys:rotate` + alvo gerenciável | F |
| `workspace control-key revoke <key-id>` | POST `/{control_key_id}/revoke`. | `keys:revoke` + alvo gerenciável | F |
| `workspace control-key grant list` | Ler grants nos metadados da chave. | `keys:read` | F/L |
| `workspace control-key grant add/update/remove` | PATCH do conjunto ou subrecurso atômico proposto. | `keys:update` + subconjunto | F/N |
| `workspace control-key grant set-category` | Resolver categoria/revisão e persistir permissões concretas. | Delegação equivalente ao conjunto | N |
| `workspace control-key inspect-delegation` | Consulta de autoridade delegável própria. | Introspecção própria | N |
| `workspace control-key audit` | Eventos administrativos dessa credencial. | `audit:read` proposto | N |

O PATCH atual substitui o conjunto de grants quando fornecido. Para comandos de alteração incremental, não fazer read-modify-write sem proteção de revisão. Preferir subrecurso atômico ou PATCH condicional.

Distinguir ID da emissão e `credential_id` da linhagem. `rotate` retorna nova emissão; comandos devem informar ambos.

## 10.5. Project, acesso e overview

Base: `/core/projects`.

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project list` | GET com `workspace_id`. | `workspace:read` para Control Key; membership para humano | M/F |
| `project get <id>` | GET `/{project_id}`. | `project:read` | M |
| `project create` | POST com Workspace explícito. | `projects:create` / política humana | M/F |
| `project update <id>` | PATCH `/{project_id}`. | `project:update` | M |
| `project archive/restore <id>` | PATCH de status, após validar transições permitidas. | `project:update` | M; lifecycle completo a validar |
| `project overview` | GET `/{project_id}/overview`. | `project:read` | M |
| `project run list` | GET `/{project_id}/runs`; ledger de Agent/Network Runs. | `project:read` no mapeamento da branch | M |
| `workspace project-access list` | GET `/core/workspaces/{workspace_id}/project-access`. | Política administrativa; mapeamento de Control Key precisa ser acrescentado | M/N |
| `project member list` | GET `/{access_project_id}/members`. | `project:access:read` | M/F |
| `project access grant --subject-type member\|invite --subject-id ...` | POST `/{access_project_id}/access`. | `project:access:write` | M/F |
| `project access revoke --subject-type ... --subject-id ...` | DELETE `/{access_project_id}/access/{subject_type}/{subject_id}`. | `project:access:write` | M/F |
| `project member grant --email ...` | POST `/{access_project_id}/members`. | `project:access:write` | M/F |
| `project member revoke <user-id>` | DELETE `/{access_project_id}/members/{target_user_id}`. | `project:access:write` | M/F |

Grant de acesso humano ao Project e grant de Control Key são entidades diferentes. Os comandos não devem apresentar ambos como um único tipo de membro.

Acesso implícito do owner não pode ser revogado pela remoção de um vínculo de Project. O backend já diferencia esse caso.

## 10.6. Environment keys e chaves do Project

### Environment keys

| Comando | HTTP | Permissão |
| --- | --- | --- |
| `project env list` | GET `/core/projects/{project_id}/environment-keys`. | `project:environment:read` |
| `project env set <name> --stdin` | PUT `/core/projects/{project_id}/environment-keys/{key}`. | `project:environment:write` |
| `project env unset <name>` | DELETE do mesmo recurso. | `project:environment:write` |
| `project env usage <name>` | Projeção de `used_by_tools` retornada pelo servidor. | Leitura autorizada |
| `project env import --file <path>` | Composição de operações explícitas, com relatório por chave. | Escrita autorizada |

Rotas M. Rever o contrato de retorno para mascarar valores sensíveis no servidor; mascaramento apenas no terminal não implementa permissão de segredo. Exportação padrão contém nomes, metadados e referências, sem valores secretos.

### Project API Keys e Runtime Keys

| Comando | HTTP | Autoridade | Situação |
| --- | --- | --- | --- |
| `project api-key list` | GET `/core/projects/{project_id}/api-keys`, filtrando kind. | `api_key:read` | M |
| `project api-key create` | POST `/core/projects/{project_id}/api-keys`. | `api_key:write` e condições de emissão | M/F |
| `project api-key update <id>` | PATCH `/core/projects/{project_id}/api-keys/{api_key_id}`. | `api_key:write` | M/F |
| `project api-key rotate/revoke <id>` | POST no sufixo correspondente. | `api_key:write` | M/F |
| `project runtime-key list` | Mesma listagem, filtrando `kind=runtime`. | `api_key:read` | M/L |
| `project runtime-key create` | POST `/core/projects/{project_id}/runtime-keys`. | `api_key:write` e restrições de target/ambiente/interfaces | M/F |
| `project runtime-key update/rotate/revoke <id>` | Lifecycle de API Key conforme kind e contrato. | `api_key:write` | M/F |

Criação de Runtime Key exige `target_type`, `target_id`, `environment` e interfaces explícitas. `draft` não é ambiente permitido para Runtime Key. `jobs` está representado no enum, mas sua habilitação é rejeitada pelo DTO atual; não apresentá-lo como interface disponível.

Os scopes legados `reading`, `writing` e `admin` possuem normalização de compatibilidade. `custom` legado é rejeitado; ele não é a implementação das categorias personalizáveis.

## 10.7. Agents e configurações

Base administrativa: `/ai/agents`.

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project agent list/create` | GET/POST da base, com Project. | `agent:read` / `agent:write` | M |
| `project agent get/update <agent-id>` | GET/PATCH `/{agent_id}`. | `agent:read` / `agent:write` | M |
| `project agent delete <agent-id>` | DELETE `/{agent_id}`; branch usa lifecycle de status. | `agent:delete` | F |
| `project agent export <agent-id>` | Leitura e normalização de manifesto de configuração. | Permissões de leitura das partes exportadas | L |
| `project agent prompt list/get/create` | `/{agent_id}/prompts` e `/{version_id}`. | `agent:read` / `agent:write` | M |
| `project agent contract list/get/create/update` | `/{agent_id}/contracts` e `/{contract_id}`. | `agent:read` / `agent:write` | M |
| `project agent model-config list/get/create` | `/{agent_id}/model-configs` e `/{config_id}`. | `agent:read` / `agent:write` | M |
| `project agent tool list` | GET `/tools/agents/{agent_id}/tools`. | `tool:read` | M |
| `project agent tool bind/unbind` | Alteração dos bindings na definição, usando DTO do Agent. | `agent:write`; referências válidas | N/L sobre M |
| `project agent skill bind/unbind` | Definição de bindings/configuração suportada pelo Agent. | `agent:write`; versões de Skill válidas | N/L sobre M |
| `project agent collection list/bind/unbind` | `/knowledge/agent-collections` e DELETE `/{link_id}`. | `knowledge:read` / `knowledge:write`; rever detach atualmente classificado como delete | M |
| `project agent knowledge-version list/create` | `/knowledge/agents/{agent_id}/knowledge-versions`. | `knowledge:read` / `knowledge:write` | M |
| `project agent validate --file <path>` | Schema local e validação sem persistência proposta. | Consulta/preflight correspondente | L/N |

Bindings de Tool, Skill, Model e Knowledge precisam preservar o schema efetivo da Woobe. Não substituir a definição por um formato ad hoc do CLI.

O modelo de Agent deve permanecer extensível a tipos e modalidades. O CLI não impõe que todo Agent seja exclusivamente um LLM textual. ModelSpec e compatibilidade de Execution Strategy vêm do servidor.

### Prompts e contratos

- Prompt novo cria versão; não prometer atualização in-place onde só existe criação versionada.
- Alteração de contrato/draft não modifica o snapshot de uma release publicada.
- Contratos de output e External Context são diferentes e devem ser apresentados separadamente.
- Valores de External Context não são credenciais de autorização administrativa.
- Campos com scope session e run mantêm a semântica de lifecycle do runtime.

### Releases de Agent

| Comando | HTTP | Permissão | Situação |
| --- | --- | --- | --- |
| `project agent release list/create` | GET/POST `/ai/agents/{agent_id}/releases`. | `agent:read` / `agent:version` | M |
| `project agent release get <release-id>` | GET `/ai/agents/{agent_id}/releases/{release_id}`. | `agent:read` | M |
| `project agent release test <release-id>` | POST `/ai/agents/{agent_id}/release-tests` com referência explícita. | `agent:version`; teste executa trabalho real | M |
| `project agent release tests <release-id>` | GET `/{release_id}/tests`. | `agent:read` | M |
| `project agent release promote <release-id> --environment staging` | POST `/{release_id}/promote` com `target_status` correto. | Separação de staging precisa ser corrigida no mapper | M/N |
| `project agent release activate <release-id> --environment production` | Promotion/activation do contrato atual, preservando a identidade do snapshot. | `agent:production` | M |
| `project agent release rollback <release-id>` | POST `/{release_id}/rollback`. | `agent:production` | M |
| `project agent release delete <release-id>` | DELETE `/{release_id}`; regras do domínio continuam obrigatórias. | `agent:version` no catálogo atual | M |
| `project agent release activations` | GET `/ai/agents/{agent_id}/release-activations`. | `agent:read` | M |
| `project agent release diff <a> <b>` | Comparação local de snapshots autorizados. | `agent:read` | L |

A branch classifica todo POST de `promote` como `agent:production`, inclusive quando o corpo seleciona staging. Corrigir a classificação por operação e destino, sem confiar apenas no nome do comando.

## 10.8. Agent Networks

Não usar o endpoint legado `PUT /network/projects/{project_id}` como fluxo padrão de criação. Ele representa ensure de uma Network e não expressa a seleção entre múltiplas Networks.

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project network list/create` | GET/POST `/network/projects/{project_id}/networks`. | `network:read` / `network:write` | M |
| `project network get/update <network-id>` | GET/PATCH `/network/projects/{project_id}/networks/{network_id}`. | `network:read` / `network:write` | M |
| `project network delete <network-id>` | DELETE do recurso individual. | `network:delete` | F |
| `project network draft get` | Ler `draft_definition` e `draft_revision` no recurso. | `network:read` | M/L |
| `project network draft update --file <path>` | PATCH `/network/{network_id}/draft`. | `network:write` | M |
| `project network node add/update/remove` | Ler, editar e enviar draft com expected_revision. | `network:read` + `network:write` | L |
| `project network binding set/unset` | Mesmo contrato de draft, preservando nós/bindings. | Leitura/escrita e referências válidas | L |
| `project network release preview --environment staging\|production` | POST `/network/{network_id}/promotions/preview`. | `network:version` no catálogo da branch | M |
| `project network release create --environment staging` | POST `/network/{network_id}/promotions`. | `network:version` | M |
| `project network release activate <network-id> --version <version-id> --environment production` | POST `/network/{network_id}/production/activations`. | `network:production` | M |
| `project network release rollback` | POST `/network/{network_id}/rollback`. | `network:production` | M |
| `project network release list` | GET `/network/{network_id}/management/versions`. | `network:read` | M |
| `project network release get <network-id> --version <version-id>` | Seleção de versão da listagem autorizada; GET dedicado opcional. | `network:read` | L/N |
| `project network release activations` | GET `/network/{network_id}/management/activations`. | `network:read` | M |
| `project network contract get --environment ...` | GET `/network/{network_id}/management/external-context-contract`. | `network:read` | M |

**Concorrência já suportada:** preservar `expected_revision`, `expected_network_version_id`, `expected_current_production_version_id` e ações aprovadas previstas no contrato, quando exigidos pela operação.

O comando de ativação deve apontar para a versão imutável e mostrar a produção esperada. Não publicar o draft corrente por inferência.

Uma release de Network contém composição e bindings. O CLI exibe Agents vinculados, versões/snapshots e contratos; não reconstrói esses snapshots como fonte autoritativa.

## 10.9. Ambientes de execução

Ambientes de target são diferentes das environment keys do Project.

| Comando | HTTP | Situação |
| --- | --- | --- |
| `project agent environment list` | GET `/ai/agents/{agent_id}/runtime-environments` com Project. | M |
| `project agent environment enable/disable` | PATCH `/ai/agents/{agent_id}/runtime-environments/{environment}`. | M/N para política completa |
| `project agent environment context set` | PATCH com `external_context_values`. | M/N |
| `project network environment list` | GET `/network/{network_id}/runtime-environments`. | M |
| `project network environment enable/disable` | PATCH `/network/{network_id}/runtime-environments/{environment}`. | M/N |
| `project network environment context set` | PATCH com valores explicitamente selecionados. | M/N |

Os handlers inspecionados de runtime environments não aceitam ControlPlanePrincipal, e o mapper da branch não cobre de maneira coerente ambos os targets. Adaptar handler e autorização conjuntamente.

Separar alterar configuração de staging e ligar/desligar produção. Um editor de draft não recebe capacidade de alterar produção por possuir `agent:write`.

## 10.10. Tools HTTP e MCP

Base: `/tools`.

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project tool list/create` | GET/POST `/tools/tools`. | `tool:read` / `tool:write` | M |
| `project tool get <id>` | Seleção da listagem autorizada; GET individual proposto. | `tool:read` | L/N |
| `project tool update <id>` | PATCH `/tools/tools/{tool_id}`. | `tool:write` | M |
| `project tool enable/disable <id>` | PATCH `/tools/tools/{tool_id}/status`. | `tool:write` | M |
| `project tool delete <id>` | DELETE `/tools/tools/{tool_id}`. | `tool:delete` | M |
| `project tool usage <id>` | GET `/tools/tools/{tool_id}/usage-impact`. | `tool:read` | M |
| `project tool test` | POST `/tools/tools/test`. | `tool:execute`; handler requer compatibilidade de principal | M/N |
| `project tool execute` | POST `/tools/tools/execute`. | `tool:execute` | M |
| `project tool mcp discover` | POST `/tools/mcp/discover`. | `tool:write` no mapper atual | M |
| `project tool mcp refresh` | POST `/tools/mcp/refresh`. | `tool:write` | M |
| `project tool mcp permission set` | PATCH `/tools/mcp/permissions`. | `tool:write` | M |
| `project tool mcp permission set-all` | POST `/tools/mcp/permissions/bulk`. | `tool:write` | M |
| `project tool mcp auth start/complete` | POST `/tools/mcp/oauth/start` e `/complete`. | Gestão da Tool autenticada | M |
| `project tool mcp auth device-start/device-poll` | POST `/tools/mcp/oauth/device/start` e `/poll`. | Gestão da Tool autenticada | M |
| `project tool mcp auth status/disconnect` | POST `/tools/mcp/oauth/status` e `/disconnect`. | Classificação por efeito precisa ser explícita | M/N |
| `project tool secret list/create` | GET/POST `/tools/secrets`. | Segregação de metadados e escrita de segredo | M/N |

Pontos de implementação:

- HTTP e MCP são tipos de integração de capacidades agentic.
- `allow`, `deny` e `review` pertencem à política de uso das Tools pelo Agent.
- `review` não comprova um fluxo de aprovação humana de cada chamada em execução.
- Descoberta/refresh podem contatar o servidor remoto; não tratá-los como operação offline.
- Test/execute podem produzir efeitos externos e não fazem parte de `--dry-run`.
- Status de autenticação é consulta mesmo quando o contrato usa POST. Classificar pelo efeito, não apenas pelo verbo HTTP.
- Não criar integrações específicas com CRM, ERP ou redes sociais como obrigação do CLI. Usar os contratos de Tools HTTP/MCP da plataforma.

## 10.11. Knowledge, Documents e snapshots

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project knowledge collection list/create` | GET/POST `/knowledge/collections`. | `knowledge:read` / `knowledge:write` | M |
| `project knowledge collection get/update <id>` | GET/PATCH `/knowledge/collections/{collection_id}`. | Leitura/escrita | M |
| `project knowledge collection delete <id>` | DELETE do recurso. | `knowledge:delete` | F |
| `project knowledge collection overview <id>` | GET `/agent/knowledge/collections/{collection_id}/overview`. | `knowledge:read` | M |
| `project knowledge document list/get` | GET `/knowledge/documents` e `/{document_id}`. | `knowledge:read` | M |
| `project knowledge document create --file <metadata.json>` | POST `/knowledge/documents`; usar DTO real. | `knowledge:write` | M |
| `project knowledge document upload <path>` | Multipart `POST /knowledge/documents/upload`. | `knowledge:write` | M |
| `project knowledge document delete <id>` | DELETE `/knowledge/documents/{document_id}`. | `knowledge:delete` | M |
| `project knowledge search --query ...` | POST `/knowledge/search`. | Mapper atual: `knowledge:write`; corrigir para consulta apropriada | M/N |
| `project knowledge snapshot preview` | POST `/agent/knowledge/collections/{collection_id}/vector-preview`. | Preflight próprio; avaliar efeito real | M |
| `project knowledge snapshot create` | POST `/agent/knowledge/collections/{collection_id}/vector-snapshots`. | `knowledge:write` | M |
| `project knowledge snapshot list` | GET do mesmo subrecurso. | `knowledge:read` | M |
| `project knowledge snapshot get <snapshot-id>` | GET `/agent/knowledge/vector-snapshots/{snapshot_id}`. | `knowledge:read` | M |
| `project knowledge snapshot wait <snapshot-id>` | Poll de estado existente, com deadline. | Leitura | L |

Upload informa Project e Collection explicitamente. Informar aceitação/ID e acompanhar o estado sem presumir que indexação terminou. O comando de espera é observação; não reinicia upload ou construção.

Vector Snapshot é uma representação versionada do estado indexado. Não usar `knowledge-version` do Agent como sinônimo de Vector Snapshot.

Export de configuração não promete baixar o conteúdo original quando não existe endpoint autorizado para esse download.

## 10.12. Providers, credentials, models e estratégias

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project provider credential list/create` | GET/POST `/ai/credentials`. | `provider:read` / `provider:write` | M |
| `project provider credential update <id>` | PATCH `/ai/credentials/{credential_id}`. | `provider:write` | M |
| `project provider credential rotate <id>` | POST `/ai/credentials/{credential_id}/rotate`. | `provider:credential:rotate` | M |
| `project provider credential revoke <id>` | POST `/ai/credentials/{credential_id}/revoke`. | `provider:credential:revoke` | M |
| `project provider credential usage <id>` | GET `/ai/credentials/{credential_id}/usage`. | `provider:read` | M |
| `project provider credential delete <id>` | DELETE do recurso, após validação de lifecycle. | `provider:delete` | F |
| `project model list/create` | GET/POST `/ai/provider-models`. | `model:read` / `model:write` | M |
| `project model get/update <id>` | GET/PATCH `/ai/provider-models/{provider_model_id}`. | Leitura/escrita | M |
| `project model usage <id>` | GET `/ai/provider-models/{provider_model_id}/usage`. | `model:read` | M |
| `project model delete <id>` | DELETE do recurso, com lifecycle suportado. | `model:delete` | F |
| `project model discover` | Consumir capacidade de discovery já existente no Core através de rota pública validada. | Consulta ou persistência separadas | N para exposição/validação HTTP |
| `project model compatibility` | Comparar ModelSpec e Execution Strategy; servidor valida compatibilidade definitiva. | Consulta/preflight | L/N |
| `project catalog execution-strategy list` | GET `/ai/execution-strategies`. | `catalog:read` proposto | M/N |
| `project catalog context-manager list` | GET `/ai/context-managers`; alias `/ai/context-assemblers`. | `catalog:read` | M/N |
| `project catalog knowledge-strategy list` | GET `/ai/knowledge-strategies`. | `catalog:read` | M/N |
| `project catalog rag-strategy list` | GET `/ai/rag-strategies`. | `catalog:read` | M/N |

Discovery de modelos não deve persistir silenciosamente seu resultado. Separar `discover` de `import/register`.

O CLI preserva ModelSpec, modalidades, operações, capabilities, limites e configuração de fallback. Não mantém lista fechada de providers/modelos ou uma regra que transforme todo modelo em chat.

Catálogos de estratégias encontrados na master estão sem mapeamento correspondente para Control Key na branch; sua mera existência HTTP não completa o suporte do CLI administrativo.

## 10.13. Skills

Base: `/ai/projects/{project_id}/skills`.

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project skill list/create` | GET/POST da base. | `skill:read` / `skill:write` | M |
| `project skill version list/create <skill-id>` | GET/POST `/{skill_id}/versions`. | `skill:read` / `skill:version` | M |
| `project skill version get <version-id>` | GET `/versions/{skill_version_id}`. | `skill:read` | M |
| `project skill export` | Documento normalizado da versão selecionada. | Leitura | L |
| `project skill update` | Nova versão quando o conteúdo for versionado. | Versionamento | L sobre M |
| `project skill archive/delete` | Use case e contrato de lifecycle explícitos. | Permissão a definir | N; posterior |

Binding de Skill ao Agent é tratado na configuração do Agent. O comando deve informar se usa versão fixada ou outro modo realmente aceito pelo backend.

## 10.14. ChatSurfaces

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project surface list/create` | GET/POST `/chat-surfaces/projects/{project_id}`. | `chat_surface:read` / `chat_surface:write` | M |
| `project surface get/update <id>` | GET/PATCH `/chat-surfaces/{surface_id}`. | Leitura/escrita | M |
| `project surface release <id>` | POST `/chat-surfaces/{surface_id}/release`. | `chat_surface:release` | M |
| `project surface activate/disable/archive <id>` | POST no sufixo correspondente. | `chat_surface:write` | M |
| `project surface session list` | GET `/chat-surfaces/{surface_id}/sessions`. | `chat_surface:read` | M |
| `project surface activity` | GET `/chat-surfaces/{surface_id}/activity`. | `chat_surface:read` | M |
| `project surface test-session create` | POST `/chat-surfaces/{surface_id}/test-sessions`. | Política explícita de teste | M |
| `project surface access-key list/create` | GET/POST `/chat-surfaces/{surface_id}/access-keys`. | `chat_surface:keys` atual | M |
| `project surface access-key rotate/revoke <id>` | POST no lifecycle correspondente. | `chat_surface:keys` atual; separar ações futuramente | M |

A superfície pública possui contrato próprio de sessão/token e host-origin. Não reutilizar uma Control Key como token de usuário da ChatSurface.

## 10.15. Runtime, Sessions e Runs

### Execução pública

| Comando | HTTP | Credencial |
| --- | --- | --- |
| `runtime run --target agent\|network --input-file <path>` | `POST /v1/run`. | Runtime Key |
| `runtime run --stream ...` | `POST /v1/run/stream`. | Runtime Key com interface stream |
| `runtime run observe <run-id>` | `GET /v1/runs/{run_id}/stream`. | Runtime Key vinculada ao target |
| `runtime run active --session <id>` | `GET /v1/sessions/{session_id}/active-run`. | Runtime Key |
| `runtime run cancel <run-id>` | `POST /v1/runs/{run_id}/cancel`. | Runtime Key autorizada |
| `runtime contract validate --file <path>` | `POST /v1/contracts/validate`. | Runtime Key |

Rotas R, documentadas nos SDKs. O target e ambiente efetivos vêm da chave; flags servem para identificação/verificação e não alteram autorização.

`/v1/jobs` não será apresentado como funcional: o SDK Go registra que o contrato atual retorna `501`.

### Administração e histórico

| Comando | HTTP/efeito | Situação |
| --- | --- | --- |
| `project agent session create` | POST `/runtime/sessions`. | M; política para Control Key N |
| `project agent session list` | GET `/runtime/agents/{agent_id}/sessions`. | M/N |
| `project agent session messages <id>` | GET `/runtime/sessions/{session_id}/messages`. | M/N |
| `project agent run list` | GET `/runtime/runs` com Project/Agent e filtros. | M |
| `project agent run get <id>` | GET `/runtime/runs/{run_id}`. | M |
| `project agent run invocations <id>` | GET `/runtime/runs/{run_id}/model-invocations`. | M |
| `project agent run from-trace <trace-id>` | GET `/runtime/runs/by-trace/{trace_id}` e invocations. | M |
| `project agent run rerun <id>` | POST `/runtime/runs/{run_id}/rerun`; nova execução explícita. | M; autorização Control Key N |
| `project network session create/list` | POST/GET `/network/{network_id}/sessions`. | M/N |
| `project network session messages <id>` | GET `/network/{network_id}/sessions/{network_session_id}/messages`. | M/N |
| `project network session reset-context <id>` | POST no sufixo `/reset-context`. | M; política específica N |
| `project network run snapshot <id>` | GET `/network/executions/{execution_id}/snapshot`. | M; mapper completo N |
| `project network run events <id>` | GET `/network/executions/{execution_id}/events`. | M/N |
| `project network run diagnostics <id>` | GET `/network/executions/{execution_id}/diagnostics`. | M/N |
| `project network run rerun <id>` | POST `/network/executions/{execution_id}/rerun`. | M/N |

Endpoints administrativos de streaming/cancelamento já existem para Agent e Network, mas não são implicitamente abertos às Control Keys. O CLI inicial usa o runtime público para essas ações quando possível; suporte administrativo adicional exige as permissões explícitas propostas.

API legada `/runtime/ask` e aliases `/agent/...` não devem ser o caminho público padrão do novo CLI. Manter compatibilidade necessária sem duplicar a ontologia de execução.

### Streams e interrupção

1. Preservar o envelope Runtime Protocol v2 e `run_kind`.
2. Capturar `run_id`/`session_id` reais; não fabricar identidade a partir de campos incompatíveis.
3. Após obter Run ID, uma falha de conexão vira reattach da mesma Run.
4. Tratar `run.state` como snapshot de substituição no high watermark.
5. Ignorar deltas duplicados e recuperar gaps.
6. Não reenviar External Context no reattach.
7. Retry anterior à identidade só ocorre quando o contrato oferece recuperação/idempotência segura. Agent sem identidade recuperável falha sem segunda execução.
8. `Ctrl+C` interrompe observação por padrão; informar Run ID e comando de retomada.
9. Cancelamento da Run é uma operação explícita. `--cancel-on-interrupt` deve ser opt-in e usar o contrato de cancelamento.
10. Rerun sempre cria uma nova execução por decisão explícita; não é recuperação de transporte.
11. Session-scoped External Context permanece fixo segundo o contrato; reset de contexto não é permissão para sobrescrever esse snapshot.

## 10.16. Traces, uso e auditoria

| Comando | HTTP/efeito | Permissão | Situação |
| --- | --- | --- | --- |
| `project trace list` | GET `/observability/traces`. | `observability:read` para Control Key | M |
| `project trace get <id>` | GET `/observability/traces/{trace_id}`. | `observability:read` | M |
| `project trace export` | Exportação dos dados realmente autorizados. | Leitura | L |
| `project usage summary` | GET `/metering/projects/{project_id}/usage`. | `usage:read` | M |
| `project usage daily` | GET `/metering/projects/{project_id}/daily`. | `usage:read` | M |
| `project usage agent-daily <id>` | GET `/metering/agents/{agent_id}/daily`. | `usage:read` | M |
| `workspace audit list/get/export` | Eventos administrativos de grants, keys, categorias e mudanças. | `audit:read` proposto | N |

Preservar valores numéricos, moeda e unidades retornadas pela API. Não estimar custo financeiro como se fosse medição persistida.

`POST /metering/usage-events` é rejeitado na master porque metering é registrado por serviços internos. Não oferecer um comando para fabricar consumo. Operações internas de escrita de traces não recebem capacidade por “modo máximo”.

## 11. Comando HTTP genérico

Preservar a forma iniciada:

~~~bash
woobe request GET /core/projects --query workspace_id=<workspace-id>
woobe request POST /ai/agents --data @agent.json
woobe request PATCH /network/<network-id>/draft --data @network.json
woobe request POST /knowledge/documents/upload \
  --form project_id=<project-id> \
  --form collection_id=<collection-id> \
  --file file=./manual.pdf
~~~

Implementação:

- Path relativo à origem configurada; URL absoluta externa não recebe credenciais.
- Escolha explícita do tipo de credencial; não tentar session/control/runtime em sequência.
- JSON, query, form, multipart e, posteriormente, resposta streaming suportada.
- Preservar valores repetidos de query e campos permitidos pelo schema.
- Multipart deve suportar leitura incremental de arquivos e limites configurados.
- Não refletir uma resposta de emissão de key com segredo sem a opção explícita correspondente.
- Erros seguem o mesmo contrato dos demais comandos.
- A opção local readonly usa o registro de efeito; rota desconhecida não é considerada consulta automaticamente.
- Operação desconhecida pode ser enviada explicitamente fora do modo readonly, mas o backend deve negá-la para Control Keys se não houver registro de autorização.
- `--dry-run` do request faz validação/plano local; nunca envia a mutação sob pretexto de simulação.

A cobertura genérica serve para endpoints novos antes de existir comando dedicado. Ela não substitui ergonomia, schemas, validação ou autorização.

## 12. Manipulação declarativa: validate, diff, plan e apply

### 12.1. Documentos suportados

Primeira onda:

| Kind | Conteúdo |
| --- | --- |
| `Project` | Metadados e configuração editável do Project. |
| `Agent` | Definição mutable, ModelSpec/bindings/contratos suportados. |
| `AgentNetwork` | Draft e referências de Agents. |
| `Tool` | Definição HTTP/MCP, autenticação por referência e política. |
| `KnowledgeCollection` | Metadados e parâmetros suportados. |
| `SkillVersion` | Conteúdo e configuração de uma versão. |
| `ControlKey` | Permissões/grants; segredo não faz parte do documento. |
| `AuthorityCategory` | Perfil e revisão de autoridade. |
| `ChatSurface` | Configuração editável e referências de release/target. |

Provider credentials e environment keys usam referências a um provider de segredos. Releases, Runs, traces e snapshots são exportáveis conforme autorização, mas não viram objetos regraváveis por `apply`.

### 12.2. Comandos

~~~bash
woobe manifest validate --file resources.json
woobe manifest diff --file resources.json
woobe manifest plan --file resources.json --output json
woobe manifest apply --file resources.json
woobe manifest export --resource agent --id <agent-id> --file agent.json
~~~

Semântica:

1. **Validate:** validar documento local e, quando solicitado, capabilities/contratos sem persistência.
2. **Diff:** consultar o estado autorizado e identificar diferenças.
3. **Plan:** listar operações, permissões, escopos, dependências e condições.
4. **Apply:** executar o plano após revalidar autoridade e revisões.
5. **Export:** materializar campos autorizados, sem segredos e sem afirmar completude quando houve omissões.

### 12.3. Ordem de dependências

Um pacote com vários recursos deve declarar referências e IDs resolvidos. Exemplo de dependências:

~~~mermaid
flowchart TD
    PROJECT["Project"] --> PROVIDER["Credential por referência"]
    PROJECT --> KNOWLEDGE["Collection e Snapshot"]
    PROJECT --> TOOL["Tool"]
    PROJECT --> SKILL["Skill Version"]
    PROVIDER --> AGENT["Agent Draft"]
    KNOWLEDGE --> AGENT
    TOOL --> AGENT
    SKILL --> AGENT
    AGENT --> NETWORK["Network Draft"]
    NETWORK --> RELEASE["Release e ativação explícitas"]
~~~

O fluxo de configuração não publica automaticamente. Release e ativação são operações explícitas, com permissões e versões próprias.

### 12.4. Atomicidade e retomada

- Aplicação de múltiplos recursos não é transação distribuída.
- Cada operação usa sua atomicidade do servidor.
- Por padrão, interromper na primeira falha e retornar checkpoint.
- Checkpoint contém operation_id, recurso, revisão, status e request_id; não contém segredos.
- Reexecutar operações somente após reconciliar o resultado anterior.
- `--continue-on-error` só continua operações independentes; dependentes de uma falha ficam skipped.
- Importação não faz prune. Exclusões exigem seleção explícita em uma operação separada.
- Atualização de autoridade mostra diff por Workspace, Project e permissão.
- Conflito de revisão exige novo plan; não sobrescrever silenciosamente.
- Um plano salvo não concede autorização futura e não substitui as verificações na aplicação.
- Conteúdo exportado parcialmente não pode apagar campos omitidos por falta de permissão.

### 12.5. Formato de resultado do plan

~~~json
{
  "schema_version": "1",
  "context": {
    "workspace_id": "<workspace-id>",
    "project_id": "<project-id>"
  },
  "operations": [
    {
      "operation_id": "network.draft.update",
      "resource_id": "<network-id>",
      "effect": "configuration_write",
      "required_permissions": ["network:write"],
      "expected_revision": 12,
      "authorization": "allowed",
      "status": "planned"
    }
  ],
  "complete": true
}
~~~

IDs de operação pertencem ao contrato proposto do catálogo, não aos snapshots atuais. Se preflight remoto não existir, retornar `authorization: "not_evaluated"`; não inventar autorização com base em configuração local.

## 13. Contratos HTTP e registro de operações

### 13.1. Substituir classificação genérica por metadados explícitos

O mapper da branch usa prefixos e verbos. Ele é uma base, mas a cobertura máxima requer registrar cada operação pública administrativa, aliases e condições de payload.

Metadados mínimos:

| Campo | Função |
| --- | --- |
| `operation_id` | Identidade estável de domínio. |
| `method` / `route_template` | Associação ao endpoint. |
| `principal_kinds` | Principals aceitos. |
| `scope_kind` | Workspace, Project, target ou self. |
| `required_permissions` | Permissões primitivas. |
| `resource_resolver` | Como resolver ownership/tenancy. |
| `effect` | Consulta, escrita, execução externa, emissão de segredo, ativação etc. |
| `conditions` | Ambiente, target, lifecycle e teto de delegação. |
| `supports_revision` | Contrato de concorrência. |
| `supports_idempotency` | Garantia efetiva do endpoint. |
| `response_projection` | Campos públicos, metadados e segredos. |

O registro fica no servidor/composição HTTP. As regras de domínio continuam no Core. O CLI consome uma projeção desse catálogo para help, plan e capacidades; a decisão final continua no servidor.

### 13.2. Lacunas verificadas na classificação atual

| Operação inspecionada | Resultado do mapper da branch | Ajuste necessário |
| --- | --- | --- |
| `POST /knowledge/search` | `knowledge:write` | Classificar pesquisa como consulta, sem exigir escrita por usar POST. |
| `POST /tools/mcp/oauth/status` | `tool:write` | Separar consulta de autenticação das alterações de credencial. |
| `GET /ai/execution-strategies` | Sem permissão mapeada | Registrar capacidade de catálogo. |
| `GET /identity/workspaces` | Sem permissão mapeada | Descoberta própria/Workspace para Control Key. |
| `PATCH /network/{id}/runtime-environments/production` | Sem permissão mapeada | Registrar ambiente e autoridade de produção; adaptar handler. |
| `PATCH /ai/agents/{id}/runtime-environments/production` | `agent:write` | Exigir política de ambiente/produção apropriada; adaptar handler. |
| Agent promote com `target_status=staging` | `agent:production` | Condição explícita de staging/production. |
| `GET /network/executions/{id}/diagnostics` | Sem permissão mapeada | Registrar consulta de evidência e resolver execução ao Project. |

Esses resultados foram obtidos sobre a função do mapper, em avaliação local sem iniciar a stack. Não comprovam status HTTP real nem substituem testes de integração.

Outros itens a fechar:

- Handler que aceita somente AuthenticatedPrincipal/ProjectApiPrincipal deve ser adaptado conscientemente para ControlPlanePrincipal.
- `tool test` possui verificação de usuário em parte do caminho; mapear `tool:execute` sozinho não basta.
- Secrets em `/tools/secrets` não devem herdar autorização genérica de Tool sem política de projeção.
- Aliases `/agent/...` precisam das mesmas regras ou devem ser explicitamente desabilitados para Control Keys.
- Recursos relacionados no corpo não podem cruzar Projects.
- O mapper conhece alguns verbos DELETE de recursos ausentes na master; permissão registrada não cria endpoint.
- Resolvers de ownership devem reconhecer IDs indiretos, inclusive run/trace/network/version, com semântica correta.
- Nenhuma operação sem classificação é automaticamente concedida à Control Key.

### 13.3. Campos e schemas

- DTOs públicos são a fonte para documentação de inputs.
- Separar omission, null e valor vazio nas atualizações.
- Preservar enums conhecidos e campos extensíveis contratados.
- Validar UUIDs, datas UTC/timezone, expiração, interfaces e tipos de target.
- Não reutilizar schema de criação como se fosse PATCH total.
- Atualizações não devem remover metadata ou extensões desconhecidas.
- Usar modelos locais apenas para formato; o servidor valida domínio e autoridade.
- A API deve devolver erro estruturado, request_id e código estável quando possível.

### 13.4. Compatibilidade entre versões

Criar uma capability versionada do servidor com:

- Versão do contrato administrativo.
- Revisão do catálogo de permissões.
- Recursos e operações disponíveis.
- Tipos de principal suportados por operação.
- Versões do protocolo de runtime.
- Features de paginação, revisão e idempotência.

Cliente conectado a servidor sem uma capacidade necessária retorna “operação não suportada por este servidor”. Não sugerir sucesso e não cair silenciosamente em SQL ou rota legada com autorização diferente.

Servidor antigo sem Control Keys pode ser usado por sessão humana nos comandos suportados. Emissão/administração de Control Keys exige o contrato integrado.

### 13.5. Criação, emissão e idempotência administrativa

Criação de Project/Agent/Network, emissão de chave e rotação ainda precisam de garantias explícitas para aplicação declarativa confiável. Não inferir idempotência desses endpoints a partir da implementação de Network Run.

Contrato alvo para operações administrativas suportadas:

1. Idempotency-Key vinculada ao principal/linhagem, Workspace, operação e hash do payload.
2. Registro de aceitação e mutação na mesma transação quando necessário para não duplicar o recurso.
3. Mesma chave com payload diferente retorna conflito.
4. Repetição da mesma operação retorna a identidade/status já aceitos, conforme política de resposta.
5. Criação de Project e grant do criador devem concluir consistentemente; não retornar sucesso definitivo com a concessão obrigatória perdida.
6. Emissão/rotação registra IDs e lineage de maneira recuperável. A política de entrega/reentrega do segredo precisa ser explícita e limitada; nunca expor o valor em GET/list ou log de idempotência.
7. Sem suporte de servidor, uma escrita com resultado incerto termina como `unknown` e requer reconciliação. A CLI não promete exactly-once usando cache local.

Adicionar esse contrato na Fase 1 para as operações exigidas por apply e lifecycle. Testar perda de resposta depois de commit, repetição, payload conflitante e expiração do registro de idempotência.

### 13.6. Autoridade dos descendentes

A branch registra o emissor e verifica o subconjunto na concessão. Isso não é equivalente a uma política permanente de herança/revogação entre credenciais.

Decisão inicial: cada credencial emitida possui grants materializados próprios. Revogar o emissor não é apresentado pelo CLI como revogação implícita de todas as credenciais que ele criou. Expiração e teto de delegação aplicados continuam obrigatórios.

Oferecer inspeção dos descendentes e revogação explícita em cascata quando esse contrato for implementado. A operação deve validar a autoridade sobre cada alvo, produzir relatório de impacto e resultado por credencial e preservar as restrições de linhagem. Se o modelo existente já adotar teto contínuo do emissor, preservar essa regra e expô-la no catálogo; não alterar o comportamento silenciosamente.

## 14. Dados persistidos e ownership dos novos componentes

### 14.1. Reutilizar o existente

| Dado | Owner atual/proposto |
| --- | --- |
| Workspace, usuários, membership, invites | `modules/identity`. |
| Projects, Project membership | `modules/core`. |
| Control Keys e grants | Estruturas propostas na branch dentro de `modules/core`. |
| Runtime/Project API Keys | `modules/core`. |
| Tools, Knowledge, modelos/providers e Skills | Boundary Agent atual. |
| Releases/composição de Network | `modules/network`. |
| Catálogo puro de IDs de permissão | Contratos compartilhados, sem dependência HTTP ou de banco. |

### 14.2. Categorias novas, somente se ausentes

Para categorias aplicáveis a humanos e credenciais, concentrar a política e o catálogo no boundary de identidade/autorização. O Core recebe uma interface de resolução de categoria durante a composição; não importa repositories internos de Identity.

Modelo de persistência sugerido:

| Estrutura | Campos essenciais |
| --- | --- |
| `authority_categories` | id, workspace_id, scope_kind, slug, nome, status, system, revisão corrente. |
| `authority_category_versions` | category_id, revision, permissions, constraints, autoria, created_at; imutável. |
| Referência no grant | category_id/category_revision de origem, permissões concretas e conditions aplicadas. |
| Atribuição humana | Sujeito, Workspace/Project, categoria/revisão e estado; respeita papéis estruturais. |
| Auditoria | Actor user/control credential, operação, escopo, alvo, diferenças e outcome. |

Categoria para humano não remove o papel estrutural. `viewer` mantém teto de leitura, e categorias não criam ownership. `member` pode receber operações concretas conforme a política definida; não herda administração de Workspace.

Requisitos de persistência:

- Integridade de Workspace/Project e unicidade por escopo.
- Versões imutáveis.
- Concessão e metadados da categoria aplicados de maneira consistente.
- Índices para lookup de chave, grants, membership e revisão.
- Alteração condicional de grants e categorias.
- Audit/outbox transacional quando fizer parte do resultado garantido.
- Nenhum segredo em categorias, grants ou eventos.
- Migração a partir do head atual, com revisão única.
- Dados existentes mantêm comportamento definido durante a migração; não reinterpretar silenciosamente `admin` legado de Project API Key como autoridade de control plane.

Se o cadastro citado pelo usuário já estiver no Core, preservar seu ownership e expor boundary público adequado. A proposta acima não justifica migrar domínio existente sem necessidade.

## 15. Saída, erros e automação

### 15.1. Convenções de saída

| Modo | Contrato |
| --- | --- |
| Table | Resumo legível, IDs e estado; diagnostics em stderr. |
| JSON | Um envelope estável por comando, incluindo contexto, resultado e erro quando houver. |
| JSONL de runtime | Somente envelopes/eventos de runtime válidos em stdout; erros de cliente em stderr. |
| JSONL administrativo | Registros tipados e versão de schema; terminal/partial explicitamente identificados. |

Envelope administrativo proposto:

~~~json
{
  "schema_version": "1",
  "success": true,
  "context": {
    "workspace_id": "<workspace-id>",
    "project_id": "<project-id>"
  },
  "data": {},
  "meta": {
    "request_id": "<request-id>",
    "complete": true
  }
}
~~~

Não alterar os eventos Runtime v2 para encaixá-los no envelope administrativo. Preservar seus campos e a identidade semântica.

### 15.2. Códigos de saída

| Código | Significado |
| --- | --- |
| 0 | Operação concluída com sucesso. |
| 1 | Erro interno inesperado do cliente. |
| 2 | Uso inválido, input local ou validação de formato. |
| 3 | Credencial ausente, inválida ou sessão expirada. |
| 4 | Autoridade insuficiente, quando o servidor identifica essa condição. |
| 5 | Recurso não encontrado/inacessível segundo a resposta do servidor. |
| 6 | Conflito de revisão, estado ou operação concorrente. |
| 7 | Falha de conexão ou resultado de escrita desconhecido. |
| 8 | Deadline excedido. |
| 9 | Capacidade/versão de servidor não suportada. |
| 10 | Resultado parcial de operação composta. |
| 11 | Run terminou com falha ou cancelamento remoto. |
| 130 | Interrupção local pelo usuário. |

A resposta genérica `404` da tenancy não será convertida em explicação de existência de um recurso oculto.

### 15.3. Retry

- Consultas podem repetir com backoff limitado e respeito a Retry-After.
- POST de criação não é repetido automaticamente sem garantia real de idempotência.
- Uma opção `--idempotency-key` não cria suporte no servidor.
- Resultado incerto de emissão/rotação de key exige reconciliação; nunca emitir outra automaticamente.
- Não repetir automaticamente tool execute, publicação, reset de contexto ou rerun.
- Falha de autenticação pode renovar sessão no fluxo previsto; não escalonar autoridade.
- CLI não muda de contexto, target, ambiente ou credencial para “tentar funcionar”.

### 15.4. Uso não interativo

- Todos os comandos necessários aceitam input determinístico por arquivo/stdin.
- Sem TTY, campos obrigatórios ausentes produzem erro; não bloquear esperando resposta.
- `--yes` aceita uma ação já especificada, sem ampliar sua autoridade.
- Produção exige destino explícito e os controles de revisão do servidor.
- Chaves de CI têm escopo, expiração e categoria fixados.
- Tokens/segredos não entram em git, output normal ou checkpoints.
- Artefatos de pipeline informam IDs, versões ativadas e request_ids.

### 15.5. Contrato agent-friendly obrigatório

O CLI é uma interface externa de controle: um agente de desenvolvimento ou operação pode usá-lo para criar, editar, estruturar, testar e publicar Agents/Networks da Woobe, dentro da autoridade concedida. Agent que usa o CLI como ferramenta e Agent cadastrado na Woobe são papéis distintos; o cliente não substitui o runtime da plataforma.

| Necessidade do consumidor agentic | Contrato do CLI |
| --- | --- |
| Descobrir ações disponíveis | `woobe help --output json` lista a árvore de comandos; descrição detalhada aceita o caminho canônico. |
| Conhecer input e output sem inferir texto de help | `woobe schema --command "project agent create" --kind input --output json`, com identificação e versão do schema. |
| Saber o efeito e a autoridade necessária | Metadados por operation ID: consulta/mutação/execução/publicação, escopos, permissões, capability e IDs obrigatórios. |
| Identificar o que a instalação realmente permite | `woobe doctor --output json` e introspecção própria; catálogo local de sintaxe não afirma disponibilidade ou autorização remota. |
| Editar sem destruir configuração existente | Get/export, diff e atualização com semântica explícita de PATCH; revisões esperadas quando o servidor as suporta. |
| Construir uma estrutura completa | Manifesto com Agents, referências suportadas, Network, nós/bindings e dependências; validate → plan → apply → consulta do resultado. |
| Tomar decisão após uma falha | Erro estruturado, exit code, request ID, contexto e estado de escrita conhecido/desconhecido/parcial. |
| Executar sem intervenção humana | Inputs determinísticos por arquivo/stdin; ausência de TTY nunca inicia perguntas; nenhuma escolha implícita de Project, produção ou nova credencial. |

Help, schemas e comandos devem derivar do mesmo registro de operações. Não manter descrições para agentes manualmente desconectadas dos handlers Go. Descoberta local deve funcionar sem credencial; consulta de recursos e de autoridade efetiva segue as permissões do servidor.

**Cenário de aceite ponta a ponta:** um consumidor automatizado descobre o schema, cria um Agent em um Project autorizado, configura prompt/contrato/modelo e bindings disponíveis, monta uma Network, valida o draft, cria/testa releases, publica com autorização explícita e verifica IDs/versões/estado remoto. A etapa de produção também deve ser testada com credencial sem `*:production`, comprovando a negação. Uma credencial de publicação distinta somente é usada por seleção explícita, nunca como fallback automático do CLI.

Cada etapa deve funcionar pelo executável Go com JSON e sem TTY. Se uma capacidade não existir na versão do servidor, a automação recebe erro de compatibilidade estruturado, não um resultado fictício. Nenhum desses requisitos exige um modelo de IA embutido no CLI.

## 16. Exemplos de uso orientados à autoridade

Todos os comandos avançados desta seção são a sintaxe alvo. Flags como `--category` dependem do contrato de categorias proposto.

### 16.1. Leitura mínima em um Project

~~~bash
woobe auth credential import --name agent-reader --stdin
woobe context create read-study --api-url https://woobe.example
woobe context credential attach read-study --credential agent-reader
woobe context use read-study
woobe context set --workspace <workspace-id> --project <project-id>
woobe project agent list --output json
~~~

Grant necessário: `agent:read` no Project. Se IDs já são conhecidos, não obrigar o usuário a conceder `keys:read` ou administração do Workspace para executar essa leitura.

### 16.2. Criar uma categoria personalizada

~~~bash
woobe workspace authority category create \
  --workspace <workspace-id> \
  --file study-content-editor.json
~~~

Esse comando cadastra um perfil. Ele não vincula automaticamente usuários, credenciais ou Projects.

### 16.3. Emitir Control Key a partir da categoria

~~~bash
woobe workspace control-key create \
  --workspace <workspace-id> \
  --name study-content-editor-ci \
  --project <project-id> \
  --category study-content-editor \
  --category-revision 1 \
  --expires-at 2026-11-04T00:00:00Z \
  --secret-file ./study-editor.key
~~~

O servidor resolve a categoria e compara a concessão com a autoridade do emissor. Na implementação atual da branch, a forma equivalente é enviar JSON com `permissions` e `project_grants`; `--category` é extensão.

### 16.4. Permissões diferentes em Projects diferentes

~~~json
{
  "name": "study-maintenance",
  "permissions": ["workspace:read"],
  "project_grants": [
    {
      "project_id": "<sandbox-project-id>",
      "permissions": [
        "project:read",
        "agent:read",
        "agent:write",
        "agent:version",
        "network:read",
        "network:write",
        "network:version"
      ]
    },
    {
      "project_id": "<production-project-id>",
      "permissions": [
        "project:read",
        "agent:read",
        "network:read",
        "run:read",
        "usage:read"
      ]
    }
  ]
}
~~~

O mesmo CLI modifica sandbox e apenas consulta production. A diferença está nos grants; não depende de ocultar subcomandos.

### 16.5. Atualizar draft e publicar com credenciais distintas

~~~bash
woobe project network draft update <network-id> \
  --context editor \
  --file network.json \
  --expected-revision 12

woobe project network release preview <network-id> \
  --context builder \
  --environment staging

woobe project network release create <network-id> \
  --context builder \
  --environment staging \
  --expected-revision 13

woobe project network release activate <network-id> \
  --context publisher \
  --version <staging-version-id> \
  --environment production \
  --expected-production-version <current-version-id> \
  --change-description "Ativar versão validada"
~~~

O editor não precisa receber `network:production`. A chave do publisher não precisa receber `network:write` por conveniência.

### 16.6. Executar um target publicado e retomar observação

~~~bash
woobe runtime run \
  --context application-runtime \
  --target network \
  --runtime-credential study-production \
  --input-file input.txt \
  --external-context-file external-context.json \
  --stream \
  --output jsonl

woobe runtime run observe <run-id> \
  --context application-runtime \
  --runtime-credential study-production \
  --output jsonl
~~~

A segunda chamada observa a mesma Run; não cria execução nova.

## 17. Validação e critérios de aceite

### 17.1. Matriz mínima de autorização

| Caso | Resultado esperado |
| --- | --- |
| Control Key do Workspace A acessa recurso do B | Negado com resposta de tenancy definida pelo servidor. |
| Key tem grant no Project A e acessa B do mesmo Workspace | Negado. |
| ID em path é A e body/query indica B | Conflito ou negação, sem execução. |
| Apenas `agent:read` chama POST/PATCH/DELETE de Agent | Negado. |
| Apenas `agent:write` publica produção | Negado. |
| Apenas `network:version` ativa produção | Negado. |
| Chave de publisher edita draft sem write | Negado. |
| Categoria personalizada contém permissão desconhecida | Rejeitada. |
| Categoria de outro Workspace é aplicada ao grant | Negado. |
| Categoria ganha nova permissão | Credenciais existentes mantêm o conjunto aplicado. |
| Delegação tenta ampliar Workspace/Project/permissões/conditions | Negada. |
| Chave altera/revoga/rotaciona sua linhagem | Negado conforme regra atual. |
| Rotação tenta remover teto de expiração delegável | Negado. |
| Owner tenta revogar seu acesso implícito via Project membership | Rejeitado pela regra estrutural. |
| Admin convida/promove owner por fluxo genérico | Negado. |
| Viewer chama qualquer mutação coberta | Negado, inclusive via request e aliases. |
| Runtime Key tenta CRUD administrativo | Negado. |
| Control Key tenta execução pública runtime | Negado. |
| Runtime Key de outro target/ambiente observa ou cancela Run | Negado. |
| Credencial/grant foi revogado | Chamadas posteriores negadas dentro da garantia definida. |
| `request` chama mesma ação negada no comando dedicado | Também negado pelo backend. |
| Endpoint novo não registrado para Control Key | Negado por padrão. |
| Consulta é POST sem efeito de escrita | Exige a permissão de consulta apropriada. |
| List/get/export/debug de credenciais | Não retorna segredo. |

### 17.2. Testes por camada

| Camada | Verificação |
| --- | --- |
| Core | Subconjunto, condições de delegação, versões de categorias, ownership, transições e imutabilidade. |
| Integração PostgreSQL | Grants reais, membership, rotação, revogação, alteração concorrente e migrações. |
| API | Matriz HTTP de principals, métodos, aliases, ID indireto e consistência path/body/query. |
| Contratos | DTOs, documentação de capabilities e cobertura do registro de operações. |
| CLI | Contexto, parser, stdin, stdout/stderr, erros, noninteractive, segredo e composição. |
| Runtime | Reattach, Run identity, gaps, snapshots, terminais e interrupção sem duplicar execução. |
| E2E | Caminhos completos sobre uma instalação real de teste. |

Reutilizar suites atuais de Control Keys, Project membership, tenancy, refresh rotation, Runtime Keys, Agent/Network releases e MCP permissions. Ampliar cenários reais; não substituir a validação por mocks que apenas repetem a lógica do parser.

### 17.3. Gates quantitativos

1. **100% das operações públicas administrativas previstas para a versão** classificadas no registro do servidor.
2. **100% dos comandos publicados** associados a capability, endpoint e tipo de principal.
3. Nenhum alias administrativo com autorização mais permissiva.
4. Todos os casos da matriz de autorização executados no CI correspondente.
5. Um cenário E2E completo de cada perfil: reader, editor, builder, publisher, administrator e custom.
6. Nenhuma exposição de segredo nos fixtures de list/get/export/debug.
7. Upgrade de migrações a partir da master e installation fresh passam.
8. Instalação limpa do pacote e help funcionam nos sistemas suportados.
9. Agent e Network recuperam observação sem criar nova Run depois de identidade conhecida.
10. Cada recurso planejado informa o que é M/F/N, e a versão não anuncia capability que o servidor não suporta.

“CLI completo” significa cobertura das operações públicas suportadas e autorizáveis da versão declarada. Não significa acessar todas as funções privadas do Core.

### 17.4. Cenários E2E obrigatórios

**Cenário A — administração:**

- Login de owner.
- Seleção/criação de Workspace e Project.
- Categoria customizada.
- Emissão de Control Key limitada.
- Alteração autorizada de Agent/Network.
- Tentativa de acesso a outro Project negada.
- Rotação por outra credencial autorizada.
- Revogação e verificação de bloqueio.

**Cenário B — publicação:**

- Editor altera draft.
- Builder cria/testa staging.
- Publisher ativa snapshot/version selecionado.
- Editor não consegue ativar produção.
- Alterar draft depois não muda a release ativa.
- Rollback restaura a versão indicada e produz evidência.

**Cenário C — runtime:**

- Runtime Key criada para Agent e outra para Network.
- Run criada, IDs reais capturados.
- Interrupção e reattach.
- Contexto session/run preservado.
- Cancelamento explícito.
- Run de outro target não é acessível.

**Cenário D — conhecimento e Tools:**

- Upload e acompanhamento de documento/snapshot.
- Tool HTTP/MCP cadastrada e binding válido.
- Política MCP alterada.
- Permissão administrativa da Tool separada da permissão de execução.
- Listagem/exportação não retorna credenciais secretas.

## 18. Roadmap de implantação

A sequência abaixo considera uma implementação completa. Não iniciar pela criação de dezenas de comandos sobre uma autorização incompleta: primeiro estabilizar o contrato servidor/credencial.

### Fase 0 — reconciliar o trabalho existente

**Entregas:**

- [ ] Atualizar a referência da master no início da implementação.
- [ ] Localizar o cadastro de categorias citado pelo usuário, inclusive em outra branch.
- [ ] Documentar quais contratos serão reaproveitados.
- [ ] Abrir branch de integração a partir da master.
- [ ] Portar ControlPlanePrincipal, emissão de control key, grants, guard e testes pertinentes.
- [ ] Resolver a colisão Alembic com revisão livre e down_revision atual.
- [ ] Preservar ModelSpec e demais mudanças da master.
- [ ] Inicializar o module Go no repositório canônico `woobe-cli`, fixar toolchain/dependências e documentar a migração do protótipo Python.
- [ ] Atualizar ADR e documentação para o estado integrado.

**Dependência:** nenhuma.  
**Aceite:** instalação nova e upgrade da master criam Control Keys sem revision ID duplicado; rotas públicas existentes mantêm seus contratos.  
**Esforço estimado:** 2–4 dias de engenharia.

### Fase 1 — autoridade e operações do backend

**Entregas:**

- [ ] Registrar cada operação administrativa por operation_id, principal, escopo e efeito.
- [ ] Cobrir aliases/rotas legadas ou negar seu uso com Control Key.
- [ ] Corrigir pesquisa POST, auth status MCP, catálogos e runtime environments.
- [ ] Separar staging, produção e execução de ferramentas.
- [ ] Resolver todos os tipos de ID ao Project proprietário.
- [ ] Aplicar política de ações a principals humanos; fechar viewer e teto de delegação de admin.
- [ ] Preservar comparação de subconjunto por Project e Workspace.
- [ ] Especificar delegação de Runtime Keys e política de grants de Project recém-criado.
- [ ] Definir revisão/controle de concorrência para grants e alterações sem mecanismo existente.
- [ ] Implementar idempotência administrativa nas operações exigidas e consistência entre criação de Project e grant do criador.
- [ ] Documentar autoridade/expiração dos descendentes e semântica de revogação.
- [ ] Garantir projeção de segredos no servidor.

**Dependência:** Fase 0.  
**Aceite:** matriz de autorização passa pela API real, inclusive request genérico e aliases.  
**Esforço estimado:** 3–5 dias.

### Fase 2 — discovery e fundação do CLI

**Entregas:**

- [ ] Disponibilizar catálogo de permissions/operations/capabilities versionado.
- [ ] Disponibilizar introspecção própria e preflight sem mutação.
- [ ] Implementar a entrada `cmd/woobe` e a árvore Cobra, com divisão em `internal/cli`, application, controlplane, identity, runtime, contracts, config e output.
- [ ] Implementar transporte Go, cancelamento, erros tipados, adapters de credenciais e injeção de stdin/stdout/stderr.
- [ ] Implementar contextos locais e resolução determinística.
- [ ] Implementar login/refresh/logout de sessão com cookies e CSRF.
- [ ] Implementar importação e referências protegidas de Control/Runtime Keys.
- [ ] Implementar JSON, tabela, stderr e códigos de saída.
- [ ] Portar para Go os comportamentos compatíveis de request/control-key, sem dependência de execução do protótipo Python.
- [ ] Implementar doctor/version/help e validação de capacidades.
- [ ] Implementar help JSON e exportação de schemas a partir do registro único, com compatibilidade e efeito das operações.

**Dependência:** Fases 0–1.  
**Aceite:** invocação limpa e não interativa encontra o servidor, seleciona escopo e informa principal/autoridade sem expor segredo.  
**Esforço estimado:** 3–5 dias.

### Fase 3 — Workspace, Project e credenciais

**Entregas:**

- [ ] Workspace list/get/create/update.
- [ ] Membros e convites suportados, com limites de papel.
- [ ] Project list/get/create/update/overview.
- [ ] Acesso humano e acesso pendente por convite.
- [ ] Control Key CRUD/lifecycle e grants por Project.
- [ ] Project API Keys e Runtime Keys.
- [ ] Environment keys com valores protegidos.
- [ ] Alterações incrementais de grants com proteção de revisão.
- [ ] Testes de reader mínimo e credencial com permissões diferentes por Project.

**Dependência:** Fases 1–2.  
**Aceite:** a CLI administra escopos e credenciais ponta a ponta; não há acesso cruzado nem ampliação de autoridade.  
**Esforço estimado:** 3–5 dias.

### Fase 4 — categorias personalizáveis e atribuições

**Entregas:**

- [ ] Reutilizar ou implementar entidade/versionamento de categoria.
- [ ] Validar permissões primitivas e compatibilidade de scope.
- [ ] List/get/create/update/clone/history/archive/delete.
- [ ] Aplicar categoria/revisão a grants, preservando lista concreta.
- [ ] Atribuições humanas, se fizerem parte do modelo existente/escopo integrado.
- [ ] Perfis iniciais versionados de reader/editor/builder/publisher/admin.
- [ ] Plan/diff de atualização de categoria aplicada.
- [ ] Subconjunto e condições de delegação após expansão.
- [ ] Garantir que nova revisão não amplia automaticamente credenciais.
- [ ] Eventos de auditoria de criação, revisão e aplicação.

**Dependência:** Fases 1–3.  
**Aceite:** criar categoria nova e usá-la em Project/credencial sem alterar código do CLI, com testes negativos de delegação.  
**Esforço estimado:** 4–7 dias, reduzível se o cadastro citado já estiver completo.

### Fase 5 — Agents, Networks e releases

**Entregas:**

- [ ] Agents e configurações principais.
- [ ] Prompts, contratos e model configs.
- [ ] Bindings de Tools, Skills e Knowledge.
- [ ] Releases/tests/promotion/activation/rollback.
- [ ] Networks múltiplas por Project.
- [ ] Draft, nodes/bindings e revisão esperada.
- [ ] Versions, previews, staging e production activations.
- [ ] Ambientes de Agent/Network com política adequada.
- [ ] Lifecycle de exclusão/arquivamento conforme suporte real.
- [ ] Diff/export de configurações autorizado.

**Dependência:** Fases 1–4.  
**Aceite:** editor, builder e publisher operam com autoridades diferentes; produção usa snapshot imutável.  
**Esforço estimado:** 4–6 dias.

### Fase 6 — Tools, Knowledge, providers, models, Skills e surfaces

**Entregas:**

- [ ] Tools HTTP/MCP, lifecycle, uso, testes e execução explícita.
- [ ] Discovery/refresh e autenticação MCP suportada.
- [ ] Permissões MCP allow/deny/review.
- [ ] Segredos e credentials com projeção correta.
- [ ] Collections, Documents, upload/search e Vector Snapshots.
- [ ] Providers/models e discovery separado da persistência.
- [ ] Catálogos e compatibilidade de ModelSpec/estratégias.
- [ ] Skills e versões.
- [ ] ChatSurfaces, lifecycle e Access Keys.
- [ ] Paginação/export conforme capacidade real.

**Dependência:** Fases 1–5.  
**Aceite:** todos os comandos desse conjunto possuem mapa de capacidade/permissão e fluxo funcional no CI/E2E.  
**Esforço estimado:** 4–7 dias.

### Fase 7 — runtime, Sessions e evidências

**Entregas:**

- [ ] Runtime público por SDK/adapter, com credencial própria.
- [ ] Agent e Network Run, HTTP e streaming.
- [ ] Contratos de output/External Context.
- [ ] Active Run, observe/reattach e cancelamento.
- [ ] Sessions/mensagens e histórico administrativo autorizado.
- [ ] Rerun explícito e reset de contexto suportado.
- [ ] Traces, invocations, snapshots e diagnostics.
- [ ] Usage/metrics existentes.
- [ ] Auditoria administrativa, sem confundir com runtime tracing.
- [ ] Interrupção, deadline, gap e degradação sem duplicação de Run.

**Dependência:** Fases 1–6.  
**Aceite:** cenários de perda de conexão e autorização por target/ambiente passam com Agent e Network.  
**Esforço estimado:** 3–5 dias.

### Fase 8 — gestão declarativa e recuperação

**Entregas:**

- [ ] Schema de manifest versionado.
- [ ] Validate/diff/plan/export.
- [ ] Apply por operação e dependências.
- [ ] IDs/revisões esperadas e revalidação antes de mutar.
- [ ] Checkpoint e retomada por reconciliação.
- [ ] Relatório parcial/skipped e código de saída próprio.
- [ ] Importação de categorias sem concessão implícita.
- [ ] Referências protegidas para credenciais.
- [ ] Nenhuma publicação/prune implícitos.
- [ ] Não usar export incompleto como PATCH destrutivo.

**Dependência:** Fases 2–7.  
**Aceite:** aplicação repetida de um plano determinístico não duplica recursos; falha parcial é observável e retomável conforme contratos reais.  
**Esforço estimado:** 3–5 dias.

### Fase 9 — distribuição, documentação e release

**Entregas:**

- [ ] Build do executável Go `woobe` e versão semântica com revisão identificável.
- [ ] Instalação limpa a partir de binários publicados e `go install` por tag.
- [ ] CI do CLI e suites integradas do backend.
- [ ] Documentação de cada comando, permissão, exemplo e capacidade mínima.
- [ ] Completion e smoke de help.
- [ ] Matriz de compatibilidade cliente/servidor/protocolo.
- [ ] Binários por sistema/arquitetura declarados, checksums SHA-256 e manifesto dos artefatos.
- [ ] Guia de migração do CLI mínimo Python para o CLI Go.
- [ ] Changelog e notas de release com capabilities realmente entregues.
- [ ] Smoke em instalação Woobe com infraestrutura real e targets de teste.

**Dependência:** fases anteriores da versão.  
**Aceite:** binário Go instalado do artefato final executa os E2Es previstos, inclusive o fluxo agent-friendly do §15.5, com CI aprovado e documentação consistente.  
**Esforço estimado:** 2–4 dias.

### 18.1. Estimativa consolidada

As faixas somam **31–53 dias de engenharia**, para uma pessoa familiarizada com o backend e com Go, com ambiente de testes disponível. A Fase 2 inclui a implementação do cliente Go e o porte dos comportamentos do protótipo; não presume reutilização do pacote Python. Trata-se de dimensionamento, não promessa de prazo.

Parte relevante do trabalho é backend: completar autorização, introspecção, categorias e contratos ausentes. Se essas capacidades já existirem em outra branch e estiverem validadas, o esforço cai. A comparação divergente e as lacunas encontradas impedem estimar honestamente o trabalho apenas pela quantidade de comandos.

## 19. Divisão recomendada de PRs

| PR | Escopo concreto | Validação determinante |
| --- | --- | --- |
| 1 | Port seletivo de Control Keys e migração corrigida. | Upgrade/fresh install e suites existentes. |
| 2 | Registro de operações, tenancy e política de principais humanos. | Matriz de autorização e aliases. |
| 3 | Catálogo/capabilities/introspecção/preflight. | Schemas e isolamento de informações. |
| 4 | Module Go, Cobra, contexto, auth e output. | Binário, login/refresh, stdin e erros tipados. |
| 5 | Workspace/Project/access/environment keys. | Integração de membership e scopes. |
| 6 | Control/Project/Runtime Keys e delegação. | Lifecycle, subconjunto e emissão segura. |
| 7 | Categorias versionadas e aplicação a grants. | Custom categories sem ampliação implícita. |
| 8 | Agents, prompts/contratos/model configs e releases. | Draft/staging/production imutável. |
| 9 | Networks, draft, versões e ativações. | Multiplicidade e concorrência. |
| 10 | Tools/MCP e providers/models/catálogos. | Efeitos, credentials e permissão de Tool. |
| 11 | Knowledge, upload, pesquisa e snapshots. | Indexação, autorização e acompanhamento. |
| 12 | Skills/ChatSurfaces e suas chaves. | Versionamento e scope da superfície. |
| 13 | Runtime público e administração de Sessions/Runs. | Reattach/gaps/target/ambiente. |
| 14 | Traces, uso e auditoria administrativa. | Projeção/consulta e autenticidade da evidência. |
| 15 | Manifests: validate/diff/plan/export. | Schemas, permissões e completude. |
| 16 | Manifests: apply/checkpoint/reconciliação. | Concorrência e falha parcial sem duplicação. |
| 17 | Distribuição, CI, documentação e compatibilidade. | Artefato final e E2E real. |

PRs podem ser subdivididos conforme tamanho. Não agrupar mudanças de autorização com dezenas de parsers apenas para reduzir a contagem. Quantidade de commits não é critério de conclusão.

## 20. Marcos de release

| Marco | Entrega verificável |
| --- | --- |
| **Fundação — 0.1** | Control Keys integradas, escopos estáveis, categorias customizáveis, contexto/auth e administração Workspace/Project/credenciais. |
| **Cobertura operacional — 0.2** | Comandos dos recursos administrativos suportados, releases, ambientes, runtime e evidências; autoridade mínima/máxima testada. |
| **Automação declarativa — 0.3** | Validate/diff/plan/apply/export com revisão, retomada e resultado parcial. |
| **Compatibilidade — 1.0** | Comandos/DTOs estáveis, matriz de suporte publicada e política formal de depreciação. |

As versões são proposta de organização. O número já declarado no protótipo não comprova que o marco funcional esteja entregue.

O pedido de planejamento completo inclui todos os marcos. Entregar apenas request/control-key ou apenas o marco 0.1 não completa a cobertura máxima descrita.

## 21. CI e publicação

### 21.1. CLI

Executar no CI:

- `gofmt` com gate de diff vazio, `go vet ./...` e `go mod verify`.
- `go test ./...` para comandos, contexto, contratos, planos e output sem efeitos externos.
- `go test -race ./...` em runner compatível, incluindo renovação de sessão e streams quando houver concorrência.
- Testes HTTP com `net/http/httptest` para cookies/CSRF, paginação, upload, erros, cancelamento e resultado incerto; referência: [documentação oficial](https://pkg.go.dev/net/http/httptest).
- E2E de autenticação/cookies/CSRF e Control Keys.
- Recuperação de streams por fixtures e stack real.
- `go build ./cmd/woobe`, teste do executável instalado e build dos targets de distribuição declarados em ambiente limpo.
- Smoke de `woobe --help` e help das famílias publicadas.
- Conferência de exemplos e compatibilidade de flags legadas.
- Varredura de output/fixtures para segredos de teste.
- Matriz inicial Linux, macOS e Windows, em amd64 e arm64; build não substitui smoke de execução no sistema suportado. Documentar limitações verificadas de armazenamento de credenciais por plataforma.

Unitários usam `testing`, subtests e fixtures em `testdata/`; fuzzing é direcionado a parsing de input, enums/extensões e frames/eventos de streaming, com tempo limitado no CI. Não usar testes Python para validar o cliente Go; os testes existentes do backend mantêm suas ferramentas atuais.

### 21.1.1. Distribuição do CLI Go

- Nome do executável: `woobe` (`woobe.exe` no Windows). Publicar archives por `GOOS`/`GOARCH`, checksums SHA-256 e instruções de instalação/atualização.
- Fixar versão, revisão e estado do build na compilação e expô-los em `woobe version --output json`; não confundir versão do binário com capabilities do servidor.
- Preferir builds sem CGO para distribuição autônoma; adapters de credenciais e dependências precisam ser validados nesse modo. Exceções por plataforma exigem contrato de instalação explícito antes da publicação.
- Publicar em tags semânticas do repositório `woobe-cli`; documentar `go install` por tag com o module path real. Não usar `@latest` para instalações reprodutíveis de CI.
- Instalação do binário não exige Python, pip, uv ou o código-fonte do backend Woobe.
- Scripts/workflows de release devem verificar artefatos e documentação. Uso eventual de uma ferramenta de release não substitui os gates acima.

### 21.2. Backend

Executar os gates exigidos pela Woobe, ampliando:

- Authorization/tenancy/membership.
- API key/control key lifecycle.
- Migrações e cabeça Alembic única.
- Arquitetura: Core sem dependência de HTTP/CLI.
- Contratos de catálogo e coverage de operações.
- Agent/Network versioning e release immutability.
- Runtime Protocol v2 e public runtime authorization.
- Permissões HTTP/MCP e redaction.
- Instalação fresh/upgrade e cenários de delegação.

Não exigir secrets de production para testes de PR. Usar recursos de teste e credenciais próprias de curta duração quando um provedor real for necessário.

### 21.3. Política de publicação

- Release identifica a revisão exata validada.
- Documentação informa a versão mínima do servidor para cada capability.
- Versão sem suporte a uma operação não a anuncia como pronta.
- Separar versão da plataforma, versão do CLI e versões de objetos de domínio.
- Mudança de sintaxe/semântica estável passa por depreciação documentada.
- Não sobrescrever artefato de uma versão já publicada.
- Um novo catálogo de permissões não amplia as categorias/grants existentes automaticamente.

## 22. Critério final de conclusão

O CLI está completo para o escopo deste plano quando:

- [ ] O cliente é implementado em Go, tem fonte canônica em `woobe-cli` e é instalado como binário sem dependência operacional de Python.
- [ ] Descoberta, schemas e o fluxo completo de criação/edição/estruturação/publicação por agente externo atendem ao contrato do §15.5.

- [ ] Workspace, Project e runtime têm comandos organizados e contexto inequívoco.
- [ ] Todos os recursos administrativos públicos suportados possuem comando específico ou acesso genérico documentado.
- [ ] Principals humanos e de automação usam a mesma política de operação aplicável.
- [ ] Categorias existentes foram reaproveitadas ou a extensão necessária foi integrada.
- [ ] É possível criar categoria nova sem alterar o cliente.
- [ ] É possível conceder uma única permissão em um único Project.
- [ ] É possível conceder o conjunto máximo permitido em Projects explicitamente selecionados.
- [ ] A mesma credencial pode ter conjuntos diferentes em Projects diferentes.
- [ ] Role, categoria, grant, Runtime Key e MCP permission são apresentados como conceitos distintos.
- [ ] Não existe escalada por categoria, chave derivada, rotação, request ou alias.
- [ ] A enumeração de objetos respeita a autoridade do principal.
- [ ] O ciclo draft → staging → release → produção → rollback funciona.
- [ ] Models/Agents preservam extensibilidade de tipos/modalidades.
- [ ] Runs/Sessions/streams obedecem aos contratos atuais sem duplicação por retry.
- [ ] Segredos são protegidos no servidor e na CLI.
- [ ] Configuração declarativa respeita revisão, dependências e autoridade.
- [ ] Migrações, CI e E2Es da release final passaram.
- [ ] O artefato distribuído corresponde ao código validado.
- [ ] Documentação distingue capacidades disponíveis de propostas futuras.

## Apêndice A — perfis iniciais com conjuntos explícitos

Os conjuntos abaixo são propostas baseadas no catálogo encontrado. A revisão definitiva deve ser publicada pelo servidor.

| Perfil | Permissões de Project |
| --- | --- |
| `agent-reader-minimal` | `agent:read`. |
| `agent-editor` | `project:read`, `agent:read`, `agent:write`. |
| `network-editor` | `project:read`, `network:read`, `network:write`. |
| `knowledge-editor` | `project:read`, `knowledge:read`, `knowledge:write`. |
| `version-builder` | `project:read`, `agent:read`, `agent:version`, `network:read`, `network:version`; `catalog:read` quando integrado. |
| `production-publisher` | `project:read`, `agent:read`, `agent:production`, `network:read`, `network:production`. |
| `runtime-observer` | `project:read`, `run:read`, `observability:read`, `usage:read`; `run:observe` quando integrado. |
| `project-administrator` | Conjunto completo das permissões de Project na revisão explicitamente selecionada. |

`project-reader` pode usar:

~~~json
[
  "project:read",
  "project:access:read",
  "agent:read",
  "network:read",
  "tool:read",
  "knowledge:read",
  "provider:read",
  "model:read",
  "skill:read",
  "chat_surface:read",
  "run:read",
  "observability:read",
  "usage:read"
]
~~~

Esse conjunto inclui informação funcional/operacional, como mensagens e documentos apenas quando a projeção correspondente autorizar. Não incluir `project:environment:read`, `api_key:write` ou `chat_surface:keys` por conveniência; o último combina leitura e emissão no catálogo atual.

Uma chave limitada a um target específico exige suporte de conditions/resource selectors no servidor. O grant atual de Control Keys é por Project e operação: não prometer restrição a um único Agent só porque o CLI recebeu seu ID.

Permissões de Workspace são selecionadas separadamente. `workspace-key-manager` só recebe `keys:*` explicitamente necessários e continua limitado pela autoridade delegável sobre os Projects.

## Apêndice B — decisões de produto/implementação adotadas

| ID | Decisão |
| --- | --- |
| D01 | API é o ponto de entrada e o servidor é a autoridade. |
| D02 | Workspace é boundary de propriedade; Project é boundary técnico. |
| D03 | CLI pode ter cobertura máxima com credencial mínima. |
| D04 | Implementar o CLI em Go no repositório `woobe-cli`; o protótipo Python serve apenas como referência de contratos e compatibilidade. |
| D05 | SDKs atuais continuam com finalidade de runtime. |
| D06 | Portar seletivamente a branch divergente sobre a master atual. |
| D07 | Preservar 50 identificadores de Control Permissions encontrados, com extensões explícitas. |
| D08 | Reutilizar categorias citadas pelo usuário antes de criar entidades novas. |
| D09 | Categorias são perfis versionados; grants materializam o conjunto concedido. |
| D10 | Versão nova de categoria não amplia credenciais automaticamente. |
| D11 | Primeira versão usa allow-only e ausência de grant implica negar. |
| D12 | Produção exige operação/credencial apropriada e release imutável. |
| D13 | HTTP genérico segue a mesma autorização dos comandos específicos. |
| D14 | POST não é automaticamente “escrita”; classificar pelo efeito. |
| D15 | Execução de runtime e administração não compartilham uma chave universal. |
| D16 | Apply não é transação distribuída; falha parcial é explícita. |
| D17 | Não prometer endpoints ou capabilities apenas porque existe permissão no catálogo. |
| D18 | A conclusão depende de comportamento/CI/E2E, não da contagem de commits. |

## Apêndice C — fontes primárias consultadas

As URLs abaixo estão fixadas nas referências estudadas quando apontam para código. Permitem distinguir contrato observado de proposta deste planejamento.

| Fonte | Evidência |
| --- | --- |
| [Woobe: master estudada](https://github.com/A1b3rt0M3rcad0/woobe/tree/42e6667008db4e1306c05714af7a0df5b3ce7dd2) | Base atual. |
| [Branch do control plane](https://github.com/A1b3rt0M3rcad0/woobe/tree/177d580eaaca4ee8743e1125c440cc3a25f0d76e) | Implementação não integrada do CLI/Control Keys. |
| [Comparação master/branch](https://github.com/A1b3rt0M3rcad0/woobe/compare/42e6667008db4e1306c05714af7a0df5b3ce7dd2...177d580eaaca4ee8743e1125c440cc3a25f0d76e) | Divergência 132/214 e conjunto de alterações. |
| [AGENTS.md](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/AGENTS.md) | Orientação de leitura e boundaries. |
| [Índice de domínio](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/docs/agents/DOMAIN_INDEX.md) | Ownership de Workspace, Project, runtime e recursos. |
| [Invariantes](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/docs/agents/INVARIANTS.md) | Projects com várias Networks, persistência e release imutável. |
| [Arquitetura](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/docs/ARCHITECTURE.md) | API/Core/Workers e execução. |
| [ADR 0002: autenticação/tenancy](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/docs/adr/0002-authentication-tenancy.md) | Sessão, refresh rotation e tenant ownership. |
| [Enums de Identity](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-core/src/modules/identity/domain/enums.py) | Owner/admin/member/viewer. |
| [Rotas de Identity](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/identity/routes.py) | Workspace, convites e restrições do endpoint. |
| [Resposta de autenticação](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/identity/auth_endpoints.py) | Cookies e CSRF. |
| [TenantAuthorizer](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-core/src/shared/security/tenancy.py) | Isolamento e ownership de recursos. |
| [ADR 0005: Control Keys](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/docs/adr/0005-workspace-control-plane-keys.md) | Grants, delegação, linhagem e grant do criador. |
| [50 Control Permissions](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/packages/woobe-core/src/shared/security/control_plane.py) | 7 permissões de Workspace e 43 de Project. |
| [Mapeamento HTTP de permissões](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/packages/woobe-api/src/woobe_api/security/control_plane_permissions.py) | Classificação por método/prefixo e lacunas. |
| [ControlKeyService](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/packages/woobe-core/src/modules/core/infra/services/control_key_service.py) | CRUD/lifecycle, materialização de grants e subconjunto. |
| [Rotas de Control Keys](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/packages/woobe-api/src/woobe_api/http/core/control_key_routes.py) | Inputs e endpoints implementados na branch. |
| [Protótipo do CLI](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/packages/woobe-cli/src/woobe_cli/main.py) | Argparse, request/control-key e transporte. |
| [Migração de Control Keys](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/packages/woobe-core/migrations/versions/0072_workspace_control_keys.py) | Revision 0072 que precisa ser reconciliada. |
| [Migração 0072 da master](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-core/migrations/versions/0072_provider_model_specs.py) | Identificador já utilizado na master. |
| [Rotas de Project/API Keys](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/core/routes.py) | Projects, acesso e environment/API/runtime keys. |
| [API key scopes e parsing](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-core/src/shared/security/api_keys.py) | Escopos de runtime e compatibilidade legada. |
| [Runtime Key DTO](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-core/src/modules/core/application/dtos/runtime_api_key_dtos.py) | Target, ambientes, interfaces e jobs rejeitado. |
| [Rotas principais de Agent](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/agent/routes.py) | Agents/releases, Knowledge, Runtime e Tools. |
| [Network resources](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/network/resource_routes.py) | Múltiplas Networks por Project. |
| [Network draft/promotion](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/network/runtime_routes.py) | Draft revision, promoção, Sessions e Runs. |
| [Network management](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/network/management_routes.py) | Activation com versão de produção esperada. |
| [Runtime environments](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/shared/runtime_environment_routes.py) | Habilitação/contexto por target/ambiente. |
| [MCP Tools routes](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/agent/mcp_tools_routes.py) | Discovery, refresh, permissions e OAuth MCP. |
| [Política MCP](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-core/src/modules/agent/domain/mcp_permissions.py) | Allow/deny/review. |
| [Vector Snapshot routes](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/agent/vector_snapshot_routes.py) | Overview, preview, criação e consulta. |
| [Skills routes](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/agent/skill_routes.py) | Catálogo e versões. |
| [ChatSurface routes](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/chat_surface/routes.py) | Superfícies e lifecycle de keys. |
| [Metering routes](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/packages/woobe-api/src/woobe_api/http/metering/routes.py) | Consultas e rejeição de escrita externa de usage. |
| [Streaming e reattach](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/docs/runtime/STREAMING.md) | Runtime v2 e recuperação da mesma Run. |
| [SDK Go](https://github.com/A1b3rt0M3rcad0/woobe-sdk-go/blob/5a78817a64dc5dcb15aa1d38ec54d4c289f7f56c/README.md) | Runtime público, interfaces e jobs não suportado. |
| [SDK Python](https://github.com/A1b3rt0M3rcad0/woobe-sdk/blob/70265537d2ac3eddd2738c56d671b189794c5e5b/README.md) | Runtime, contratos, eventos e lazy execution. |
| [Teste de membership por Project](https://github.com/A1b3rt0M3rcad0/woobe/blob/42e6667008db4e1306c05714af7a0df5b3ce7dd2/tests/integration/security/test_project_membership_authorization_postgres.py) | Isolamento e acesso implícito do owner. |
| [Testes de delegação](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/tests/unit/core/test_control_key_service_policy.py) | Impedimento de própria linhagem e concessão mais ampla. |
| [Integração de Control Keys](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/tests/integration/security/test_control_key_guard_postgres.py) | Grant e permissão exigida no Project. |

## Apêndice D — primeira sequência executável de trabalho

1. Fixar master e confirmar a localização das categorias já criadas.
2. Portar a base de Control Keys, corrigindo a migração e os boundaries.
3. Fechar a classificação HTTP e a matriz de principals/permissões.
4. Publicar catálogo/capabilities e introspecção própria.
5. Implementar o module Go, a árvore Cobra, fundação local, auth, contexto, saída e discovery agent-friendly do CLI.
6. Entregar Workspace/Project/keys/grants e categorias.
7. Entregar configuração e ciclo de releases de Agent/Network.
8. Expandir Tools/Knowledge/providers/models/Skills/surfaces.
9. Integrar runtime e consultas de evidência.
10. Entregar gestão declarativa e validar o artefato final contra uma Woobe real.
