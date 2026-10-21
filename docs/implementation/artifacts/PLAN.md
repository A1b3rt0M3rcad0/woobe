# Woobe — Plano de implementação de Artifacts, Workspaces e exploração documental

**Data-base:** 20 de outubro de 2026.  
**Estado:** planejamento técnico; não constitui implementação, homologação, publicação ou criação de branch/PR.  
**Execução prevista:** **60 etapas, exatamente um commit por etapa, uma única branch e um único PR mantido em Draft do início ao fim.**  
**Repositório canônico:** `A1b3rt0M3rcad0/woobe`.  
**Branch proposta:** `feat/artifact-workspaces-document-runtime`.  
**Título proposto do PR:** `feat: introduce artifact workspaces and hierarchical document runtime`.

## Sumário

1. Decisões e escopo consolidado.
2. Baseline consultada e compatibilidade.
3. Regras da branch, dos commits e do Draft PR.
4. Arquitetura e organização do código.
5. Modelo de domínio e invariantes.
6. Autorização, External Context e continuidade de Sessions.
7. Armazenamento, upload, revisões e retenção.
8. Processamento documental e índice hierárquico.
9. Contratos de API, runtime, Tools e clientes.
10. Experiência visual e operações.
11. Plano sequencial de 60 etapas/commits.
12. Matriz de requisitos, aceitação e validação final.
13. Fontes e limites da análise.

---

## 1. Decisões e escopo consolidado

### 1.1. Resultado esperado

Entregar uma capacidade **Artifacts** de primeira classe na Woobe, capaz de armazenar arquivos, preservar suas revisões, preparar representações consultáveis, construir índices hierárquicos e disponibilizar operações de leitura, busca, criação e transferência. Essa capacidade terá dois acessos sobre os mesmos recursos:

- **Acesso direto:** uma aplicação consumidora, como a Lipo, opera Workspaces e arquivos pela API/SDK sem executar um Agent.
- **Acesso agentic:** o runtime resolve um Workspace autorizado a partir do External Context e fornece ao Agent as capacidades permitidas para trabalhar com seus arquivos.

O Explorer é a interface dessa capacidade, não seu backend nem uma fonte independente de dados. Os artefatos existem e são utilizáveis sem uma conversa, um Agent ou uma Session ativos.

### 1.2. Decisões definitivas deste plano

| Assunto | Decisão |
|---|---|
| Boundary de negócio | Um módulo `artifacts` dentro de `woobe-core`; não três domínios concorrentes de arquivos. |
| Deployment | Reutilizar API e Workers da Woobe; processamento pesado pode usar perfil separado do mesmo pacote de Workers. Não criar um novo microsserviço obrigatório. |
| Workspace | Entidade persistente, independente de Session/Run; um Workspace pode servir muitas Sessions autorizadas. |
| Cardinalidade | Provisionamento por API e consultas paginadas; não criar bucket, banco, processo ou Agent por Workspace. |
| Storage | Filesystem e S3-compatible atrás de uma porta de object storage. |
| Metadados | PostgreSQL; os bytes não ficam em campos JSON de mensagens ou de Runs. |
| Originais | Revisões imutáveis e verificadas por hash. Markdown, índices e resumos são derivados. |
| Documentos | Processadores substituíveis; extração textual, estrutura, tabelas, figuras, renderizações e OCR seletivo. |
| PageIndex | Adapter local e opcional, fixado por versão/revisão, para indexação; sem dependência de PageIndex Cloud. |
| Recuperação | Catálogo/busca textual + árvore + leitura sob demanda; nenhum banco vetorial obrigatório. |
| RAG existente | Não destruir nem reinterpretar Releases existentes. Novos Agents podem operar sem recuperação automática legada. |
| Tools externas | Somente HTTP e MCP, com contratos explícitos de arquivos e destinos autorizados. |
| Domínio da aplicação | Nenhum tipo obrigatório `Student`, `Study`, `Wave`, `Roadmap` ou regra pedagógica no core. |
| Aplicações externas | Lipo é caso de aceitação e exemplo de consumidor; seu repositório não será modificado por este PR. |
| Clientes | CLI, SDK Go, SDK Python, runtime-client Web e ChatSurface incluídos na entrega de código. |
| Governança | Um commit por etapa e PR sempre Draft; sem merge, auto-merge, tags, deploy em produção ou releases. |

**Exclusão expressa:** WOS e WKS não participam desta implementação, nem como dependência, adapter obrigatório, armazenamento ou coordenador.

### 1.3. Refinamentos que substituem o planejamento anterior de Session Files

Este documento consolida a conversa atual e substitui, para esta entrega, as decisões incompatíveis do plano anterior `WOOBE_PLANO_IMPLEMENTACAO_SESSION_FILES_MULTIMODAL.md`:

1. `ArtifactWorkspace` substitui o conceito limitado de `FileSpace` criado necessariamente para cada Session. Não implementar ambos como domínios paralelos.
2. A aplicação pode criar o Workspace **antes de qualquer Session**, carregar arquivos e depois vinculá-lo a várias conversas.
3. A Woobe pode manter os originais e todos os derivados. A Lipo guarda identidade pedagógica, versões aceitas e referências; não precisa duplicar todos os binários.
4. Processamento, busca textual e navegação hierárquica passam a fazer parte da capacidade Artifacts. Não depender de outro servidor de conhecimento.
5. `@arquivo` continua sendo uma ergonomia de seleção, mas a chamada efetiva usa referência tipada e revisão exata.
6. Preservam-se entrada visual, geração de imagem, transferência HTTP/MCP, CLI e SDKs do planejamento anterior.
7. Não criar uma migração de um módulo Files hipotético: na baseline remota consultada ele não foi identificado como implementação deste plano. Se houver implementação local posterior, auditar e migrar explicitamente antes de duplicar.

### 1.4. Recorte funcional obrigatório e extensões não prometidas

**Obrigatório neste PR:** Workspaces independentes; seleção por External Context; autorização por operação; filesystem/S3; arquivos e revisões; uploads recuperáveis; PDFs textuais, Markdown, texto, JSON, CSV, DOCX e imagens nas capacidades declaradas; OCR seletivo; extração de figuras/tabelas; índice estrutural nativo; adapter PageIndex; navegação e busca; referências e citações; escrita de artefatos; pontes HTTP/MCP; entradas visuais e geração de imagem com pelo menos um provider real qualificado; API, CLI, SDK Go/Python, Playground, Network e ChatSurface; operação e testes.

**Contratos extensíveis, mas não entrega anunciada neste PR:** transcrição de áudio, síntese de voz, compreensão/geração de vídeo, execução arbitrária de código, terminal POSIX do Agent, edição colaborativa de arquivos, conectores proprietários, sincronização com Drives externos e Runtime Jobs públicos genéricos. Esses formatos podem ser armazenados como binários opacos quando a policy permitir, sem declarar processamento suportado.

O `ProcessingJob` de Artifacts **não implementa nem habilita implicitamente** o `/v1/jobs` genérico do runtime.

---

## 2. Baseline consultada e compatibilidade

### 2.1. Evidência observada

A consulta ao GitHub em 20/10/2026 identificou `master` da Woobe em **`3dbcb3e1a7559f4a50ebca320e411933d46e8012`**. O PR **#219** permanecia aberto e Draft, na branch `fix/provider-modelspec-discovery-sync-integrity`, com HEAD **`1a3f22c0e7ba04d3c18730e1c4ef83c6eade30d5`**. Esse PR é alheio à implementação e não será alterado ou incorporado automaticamente. [S01, S02]

| Área existente | Evidência e consequência para o plano |
|---|---|
| Core, API e Workers | `docs/ARCHITECTURE.md` exige Core independente do transporte e consumo dos módulos por `entrypoint.py`/background boundary. Preservar essas regras. [S03] |
| External Context | Campos `session` são fixados e devem ser omitidos pelo chamador após inicialização; campos `run` variam por execução. Não mudar silenciosamente essa semântica. [S03, S04] |
| Storage de Knowledge | Existem porta e adapters local/S3 específicos de documentos. Reutilizar implementação por uma abstração genérica sem passar Collections fictícias nem mover dados legados por conveniência. [S05] |
| Knowledge Strategy | O catálogo consultado registra `rag` e preserva seu fallback histórico. Acrescentar opção explícita de ausência de recuperação; ausência de campo continua significando o comportamento legado. [S06] |
| Runtime público | Há Run, stream, reattach, cancelamento e validação de contratos; `/v1/jobs` ainda retorna 501. Não depender desse endpoint para processamento de documentos. [S07] |
| Modelo e multimodalidade | Há abstrações de operações/modalidades, mas identificadores declarados não equivalem a implementação executável de todos os providers. Revalidar catálogo e adapters na etapa inicial. [S08] |
| SDK Go | Cliente público do runtime, com Runtime Key, sem dependências externas obrigatórias e com reattach. Novas APIs devem preservar chamadas textuais existentes. [S09] |
| CLI | `internal/cli/runtime_input.go` exige entrada textual e usa o SDK Go. Precisa evoluir de forma aditiva para `content_parts` e Artifacts. [S10] |

**Limite da auditoria:** foi feita leitura dirigida de código, documentação, metadados do GitHub e do plano anterior. Não foi executada a stack, o CI, o SDK ou os parsers nesta elaboração. A etapa 01 deve atualizar a baseline e registrar divergências reais.

### 2.2. Um PR e clientes em repositórios diferentes

CLI e SDKs possuem repositórios separados. Um único PR não modifica quatro árvores Git independentes. Para manter a restrição literal já registrada no planejamento anterior, este plano incorpora as fontes dos clientes em:

```text
clients/woobe-cli/
clients/woobe-sdk-go/
clients/woobe-sdk-python/
```

A importação será um **snapshot auditável em um único commit**, com SHA, origem, licenças e manifesto de arquivos; não uma importação de histórico que acrescente centenas de commits à série. Preservar module paths Go, nome do pacote Python e interfaces públicas. O `go.work` conecta CLI e SDK Go localmente durante os testes.

Os repositórios separados não recebem commits, PRs ou publicação durante este trabalho. Passam a ser destinos previstos de sincronização/distribuição **somente após decisão posterior**. Não configurar espelhamento automático neste PR. Os clientes compilados a partir da branch serão novos; os clientes já publicados continuarão com suas capacidades anteriores.

---

## 3. Regras da branch, dos commits e do Draft PR

### 3.1. Procedimento de execução

1. Confirmar árvore limpa, `origin`, branch de integração e SHA; inventariar alterações locais sem descartá-las.
2. Criar a branch proposta a partir da `master` real. Não implementar no PR #219.
3. Concluir a etapa 01 com documentação, baseline e guardas; produzir o primeiro commit de conteúdo.
4. Abrir imediatamente o **único PR já com `draft=true`**, antes das etapas funcionais seguintes.
5. Executar as etapas 02–60 na mesma branch. Cada etapa inclui código, testes, documentação incremental e evidências correspondentes em seu próprio commit.
6. Preservar o PR em Draft inclusive com todas as verificações aprovadas. O estado final é **Draft aberto, entrega de implementação encerrada**, não Ready for review.

### 3.2. Regra de um commit por etapa

- Exatamente **60 commits de implementação**, sem commits vazios, merges intermediários, commits isolados de formatação ou commits de correção sem etapa.
- Usar a mensagem indicada em cada etapa e trailer `Plan-Step: NN/60`.
- Antes de passar à próxima etapa, concluir seus testes e conferir que não altera o comportamento legado sem autorização explícita no plano.
- Corrigir uma etapa antes de seu commit. Correções posteriores devem ser absorvidas por amend/rebase controlado na etapa responsável, preservando dependências, evidências e os 60 commits finais.
- Não reescrever branch compartilhada nem forçar push cegamente; usar lease validada quando a política do repositório permitir. Conflito de lease exige inspeção.
- Se a base mudar, fazer rebase, atualizar o SHA-base e repetir gates afetados; não acrescentar um merge commit à série.
- Uma etapa que não cumpre os critérios permanece incompleta; não substituí-la por TODOs para manter a contagem.

### 3.3. Registro e guardas

Criar `docs/implementation/artifacts/PROGRESS.md` e um manifesto com etapa, dependências, status, testes e evidência. O arquivo não pode registrar o SHA do próprio commit que o contém: SHAs são reconciliados pelo CI/artefato de validação e pelo corpo do PR após o commit. Registrar comandos, ambiente e resultado real, diferenciando `passed`, `failed`, `not_run` e `skipped`.

Acrescentar verificação de Draft nas ações suportadas pelo GitHub, contagem/trailers da série, detecção de alterações fora do escopo e ausência de publicação. A guarda apenas reprova o workflow quando necessário; não possui permissão para alterar PRs alheios ou efetuar merge.

**Proibido durante toda a execução:** converter o PR para Ready, habilitar auto-merge, mesclar, criar tags, publicar pacotes/imagens, disparar releases, promover ambientes de produção ou alterar a branch principal diretamente.

---

## 4. Arquitetura e organização do código

### 4.1. Fluxo conceitual

```text
Aplicação consumidora ── API/SDK ──┐
                                  v
                         Artifacts entrypoint
                                  |
Agent/Network ── RuntimeAccess ────┤
                                  v
          autorização + casos de uso + catálogo/revisões
                       |                         |
                  ObjectStorage          ProcessingJobs
                  local / S3                  |
                                   Workers da própria Woobe
                                              |
                         representação canônica + derivados
                                              |
                              índices nativo / PageIndex
                                              |
                     catálogo → busca → árvore → leitura
```

API direta e capacidades agentic chamam os mesmos casos de uso; não duplicar regras de ownership, quota, revisão ou remoção. O runtime não entrega o cliente S3, caminhos do host ou repositórios SQL ao Agent.

### 4.2. Árvore de código proposta

```text
packages/woobe-core/src/modules/artifacts/
  domain/                         # entidades, referências, estados e policies
  application/
    ports/                        # storage, processors, indexers, authorizer
    use_cases/                    # operações transacionais e coordenação
    contracts/                    # DTOs e schemas sem dependência HTTP
  infra/
    database/                     # SQL e repositories
    storage/                      # local / S3
    processors/                   # native, Docling, OCR
    indexers/                     # structural, PageIndex
    search/                       # catálogo e índice textual
    external_tools/               # adaptação de transferência, não novo executor
  composition/
  presentation/                   # contratos conforme convenção existente
  entrypoint.py
  background_boundary.py

packages/woobe-api/src/woobe_api/http/artifacts/
packages/woobe-workers/src/woobe_workers/consumers/artifacts/
packages/woobe-frontend/src/features/artifacts/
packages/woobe-runtime-client/src/  # tipos/eventos compartilhados
packages/woobe-embed/src/           # consumidor browser-facing
clients/                          # CLI e SDKs importados
contracts/artifacts/v1/            # fixtures/schemas canônicos da entrega
```

Nomes novos são propostas. Arquivos de composição, testes e migrações devem seguir a convenção real inventariada na etapa 01; não criar um segundo framework de DI, outbox, contratos ou migração.

### 4.3. Dependências e interfaces

`Artifacts` não importa implementações de Agent/Network para processar um documento. O host injeta portas restritas quando é preciso invocar um modelo ou uma Tool. `Agent`/`Network` consomem uma fachada autorizada de Artifacts, não suas tabelas.

Portas a definir: `ArtifactGateway`, `WorkspaceAuthorizer`, `ObjectStorage`, `DocumentProcessor`, `DocumentIndexer`, `DocumentModelGateway`, `ProcessingScheduler` e `ArtifactTransferPort`. Cada uma terá versão de contrato, erro tipado, limites e testes de conformidade.

PageIndex e Docling permanecem em `infra` e extras/perfis de Workers. Instalar o core ou iniciar a API sem esses extras precisa continuar funcionando. Não carregar modelos pesados durante import de módulo ou startup da API.

`Observer` permanece passivo: registra/exporta eventos; não escolhe documentos, aprova acessos, agenda etapas ou decide o fluxo de execução.

---

## 5. Modelo de domínio e invariantes

### 5.1. Entidades e registros

| Entidade/registro | Conteúdo e função |
|---|---|
| `ArtifactWorkspace` | `id`, `project_id`, `environment`, `external_namespace`, `external_key`, nome, status, storage profile, quota/retention policy e versão CAS. |
| `WorkspaceGrant` | Principal/categoria autorizada, seletor de Workspace/namespace, ações, validade e revisão de revogação; utilizar autoridade existente, sem um segundo sistema de usuários. |
| `Artifact` | Identidade lógica, Workspace, tipo, diretório/caminho lógico, nome, ponteiro para revisão atual e estado. |
| `ArtifactRevision` | Revisão imutável, chave de objeto, MIME verificado, tamanho, SHA-256, origem e produtor. |
| `ArtifactHeadHistory` | Intervalos de versões do catálogo para ponteiros de revisão, caminho/membership e estado; permitem seleção estável sem copiar a lista completa do Workspace em cada Run. |
| `UploadIntent` | Chave idempotente, dados esperados, partes/offset, reserva de quota, estado e recibo de finalização. |
| `ProcessingProfileRevision` | Receita imutável de processor/indexer, parâmetros, versões e limites; sem segredo embutido. |
| `ProcessingJob` | Revisão de entrada, receita, estado, tentativa, lease/fencing, etapas concluídas e erro seguro. |
| `RepresentationSet` | Publicação atômica de um conjunto coerente de derivados para uma revisão/perfil. |
| `ArtifactRepresentation` | Markdown, estrutura JSON, texto, tabela, figura ou renderização, com seu próprio hash e vínculo à origem. |
| `DocumentIndex` e `DocumentNode` | Versão do índice, adapter, raiz/hierarquia, títulos/resumos e localizadores canônicos. |
| `RuntimeArtifactBinding` | Workspace efetivo, scope, policy de Release/Node e catálogo observado em uma Session/Run. |
| `SourceRef` / `SourceManifest` | Referência verificável de origem e conjunto de fontes efetivamente lidas/usadas por uma operação. |
| `ArtifactTransferReceipt` | Operação de envio/recebimento de Tool, referências exatas, checksum e resultado/estado incerto. |

Esses registros podem ser agrupados em tabelas conforme acesso e transação; não há obrigação de transformar cada value object em uma tabela ou endpoint.

### 5.2. Regras invariantes

1. `Workspace` administrativo da conta e `ArtifactWorkspace` são conceitos distintos. APIs e UI usam nomes que não confundem suas identidades.
2. Workspace pertence a um Project e a um Environment. Compartilhamento implícito entre Draft, Staging e Production é proibido.
3. Identidade externa é opaca e genérica. `student_id`, `study_id` e nomes de produto não são colunas obrigatórias.
4. Nome/caminho é apresentação e organização; bytes são identificados por `artifact_id + revision_id` e hash, não por URL ou nome atual.
5. Renomear/mover um Artifact não muda suas revisões nem invalida referências históricas.
6. Alterar conteúdo cria nova revisão; não sobrescreve o objeto de uma revisão existente.
7. Artefato gerado, extração literal e resumo inferido possuem proveniências distintas. Um resumo não pode aparecer como texto literal do original.
8. Representações e índices referenciam a revisão exata e a receita utilizada; reprocessamento não reescreve conjuntos antigos.
9. Uma Session sem Artifacts continua operando. Vincular um Workspace não carrega todos os arquivos no contexto.
10. Deletar/encerrar uma Session não remove o Workspace compartilhado.
11. Nenhum acesso autorizado no passado garante acesso atual depois de revogação; snapshots preservam identidade de execução, não permissões irrevogáveis.
12. Arquivos legados de Knowledge continuam com comportamento e localizações compatíveis.
13. Não há promessa de exatamente uma chamada a serviços externos. Idempotência local, recibos e estado `uncertain` tratam os limites reais.
14. Nenhum benchmark sintético ou fixture substitui aceitação com os adapters/providers reais anunciados.

---

## 6. Autorização, External Context e continuidade

### 6.1. Seleção não equivale a autorização

O External Context transporta a **seleção** do Workspace. A credencial autenticada e os grants efetivos decidem se essa seleção é permitida. Um `user_id`, `tenant_id` ou `workspace_id` arbitrário não prova identidade.

Acesso efetivo deve ser a interseção de:

```text
Project/Environment do principal
∩ grants atuais da credencial/aplicação
∩ acesso atual ao Artifact Workspace
∩ policy congelada do Agent Release
∩ restrições do Node/delegação, quando houver
∩ restrições da operação, do formato e do destino externo
```

Uma credencial backend da Lipo pode receber acesso a um namespace amplo. Nesse caso, **o backend autenticado da Lipo é responsável por validar qual usuário final solicitou o estudo**. A Woobe valida a delegação técnica, não adivinha o usuário a partir de texto. Para acesso de browser/ChatSurface, usar credencial de sessão já escopada emitida pelo servidor; nunca expor a chave ampla ao cliente.

Estender os mecanismos atuais de Control/Runtime Key com ações/interface de Artifacts. Não exigir uma chave por aluno ou Workspace. Leitura direta por Runtime Key só é permitida quando a interface `artifacts` e os grants correspondentes foram concedidos; não dar acesso administrativo porque a chave consegue executar um Agent.

### 6.2. Exemplo de autoria proposto

O trecho abaixo **é contrato a implementar**, não sintaxe já disponível. Nomes de campo são configuráveis por binding; a Woobe não codifica `study_title` em suas regras.

```yaml
spec:
  external_context:
    artifact_workspace_id:
      required: true
      scope: session
      schema:
        type: string
        minLength: 1
      model:
        expose: false
    study_title:
      required: false
      scope: session
      schema:
        type: string
      model:
        expose: true
  artifacts:
    enabled: true
    workspace_binding:
      source: external_context
      field: artifact_workspace_id
      scope: session
    permissions:
      read: true
      search: true
      write: true
      delete: false
      process: false
      transfer: true
    processing_profile_ref: document-default-v1
    limits:
      max_read_bytes_per_call: 65536
      max_tool_calls_per_run: 24
```

Valores de limites são defaults propostos e configuráveis, não capacidades já medidas. Permissões booleanas ilustram a superfície de autoria; o modelo persistido pode usar ações normalizadas da autoridade existente.

### 6.3. Session, Run e troca de contexto

- **Binding `session`:** resolver uma vez, persistir o vínculo e exigir omissão do campo nas Runs seguintes, conforme o contrato atual. Mudança exige outra Session; não sobrescrever silenciosamente.
- **Binding `run`:** resolver em cada Run. Em Agent stateful, rejeitar troca para outro Workspace quando o histórico contém contexto do anterior; usar nova Session. Não confiar apenas em filtrar Tools, pois o histórico já pode conter dados.
- **Stateless:** pode selecionar outro Workspace na próxima execução, sem carregar conversa anterior; não eliminar a identidade técnica de Session que o runtime já utiliza.
- **Networks:** a Network Session/Run define o binding raiz. Child Agents recebem apenas projeção autorizada; um Node não pode ampliar o acesso da rede nem escolher outro Workspace via argumento de Tool.
- **Sem binding:** Agents que não requerem Artifacts continuam normais; Agents que o exigem falham na Acceptance antes de chamar modelo/Tool.
- **Workspace inexistente:** erro explícito. Não criar implicitamente a partir de um ID enviado no chat.

Para a Lipo: `ENEM em 30 dias` e `Matemática` podem usar dois Workspaces e duas Sessions do mesmo Tutor, sem criar novos Agents ou Projects. A API direta lista exatamente o mesmo catálogo que o runtime autorizado.

### 6.4. Catálogo consistente sem snapshot gigante

Ao aceitar uma Run, registrar uma versão monotônica do catálogo do Workspace. Busca/listagem/leitura dentro dessa Run resolvem revisões visíveis nessa versão e fixam os `SourceRefs` efetivamente utilizados. Manter histórico de ponteiros, caminhos/membership e estado para permitir essa consulta sem copiar milhões de metadados. A publicação de uma nova representação/índice também avança a versão do catálogo; uma Run lê a geração visível no seu corte, não uma geração concluída posteriormente por outra operação. O job solicitado pela própria Run pode devolver uma referência explícita ao novo resultado, sujeita à mesma regra de sobreposição e autorização.

Arquivos gerados pela própria Run são uma sobreposição explícita: ficam acessíveis por referência retornada na escrita e a Nodes autorizados que recebem essa referência. Eles não autorizam a Run a enxergar todas as mudanças concorrentes do Workspace. Essa regra deve ser testada em Runs concorrentes, reattach e retomada.

Snapshots não ignoram exclusão, revogação ou purga. Se uma origem foi removida, reportar indisponibilidade em vez de substituir pela revisão atual.

---

## 7. Armazenamento, uploads e ciclo de vida

### 7.1. Object storage

Reutilizar um contrato genérico com `put/open/stat/delete` e streaming, checksum, tamanho e Range. Adaptar o storage legado de Knowledge por fachada compatível. Não fazer `read()` integral obrigatório de documentos nem bloquear o event loop com SDK síncrono.

Keys físicas devem conter identificadores opacos e segregação de Project/Environment/Workspace; caminhos lógicos não viram caminhos do host. Local storage exige escrita temporária, conclusão atômica, contenção de diretório e proteção contra symlinks. S3 exige multipart quando aplicável e verificação de integridade: **ETag não é tratado como SHA-256**.

Em múltiplas instâncias, filesystem precisa ser volume compartilhado compatível ou execução restrita ao nó que possui os objetos. Disco efêmero por worker não satisfaz disponibilidade distribuída. S3 é o perfil recomendado para replicação de API/Workers, sem reivindicar desempenho antes do ensaio.

### 7.2. Upload e publicação

```text
created → uploading → verifying → committed
                   ↘ failed / aborted / expired
```

Criar intenção com chave idempotente e reserva de quota; transmitir bytes; validar MIME/tamanho/hash; publicar revisão e evento em transação curta. Perda de resposta após `committed` deve recuperar o mesmo recibo. Não repetir upload ou criar revisão nova só porque o ACK foi perdido.

A chave de objeto definitivo não fica reutilizável pelo cliente depois da finalização. URLs de upload apontam para staging controlado; confirmação promove/copia para chave imutável, ou fixa versionamento de objeto equivalente. Verificar hash novamente no boundary de publicação.

Separar **original disponível** de **processamento pronto**. Um PDF pode ser baixado enquanto seus derivados estão na fila. Falha de OCR não deve tornar o upload inexistente.

### 7.3. Concorrência, quotas e remoção

Usar `expected_revision`/ETag lógico nas mutações, reserva transacional de quota e chave idempotente por intenção. Concorrência de upload, rename e write deve produzir conflito explícito, não perda silenciosa.

Arquivamento impede novas escritas/execuções conforme policy. Exclusão lógica revoga acesso e oculta busca; purga física é assíncrona e remove originais, derivados, índices e caches. Reconciliador limpa staging/objetos órfãos após janela configurada, sem apagar objeto ainda ligado a uma publicação válida.

Histórico de Runs preserva recibos e metadados mínimos; não promete leitura de conteúdo que foi expurgado. Backups e restauração devem reaplicar o registro de exclusões para não reexpor documentos removidos. Tokens/URLs temporários nunca são usados como referência durável.

---

## 8. Preparação documental, PageIndex e recuperação

### 8.1. Pipeline configurável

```text
original imutável
 → inspeção de formato/limites
 → extração nativa
 → OCR seletivo quando necessário e disponível
 → documento canônico estruturado
 → Markdown + tabelas/figuras/renderizações + mapa de origem
 → índice estrutural nativo OU adapter PageIndex
 → validação de cobertura/localizadores
 → publicação atômica do conjunto de representações
 → busca/navegação disponíveis
```

A extração ocorre uma vez por revisão/receita, não a cada mensagem. Chave de reuso inclui tenant/Project/Workspace, hash da entrada, versão do parser, modelos/artefatos de OCR, parâmetros, idioma, versão do indexador e modelo de sumarização. Não usar deduplicação global observável entre clientes.

### 8.2. Documento canônico e derivados

Armazenar uma árvore estruturada com blocos e IDs estáveis **dentro da mesma representação**. Cada bloco pode registrar `page_index` físico zero-based, `page_number` de apresentação one-based, rótulo impresso, seção, intervalo de caracteres e bbox quando o extractor realmente fornece essa evidência. Markdown sem páginas usa heading/linhas/offset; não fabricar numeração de páginas.

Derivados mínimos: `content.md`, estrutura JSON, sumário, mapa de fontes, tabelas em representação estruturada quando confiável, figuras e renderizações necessárias. Não é obrigatório materializar cada componente em vários arquivos redundantes: a API pode expor uma visualização lógica sobre os objetos registrados.

Na UI, apresentar o original com seção **Representações** expansível, não despejar dezenas de arquivos internos na raiz do Explorer. Representações publicadas são somente leitura; editar uma cópia cria outro Artifact com proveniência.

Marcar cobertura `complete`, `partial`, `needs_ocr` ou `unsupported`, com páginas/faixas ausentes e motivo verificável. Fórmula ou tabela ilegível deve manter imagem/localização e aviso; não inventar estrutura textual.

### 8.3. Processadores

- Perfil leve: texto/Markdown/JSON/CSV e PDF textual usando bibliotecas selecionadas e fixadas após auditoria das dependências existentes.
- Perfil Docling: conversão de documentos e layout complexo, tabelas/figuras e DOCX; converter `DoclingDocument` para contrato canônico da Woobe, sem expor seus tipos na API pública. O projeto documenta a separação entre documento estruturado e serialização Markdown. [S14, S15]
- Perfil OCR: tratamento seletivo de páginas/imagens que não possuem texto suficiente. Declara idiomas, artefatos/modelos, versão, limite de páginas, memória e tempo. Falta do perfil é erro de capacidade, não sucesso vazio.
- Vision/enriquecimento: análise pelo modelo quando explicitamente autorizada; saída inferida fica separada de transcrição/extração literal.

Parsers não executam macros, scripts ou binários do arquivo. Processamento usa diretório temporário isolado, limites e limpeza. Não permitir que uma receita enviada pelo usuário instale dependências ou execute comandos arbitrários.

### 8.4. PageIndex como adapter, não segundo runtime

O PageIndex atual se descreve como **RAG orientado por raciocínio**, não como ausência de recuperação. Neste plano, o que deixa de ser obrigatório é a cadeia vetorial e a injeção automática legada. A exploração documental continua sendo recuperação fundamentada. [S11, S12]

A documentação consultada distingue o modo local para PDFs textuais de capacidades cloud como OCR visual e organização de pastas; este plano não pressupõe que funções cloud existam no adapter local. A alta cardinalidade e o isolamento serão implementados na Woobe. [S11, S12]

Implementação prevista:

1. Fixar versão/revisão upstream, dependências, licença e fixtures.
2. Preferir o caminho estrutural/local apropriado ao formato; Markdown usa indexador nativo ou função upstream específica validada, não uma chamada fictícia do SDK PDF.
3. Materializar entrada em scratch exclusivo da operação quando o upstream exigir arquivo local.
4. Invocar indexação, converter seus nós para `DocumentIndex/DocumentNode` e validar limites, hierarquia e localização.
5. Invocações de modelo necessárias passam por gateway instrumentado da Woobe, com credenciais/configuração da operação, limite de custo/tokens e cancelamento. Não usar variáveis globais mutáveis com a chave de outro cliente.
6. Quando o upstream não oferecer injeção adequada, integrar apenas o algoritmo estrutural ou um shim mínimo, auditado e atribuído, com porta de modelo explícita. Não criar um cliente LLM paralelo invisível ao runtime.
7. Não utilizar o chat/agente embutido do PageIndex como orquestrador da Woobe. A decisão de navegação pertence ao Agent/ExecutionStrategy existente.
8. PageIndex indisponível ou falho só pode cair para indexador nativo se essa policy foi configurada; a resposta informa qual engine produziu o índice. Nunca chamar fallback de PageIndex concluído.

Não importar promessas de acurácia, custo por página ou escala de benchmarks upstream como metas já comprovadas para a Lipo.

### 8.5. Busca e leitura progressivas

A sequência normal é **descobrir documentos → buscar títulos/termos → abrir árvore parcial → ler nós/páginas → verificar fontes → produzir**. A listagem inicial não injeta o catálogo inteiro no prompt.

Busca textual PostgreSQL com filtros de autorização, versão e Environment é obrigatória. Busca semântica fica como extensão; não exige migração do produto para um servidor externo. Search deve consultar IDs candidatos escopados antes da montagem de resultados, jamais buscar globalmente e filtrar depois.

Retornar cursores, `has_more`, `truncated`, cobertura e razões de corte. Leitura de um nó enorme usa paginação/continuação; não corta a última metade de uma seção sem indicar isso. Resumos orientam navegação; o Agent precisa abrir o conteúdo de origem para fundamentar afirmações.

---

## 9. Contratos propostos de API, runtime e Tools

**Todos os nomes e endpoints novos desta seção são contratos-alvo a implementar.** Compatibilidade e nomes definitivos devem ser congelados na etapa 03 e refletidos no OpenAPI, fixtures, SDKs e CLI.

### 9.1. Famílias de API

| Família | Operações previstas |
|---|---|
| `/v1/artifact-workspaces` | Criar, resolver por chave externa, listar com cursor, obter, atualizar com CAS, arquivar/excluir. |
| `/v1/artifact-workspaces/{id}/artifacts` | Listar diretórios/arquivos, criar entrada, renomear/mover, criar revisão, arquivar/excluir. |
| `/v1/artifact-workspaces/{id}/uploads` | Criar intenção, enviar/retomar partes, consultar estado, finalizar, abortar. |
| `/v1/artifacts/{id}/revisions/{revision_id}` | Metadados e download/Range da revisão exata, sempre validando Workspace e principal. |
| `/v1/artifacts/{id}/processing` | Solicitar processamento de revisão/perfil, consultar etapas e cancelar de forma reconciliada. |
| `/v1/artifacts/{id}/representations` | Listar/ler derivados, gerações e capacidades disponíveis. |
| `/v1/document-indexes/{id}` | Consultar árvore paginada, nós, páginas/localizadores e conteúdo. |
| `/v1/artifact-workspaces/{id}/search` | Catálogo e texto com filtro de versão e resultados limitados. |
| `/v1/source-references/resolve` | Resolver lote limitado de referências para preview/citação, sem ampliar acesso. |

Superfície administrativa project-scoped usa o padrão real de `/ai/projects/{project_id}/...`, consumindo os mesmos casos de uso. Runtime Keys com interface Artifacts não ganham acesso ao control plane. Endpoints de capacidades anunciam formatos, processors, indexers, transferência e limites realmente disponíveis no Environment.

Falhas devem ter código estável, mensagem segura e correlação. Exemplos: `ARTIFACT_ACCESS_DENIED`, `WORKSPACE_BINDING_CONFLICT`, `ARTIFACT_REVISION_CONFLICT`, `UPLOAD_INTEGRITY_MISMATCH`, `PROCESSOR_UNAVAILABLE`, `REPRESENTATION_NOT_READY`, `SOURCE_UNAVAILABLE`, `FILE_TRANSFER_UNSUPPORTED`, `QUOTA_EXCEEDED` e `EXTERNAL_OPERATION_UNCERTAIN`.

### 9.2. Referências tipadas e conteúdo multimodal

```json
{
  "content_parts": [
    {"type": "text", "text": "Explique o capítulo e a figura selecionada."},
    {
      "type": "artifact_ref",
      "artifact_id": "opaque-artifact-id",
      "revision_id": "opaque-revision-id"
    }
  ],
  "options": {
    "external_context": {
      "artifact_workspace_id": "opaque-workspace-id",
      "study_title": "ENEM em 30 dias"
    }
  }
}
```

Exemplo de forma lógica; adaptar o envelope à API atual sem duplicar `options`/bindings internos. Entradas textuais existentes continuam válidas. Se `input` textual e `content_parts` forem fornecidos de forma conflitante, rejeitar em vez de concatenar silenciosamente. Imagem sem texto pode ser válida quando operação/modelo aceitam; string vazia não deve invalidar um resultado de imagem válido.

A menção `@apostila.pdf` é resolvida por autocomplete/serviço de referências para ID e revisão autorizados. Nomes duplicados exigem desambiguação. Uma string digitada à mão não ganha acesso nem faz leitura implícita de arquivo fora do binding.

### 9.3. Fonte e proveniência

```json
{
  "artifact_id": "opaque-artifact-id",
  "revision_id": "opaque-revision-id",
  "representation_set_id": "opaque-set-id",
  "document_index_id": "opaque-index-id",
  "node_id": "node-0042",
  "locator": {"page_index": 11, "page_number": 12, "block_id": "block-83"},
  "source_sha256": "sha256-of-original",
  "excerpt_sha256": "sha256-of-exact-excerpt"
}
```

IDs de nó são únicos no índice, não globalmente entre todas as revisões. `bbox`, linhas ou timestamps só existem quando sustentados pela representação. A API valida referência e alcance; validar estrutura de citação não prova que o texto gerado é semanticamente correto. Essa qualidade é avaliada em testes separados.

### 9.4. Capacidades internas dos Agents

Inventário proposto: `artifacts.list`, `artifacts.inspect`, `artifacts.search`, `documents.outline`, `documents.read`, `artifacts.write` e `artifacts.process`. O modelo recebe apenas operações autorizadas. O Workspace é resolvido pelo runtime; não há um argumento livre para escolher Workspace de outro cliente.

Processamento pesado retorna uma operação acompanhável. Não simular espera/resume genéricos ainda não implementados: o Agent pode consultar um job concluído ou informar pendência e concluir a Run; uma execução posterior pode continuar com os mesmos artefatos. Usar suspensão existente somente onde houver contrato durável já validado.

Proibir ferramenta genérica do tipo `send_file(url_arbitraria, arquivo)`. A exportação ocorre por Tools HTTP/MCP configuradas com bindings de arquivo e autorização do destino.

### 9.5. Ponte externa HTTP/MCP

**HTTP:** mapear `ArtifactRef` para multipart, bytes ou URL temporária restrita conforme contrato. Segredos permanecem no servidor; validar limite de bytes, MIME, destino, redirecionamento e egress antes do envio. Reconhecer resposta binária/estruturada e criar nova revisão/Artifact com proveniência.

**MCP:** uma referência/URI local não é automaticamente legível por servidor remoto. `resource_link` e conteúdo estruturado são formas de resultado do protocolo, não um upload universal. Definir bindings por schema/capabilidade negociada: bytes codificados com limite, URL autorizada, ou upload HTTP prévio previsto pelo servidor. Falta de contrato resulta em `FILE_TRANSFER_UNSUPPORTED`, sem inventar endpoint ou acesso remoto ao filesystem. [S16]

Result files são validados antes da publicação. URLs retornadas só são buscadas em destinos aprovados; não seguir qualquer URL devolvida por documento/Tool. `isError`/erro de aplicação não é sucesso apenas porque o HTTP foi 200.

### 9.6. Eventos e resultados

Adicionar referências de artefatos e fontes a resultados de Run e ao protocolo v2 de streaming, preservando envelope, identidade e ordem. Eventos exemplificativos: `artifact.created`, `artifact.ready`, `artifact.processing.updated` e `artifact.transfer.completed`. Só emitir disponibilidade após publicação durável verificável.

`run.state` deve reconstruir referências e estado atual sem retransmitir os binários. Reattach observa a Run existente e nunca gera imagem de novo nem repete transferência concluída. URLs temporárias são regeneradas após autorização, não persistidas como conteúdo do evento.

Persistência do journal/hot state de Runs permanece a existente da Woobe; não migrar PostgreSQL/Redis/MongoDB nem redefinir Acceptance/Execution/terminalização para entregar Artifacts.

### 9.7. Clientes e distribuição

- **SDK Go:** operações diretas de Workspace/Artifacts com Runtime Key autorizada, streams `io.Reader/io.Writer`, paginação, cancelamento, referências, outputs e recuperação. Preservar o escopo consumer-facing; não importar administração de Agents para o SDK runtime.
- **SDK Python:** mesma semântica e schemas, leitura/escrita em streaming, erros tipados e comportamento lazy das chamadas de chat preservado.
- **CLI:** administração usa Control Key; operação runtime usa Runtime Key explicitamente. Novos comandos não fazem fallback de credenciais nem escondem ação mutante em inspeção.
- **Runtime-client Web:** parser/eventos/types comuns; não executa Runs ou assume responsabilidade do core.
- **Pacotes portáveis de Agents:** exportam configuração de binding/receita/permissões, não apostilas, IDs locais de Workspaces de usuários, tokens ou binários privados por padrão.

---

## 10. Experiência visual e operação

### 10.1. Explorer e leitor

Criar um Explorer project-scoped com filtro/paginação e uma versão contextual em Session/Run. Mostrar Workspace selecionado, permissões efetivas e Environment. Arquivos têm nome, MIME, tamanho, revisão, estado de processamento e origem; detalhes avançados aparecem sob demanda.

O original é o item principal; representações, índice, fontes e histórico são painéis/abas do mesmo recurso. Em desktop, leitor e árvore podem dividir a área; em telas estreitas, usar tabs/drawer alternados. Evitar várias barras laterais comprimindo simultaneamente chat, árvore, preview e configurações.

Composer recebe upload, progresso, falhas recuperáveis e autocomplete `@`. A seleção mostra arquivo/revisão; uma falha de upload não envia referência quebrada. Preview não executa HTML/SVG/script não sanitizado. ChatSurface respeita o mesmo modelo e não apresenta seletor global de Workspaces ao visitante.

### 10.2. Configuração e diagnóstico

Features e dependências têm capabilities explícitas por Environment. Preferir flags graduais para API de Artifacts, processamento, runtime bindings e UI; habilitar UI sem suporte do backend não pode oferecer controles enganosos.

Observabilidade inclui bytes armazenados/transferidos, filas, tempos de parsing/indexação, páginas processadas, cobertura, cache, falhas, uso de modelo e read amplification. Métricas agregadas não usam `user_id` ou `workspace_id` como labels de cardinalidade ilimitada. Traces auditáveis usam IDs sob autorização; não registrar conteúdo privado, chaves, URLs assinadas ou raciocínio privado do modelo.

### 10.3. Reuso na Lipo

Cenário-alvo: backend provisiona um Workspace por jornada, envia originais, acompanha processamento e fornece o ID via External Context. O Tutor e os geradores usam as mesmas capacidades genéricas. A aplicação abre/download os mesmos artefatos pela API e persiste referências de resultados aprovados.

A Woobe não se torna dona do progresso, agenda, avaliações aceitas ou critérios de domínio. O exemplo end-to-end desta entrega será um consumidor de referência com dados sintéticos, sem mudar o repositório Lipo nem exigir uma instância completa dele.

---

## 11. Plano sequencial de implementação — 60 etapas, 60 commits

Todas as etapas herdam as invariantes das seções anteriores. `Áreas` identifica caminhos existentes ou diretórios propostos; confirmar sua localização exata na baseline antes da edição. `Testes` são trabalho a executar, não resultados já obtidos. O critério de conclusão é obrigatório antes de avançar.

### Visão geral da sequência

| Faixa | Foco | Commits |
|---|---|---|
| 01–06 | Fundação, governança e autorização | 6 |
| 07–12 | Storage, uploads e API direta | 6 |
| 13–19 | Processamento documental e derivados | 7 |
| 20–24 | Indexação, busca e leitura verificável | 5 |
| 25–32 | Bindings, Agents, Networks e protocolo de runtime | 8 |
| 33–39 | Tools externas, multimodalidade e exploração fundamentada | 7 |
| 40–45 | SDKs, CLI e contratos de clientes | 6 |
| 46–51 | Explorer, Playground, Network e ChatSurface | 6 |
| 52–60 | Operação, compatibilidade, qualificação e encerramento Draft | 9 |

### Índice dos commits

| Etapa | Entrega | Commit sugerido |
|---|---|---|
| 01 | Congelar baseline, decisões e execução em Draft | `docs(artifacts): freeze baseline and single-draft implementation workflow` |
| 02 | Consolidar fontes de CLI e SDKs no mesmo repositório | `chore(clients): import pinned CLI and SDK sources for atomic delivery` |
| 03 | Criar o boundary Artifacts e os contratos canônicos | `feat(artifacts): establish domain boundary and versioned contracts` |
| 04 | Persistir catálogo, revisões e histórico de visibilidade | `feat(artifacts): persist workspace catalog and immutable revisions` |
| 05 | Integrar autorização e revogação à autoridade existente | `feat(auth): authorize artifact operations through scoped grants` |
| 06 | Provisionar e resolver Workspaces independentes | `feat(artifacts): add idempotent workspace lifecycle and resolution` |
| 07 | Extrair object storage genérico com compatibilidade de Knowledge | `refactor(storage): introduce object storage without breaking knowledge` |
| 08 | Implementar storage local com publicação atômica | `feat(storage): add safe streaming local artifact storage` |
| 09 | Implementar storage S3 e multipart controlado | `feat(storage): add streamed S3 artifact persistence and integrity` |
| 10 | Construir upload retomável e finalização idempotente | `feat(artifacts): implement resumable uploads and durable receipts` |
| 11 | Operar arquivos e diretórios com CAS e proveniência | `feat(artifacts): add file mutations revisions and logical directories` |
| 12 | Expor APIs diretas de Artifacts e downloads autorizados | `feat(api): expose artifact workspace and file operations` |
| 13 | Definir receitas e registro de processamento | `feat(processing): define versioned processor and indexer profiles` |
| 14 | Executar processamento durável nos Workers existentes | `feat(workers): orchestrate durable artifact processing jobs` |
| 15 | Processar formatos textuais com origem preservada | `feat(processing): normalize text markdown JSON and CSV sources` |
| 16 | Extrair PDFs textuais e preservar páginas | `feat(processing): extract PDF text with page-level provenance` |
| 17 | Adicionar Docling como perfil opcional de extração | `feat(processing): integrate optional Docling document conversion` |
| 18 | Adicionar OCR seletivo e cobertura visual | `feat(processing): add selective OCR and visual coverage diagnostics` |
| 19 | Publicar derivados e mapa de fontes atomicamente | `feat(artifacts): publish coherent representation sets and source maps` |
| 20 | Construir índice hierárquico nativo | `feat(indexing): build versioned structural document trees` |
| 21 | Instrumentar enriquecimento por modelo no processamento | `feat(processing): govern model-assisted indexing through runtime ports` |
| 22 | Integrar PageIndex local como indexador substituível | `feat(indexing): add a pinned local PageIndex adapter` |
| 23 | Implementar busca textual e descoberta de documentos | `feat(search): add scoped workspace and document text retrieval` |
| 24 | Expor navegação, leitura e resolução de fontes | `feat(api): expose document outlines bounded reads and citations` |
| 25 | Versionar bindings e permissões nas definições de Agents | `feat(agent): version artifact bindings and runtime policies` |
| 26 | Resolver Workspace na Acceptance pelo External Context | `feat(runtime): bind authorized workspaces through external context` |
| 27 | Propagar escopo e permissões dentro de Networks | `feat(network): constrain artifact access per node and child run` |
| 28 | Congelar fontes utilizadas sem copiar o Workspace inteiro | `feat(runtime): pin artifact source manifests to run catalog versions` |
| 29 | Aceitar mensagens com partes e referências tipadas | `feat(runtime): add backward-compatible multimodal content parts` |
| 30 | Disponibilizar capacidades internas de navegação e escrita | `feat(agent): expose governed artifact and document tools` |
| 31 | Controlar orçamento de leitura e montagem de contexto | `feat(context): budget artifact exploration and preserve source fidelity` |
| 32 | Persistir artefatos de saída e projetá-los no streaming | `feat(runtime): persist artifact outputs and resumable stream projections` |
| 33 | Transferir arquivos por Tools HTTP configuradas | `feat(tools): bind artifact inputs to authorized HTTP transfers` |
| 34 | Transferir arquivos por MCP conforme o contrato negociado | `feat(mcp): support schema-bound artifact transfer and resource results` |
| 35 | Ingerir outputs externos e reconciliar operações demoradas | `feat(artifacts): ingest external tool outputs with durable provenance` |
| 36 | Executar entrada visual sobre referências autorizadas | `feat(models): resolve artifact images for vision-capable providers` |
| 37 | Executar geração de imagem com output persistente | `feat(models): generate images into artifact workspaces` |
| 38 | Tornar recuperação legada opcional sem quebrar Releases | `feat(knowledge): allow artifact-only agents with legacy RAG compatibility` |
| 39 | Criar Skill de exploração documental fundamentada | `feat(skills): add bounded evidence-based document exploration` |
| 40 | Ampliar SDK Go para acesso direto aos Workspaces | `feat(sdk-go): add workspace artifact and processing clients` |
| 41 | Ampliar SDK Go para multimodalidade e eventos | `feat(sdk-go): support artifact-aware runs and stream recovery` |
| 42 | Entregar paridade no SDK Python | `feat(sdk-python): add artifact workspaces multimodal parts and receipts` |
| 43 | Operar Artifacts pela CLI | `feat(cli): add workspace artifact upload and document commands` |
| 44 | Atualizar autoria CLI, pacotes e skill de desenvolvimento | `feat(cli): author artifact bindings and multimodal runtime manifests` |
| 45 | Estender o runtime-client compartilhado do navegador | `feat(runtime-client): decode artifact content and stream state` |
| 46 | Criar Explorer de Workspaces e arquivos | `feat(ui): add paginated artifact workspace explorer` |
| 47 | Criar leitor documental com árvore e fontes | `feat(ui): add document reader with hierarchy and source provenance` |
| 48 | Configurar Artifacts nos editores de Agent e Network | `feat(ui): configure artifact bindings profiles and permissions` |
| 49 | Integrar upload, menções e resultados no Playground | `feat(ui): add artifact mentions attachments and output previews` |
| 50 | Integrar Explorer e artefatos ao fluxo visual de Networks | `feat(ui): expose network artifact scope and node outputs` |
| 51 | Entregar paridade no ChatSurface/Embed | `feat(embed): add scoped artifact conversations and downloads` |
| 52 | Instrumentar operações, custos e auditoria passiva | `feat(observability): trace artifact processing retrieval and transfer` |
| 53 | Empacotar perfis de execução e capacidades opcionais | `chore(deploy): add optional document worker profiles and capability probes` |
| 54 | Preparar upgrade e rollback compatíveis | `feat(compat): preserve legacy runtime and package contracts during rollout` |
| 55 | Validar dois acessos com consumidor de referência | `test(integration): qualify direct and agentic workspace access end to end` |
| 56 | Concluir retenção, purga, exportação e restauração | `feat(operations): manage artifact retention garbage collection and restore` |
| 57 | Ensaiar alta cardinalidade, concorrência e falhas | `perf(artifacts): qualify scale bounds backpressure and recovery` |
| 58 | Avaliar qualidade de recuperação e geração fundamentada | `test(retrieval): benchmark hierarchical navigation and grounded outputs` |
| 59 | Concluir documentação operacional, APIs e guias de clientes | `docs(artifacts): publish developer integration and operations guides` |
| 60 | Auditar a entrega e encerrar mantendo o PR em Draft | `chore(artifacts): finalize acceptance evidence and retain draft status` |


### Bloco 01–06 — Fundação, governança e autorização

#### Etapa 01 — Congelar baseline, decisões e execução em Draft

**Commit único:** `docs(artifacts): freeze baseline and single-draft implementation workflow`  
**Trailer:** `Plan-Step: 01/60`  
**Dependências:** Nenhuma; etapa inicial.

**Objetivo.** Tornar o escopo executável e auditável antes de adicionar comportamento ao produto.

**Áreas.** `docs/implementation/artifacts/`, `docs/adr/`, guards de CI e convenções existentes de contribuição.

**Implementação detalhada:**

1. Inspecionar master, código local, PR #219, workers, migrations, APIs, pacotes e contratos dos clientes; registrar SHA-base e desvios entre documentação e implementação.
2. Criar ADR com Workspace independente, módulo artifacts, seleção por External Context, PageIndex opcional, preservação dos originais e exclusão dos serviços que não fazem parte do escopo.
3. Criar branch, ledger das 60 etapas, inventário de dependências e mapa de ownership; abrir o único PR como Draft após este primeiro commit de conteúdo.
4. Definir gates e trailers de commit; configurar verificação de draft/ausência de publicação sem alterar PRs existentes. Fixar os códigos e nomes propostos que ainda dependem do inventário.

**Testes e evidências a produzir:**

- Executar a seleção oficial de baseline disponível; classificar separadamente falhas preexistentes, indisponibilidade de ambiente e testes executados.
- Validar que a branch tem uma única origem, o PR é draft=true e a guarda não concede permissões de merge/publicação.
- Conferir que nenhuma regra depende de tipos pedagógicos e que os 60 IDs de etapa são únicos.

**Critério de conclusão.** Baseline, ADR e ledger versionados; primeiro commit criado; novo PR aberto em Draft, sem tocar no #219.

---
#### Etapa 02 — Consolidar fontes de CLI e SDKs no mesmo repositório

**Commit único:** `chore(clients): import pinned CLI and SDK sources for atomic delivery`  
**Trailer:** `Plan-Step: 02/60`  
**Dependências:** 01

**Objetivo.** Permitir alterações efetivas nos clientes dentro do único PR, preservando sua distribuição independente.

**Áreas.** `clients/woobe-cli/`, `clients/woobe-sdk-go/`, `clients/woobe-sdk-python/`, `go.work`, build/test do monorepo.

**Implementação detalhada:**

1. Consultar e registrar os SHAs reais dos três repositórios de origem; importar snapshots sem histórico adicional, credenciais, caches, binaries ou diretórios privados.
2. Preservar licenças, module paths, imports e nomes publicados; adicionar manifesto de origem/hash e documentação de que fontes locais são canônicas nesta entrega.
3. Ligar CLI ao SDK Go local por go.work; permitir testes standalone do SDK com GOWORK=off e builds da CLI no workspace de integração.
4. Transportar checks úteis dos clientes para o CI principal; manter workflows de release dos snapshots inertes e não configurar mirrors automáticos.

**Testes e evidências a produzir:**

- Compilar/testar clientes importados sem mudança funcional e comparar seus contratos com as versões de origem.
- Confirmar que nenhum workflow em subdiretórios publica pacotes e que o build não baixa silenciosamente um SDK Go remoto antigo.
- Validar licenças/atribuições, ausência de segredos e reprodutibilidade da importação pelo manifesto.

**Critério de conclusão.** Três clientes compiláveis na árvore canônica, sem commits externos e sem mudança de versão/publicação.

---
#### Etapa 03 — Criar o boundary Artifacts e os contratos canônicos

**Commit único:** `feat(artifacts): establish domain boundary and versioned contracts`  
**Trailer:** `Plan-Step: 03/60`  
**Dependências:** 01, 02

**Objetivo.** Criar a unidade modular única com interfaces testáveis e schema público coerente.

**Áreas.** `modules/artifacts/{domain,application,presentation,composition}`, entrypoints, `contracts/artifacts/v1/`, quality gates.

**Implementação detalhada:**

1. Definir entidades/value objects de Workspace, Artifact, Revision, SourceRef, uploads, representations, índice e jobs com IDs opacos e estados válidos.
2. Criar portas ArtifactGateway, ObjectStorage, Authorizer, Processor, Indexer, Scheduler e ModelGateway, sem dependência do HTTP host ou dos tipos de PageIndex/Docling.
3. Congelar schemas de request/response, referências, erro, cursor e capabilities; adicionar fixtures positivas e negativas reutilizadas por Python, Go e TypeScript.
4. Registrar entrypoint e background_boundary no verificador de arquitetura; construir testes de contrato e doubles explícitos, sem simular comportamento produtivo como pronto.

**Testes e evidências a produzir:**

- Testar invariantes de domínio, serialização, IDs, versões de schema e rejeição de combinações inválidas.
- Executar guards de imports para impedir Core→API/Workers/tooling e application→infra.
- Validar schemas com campos desconhecidos e evolução aditiva planejada.

**Critério de conclusão.** Módulo e contratos testados; nenhuma dependência externa pesada obrigatória no import do core.

---
#### Etapa 04 — Persistir catálogo, revisões e histórico de visibilidade

**Commit único:** `feat(artifacts): persist workspace catalog and immutable revisions`  
**Trailer:** `Plan-Step: 04/60`  
**Dependências:** 03

**Objetivo.** Garantir identidade durável e consultas versionadas antes de escrever bytes.

**Áreas.** `modules/artifacts/infra/database/`, repositórios e migrations de `woobe-core`.

**Implementação detalhada:**

1. Criar migrations aditivas para Workspaces, artefatos, revisões, intents, grants e registros de catálogo necessários; usar schema/nomes consistentes com a baseline.
2. Adicionar unicidade por Project/Environment/namespace/chave externa e por caminho normalizado dentro do Workspace; não usar nome do aluno como chave física.
3. Manter versão monotônica do catálogo e histórico dos ponteiros de revisão, permitindo consultas as_of_catalog_version sem copiar todo o inventário por Run.
4. Implementar repositórios com índices e filtros por scope em todas as consultas; definir transações curtas e FKs que não apaguem Workspaces ao excluir Sessions.

**Testes e evidências a produzir:**

- Aplicar migrations em banco vazio e sobre baseline populada; verificar migração repetível via ledger e leitura dos dados anteriores.
- Testar unicidade, rollback de transação, concorrência de revisões e query de catálogo histórico.
- Inspecionar planos SQL para listagem paginada e busca por namespace sem full scan desnecessário.

**Critério de conclusão.** Metadados duráveis, consultas escopadas e seleção histórica comprovados em PostgreSQL real.

---
#### Etapa 05 — Integrar autorização e revogação à autoridade existente

**Commit único:** `feat(auth): authorize artifact operations through scoped grants`  
**Trailer:** `Plan-Step: 05/60`  
**Dependências:** 03, 04

**Objetivo.** Aplicar a mesma decisão de acesso a API direta, runtime, jobs e transferência.

**Áreas.** Artifacts Authorizer, catálogo de operações de Identity/Core, Runtime Keys, HTTP guard e permissões de Environment.

**Implementação detalhada:**

1. Adicionar ações de Artifacts e interface de Runtime Key sem criar um sistema independente de usuários/segredos.
2. Definir grants por Workspace ou namespace autorizado, negação por padrão, revisão de revogação, validade e escopo de Environment.
3. Implementar interseção principal→grant→Workspace→Release→Node e verificações por operação; tornar a verificação reutilizável pelos workers e pelos downloads.
4. Distinguir backend com delegação ampla de sessão browser restrita; impedir que identificadores em External Context, nomes de arquivo ou argumentos de Tool concedam acesso.

**Testes e evidências a produzir:**

- Matriz de principal/ação/Project/Environment/Workspace, inclusive acesso cruzado, grants expirados e Runtime Key sem interface artifacts.
- Revogação entre admission, leitura, transferência e publicação; resposta não deve revelar existência de recurso alheio.
- Confirmar que Control Key e Runtime Key mantêm identidades e responsabilidades distintas.

**Critério de conclusão.** Todas as superfícies usam o mesmo authorizer e nenhuma concede acesso apenas por conhecer um ID.

---
#### Etapa 06 — Provisionar e resolver Workspaces independentes

**Commit único:** `feat(artifacts): add idempotent workspace lifecycle and resolution`  
**Trailer:** `Plan-Step: 06/60`  
**Dependências:** 04, 05

**Objetivo.** Permitir a aplicações gerenciar muitos Workspaces antes e independentemente de conversas.

**Áreas.** Casos de uso de Workspace, repositories, contratos de resolução e policy de quota/retention.

**Implementação detalhada:**

1. Implementar criação idempotente, resolução por external_namespace/external_key, leitura, paginação, atualização CAS e arquivamento.
2. Fixar Project, Environment e storage profile na criação; mudanças de storage exigem procedimento explícito, não edição de string sem migração.
3. Guardar labels/contexto amigável como metadados, sem entidades educacionais e sem uma pasta/bucket físico por usuário.
4. Definir estado deletion_pending e bloqueio de novas escritas; a remoção física será executada pelo lifecycle da etapa 56.

**Testes e evidências a produzir:**

- Duas criações concorrentes da mesma identidade externa recuperam o mesmo Workspace ou conflito de payload, não duplicatas.
- Múltiplos usuários/projetos com nomes iguais continuam isolados; cursores não podem ser reutilizados em outro escopo.
- Workspace sobrevive ao encerramento de Sessions e pode existir sem Run.

**Critério de conclusão.** CRUD/resolução de Workspaces utilizáveis sem Agent, com CAS, isolamento e paginação reais.

---

### Bloco 07–12 — Storage, uploads e API direta

#### Etapa 07 — Extrair object storage genérico com compatibilidade de Knowledge

**Commit único:** `refactor(storage): introduce object storage without breaking knowledge`  
**Trailer:** `Plan-Step: 07/60`  
**Dependências:** 03, 04

**Objetivo.** Reutilizar a infraestrutura de arquivos sem acoplar Artifacts ao domínio de Collections.

**Áreas.** Porta genérica de object storage em boundary compartilhado apropriado, adapters legados de Knowledge e composição.

**Implementação detalhada:**

1. Inventariar save/open/delete existentes e estabelecer contrato streaming, metadata, checksum e Range sem exigir IDs de Collection.
2. Criar facade compatível para os chamadores de Knowledge; manter keys físicas, hashes e semântica de documentos existentes.
3. Centralizar erros de transporte, contenção de diretório, size accounting e limites; evitar copiar dois stacks de storage.
4. Se o contrato compartilhado exigir mudança de quality-gate, declarar a dependência estreita e não permitir import direto entre implementações de bounded contexts.

**Testes e evidências a produzir:**

- Rodar regressões de Knowledge, export/import, snapshots e documentos legados.
- Testes de conformidade da porta com streams pequenos/grandes, zero bytes quando permitido e encerramento antecipado.
- Comparar keys/metadados antes e depois; nenhuma migração de binários implícita.

**Critério de conclusão.** ObjectStorage genérico funcional e todos os consumidores legados preservados.

---
#### Etapa 08 — Implementar storage local com publicação atômica

**Commit único:** `feat(storage): add safe streaming local artifact storage`  
**Trailer:** `Plan-Step: 08/60`  
**Dependências:** 07

**Objetivo.** Disponibilizar o perfil local com integridade e sem exposição do filesystem do servidor.

**Áreas.** Adapter LocalStorage, configuração de diretórios/volumes e testes de filesystem.

**Implementação detalhada:**

1. Escrever em staging exclusivo com streaming e hash incremental; promover apenas após validação e fechamento do handle.
2. Derivar paths físicos de IDs opacos e conter todas as operações na raiz; negar traversal, symlinks, escapes, nomes reservados e normalizações ambíguas.
3. Implementar leitura por range, stat e delete idempotente; diferenciar objeto ausente de erro de permissão/disco.
4. Definir isolamento de scratch por job, remoção de temporários e requisito explícito de volume compartilhado no modo multi-instância.

**Testes e evidências a produzir:**

- Testar crash durante escrita, disco cheio, stream interrompido, hash divergente e tentativa de ler staging não publicado.
- Testar symlink/traversal/Unicode e Range inválido sem abrir arquivos externos.
- Medir memória durante upload para comprovar ausência de buffer integral obrigatório.

**Critério de conclusão.** Arquivos locais íntegros e endereçáveis por revisão, sem acesso a paths arbitrários do host.

---
#### Etapa 09 — Implementar storage S3 e multipart controlado

**Commit único:** `feat(storage): add streamed S3 artifact persistence and integrity`  
**Trailer:** `Plan-Step: 09/60`  
**Dependências:** 07, 08

**Objetivo.** Suportar API e Workers replicados sem dependência de disco local permanente.

**Áreas.** Adapter S3-compatible, storage profile, client lifecycle e test fixtures de object store.

**Implementação detalhada:**

1. Implementar upload/read/delete em streaming e multipart com limite de concorrência; reutilizar configuração/credential chain aprovada.
2. Distinguir staging de keys imutáveis; verificar tamanho e SHA-256 sem assumir equivalência do ETag.
3. Persistir somente referências de storage e versão quando aplicável; nunca salvar credenciais/URLs temporárias no catálogo.
4. Abortar multiparts expirados e tratar timeouts, objeto já existente e resposta perdida; aplicar limites reais de cada adapter, sem anunciar recursos não suportados.

**Testes e evidências a produzir:**

- Suite contra S3-compatible real, cobrindo multipart, Range, abort, checksum e retry de read seguro.
- Falha antes/depois da conclusão e reconciliação por metadata/hash sem duplicar publicação.
- Executar teste AWS apenas se ambiente autorizado existir; distinguir isso do teste de compatibilidade local.

**Critério de conclusão.** Storage S3 funcional com integridade e recuperação; credenciais permanecem exclusivamente no servidor.

---
#### Etapa 10 — Construir upload retomável e finalização idempotente

**Commit único:** `feat(artifacts): implement resumable uploads and durable receipts`  
**Trailer:** `Plan-Step: 10/60`  
**Dependências:** 05, 06, 08, 09

**Objetivo.** Permitir uploads grandes e recuperação de ACK perdido sem duplicar artefatos.

**Áreas.** UploadIntent, reserva de quota, serviços de finalização, repositories e port de upload.

**Implementação detalhada:**

1. Implementar intenção com fingerprint do request, bytes esperados, hash, tipo, artefato/revisão alvo e chave idempotente.
2. Permitir envio proxy e retomada por partes/offset contratados; disponibilizar URL temporária apenas onde o adapter e a autorização permitirem.
3. Validar MIME efetivo, tamanho, checksum e versão esperada; publicar revision+recibo+evento em transação curta após objeto verificável.
4. Impedir alteração do objeto final por uma URL de staging ainda válida; reconciliar cancelamento/expiração com confirmação concorrente.

**Testes e evidências a produzir:**

- Retry da mesma intenção, mesmo ID com outro payload, queda de rede, offset divergente e ACK perdido após publicação.
- Upload concorrente disputando quota e mesma revisão; garantir reserva/liberação exatas.
- Retomada por outro principal/Workspace negada, inclusive em consultas de status.

**Critério de conclusão.** Upload interrompido é recuperável e confirmação repetida retorna a mesma revisão e recibo.

---
#### Etapa 11 — Operar arquivos e diretórios com CAS e proveniência

**Commit único:** `feat(artifacts): add file mutations revisions and logical directories`  
**Trailer:** `Plan-Step: 11/60`  
**Dependências:** 04, 05, 06, 10

**Objetivo.** Completar as operações do catálogo usadas pela aplicação e pelos Agents.

**Áreas.** Casos de uso de Artifact, normalização de paths, diretórios lógicos, revisions e lineage.

**Implementação detalhada:**

1. Implementar criação/escrita de texto, nova revisão, rename, move, listagem por diretório e exclusão lógica, sempre com autorização e CAS.
2. Conservar artifact_id após rename/move; evitar aliases ambíguos entre arquivo e diretório e manter índices de caminho atualizados.
3. Registrar origem upload/Agent/Tool/processing e IDs de operação, Run/Node quando existirem; APIs diretas não inventam Run.
4. Converter escrita de Agent em publicação idempotente por operation_id; resultados repetidos não criam novas revisões acidentalmente.

**Testes e evidências a produzir:**

- Corridas de write/rename/delete, colisões de nome, diretório não vazio e leitura histórica após mudança de caminho.
- Criar arquivo por API e lê-lo pela facade runtime com os mesmos bytes/hash.
- Negar escrita em representações imutáveis; cópia editável deve ser novo Artifact.

**Critério de conclusão.** Catálogo operacional completo, sem sobrescrita silenciosa e com origem rastreável.

---
#### Etapa 12 — Expor APIs diretas de Artifacts e downloads autorizados

**Commit único:** `feat(api): expose artifact workspace and file operations`  
**Trailer:** `Plan-Step: 12/60`  
**Dependências:** 05, 06, 10, 11

**Objetivo.** Entregar o primeiro fluxo completo aplicação→Workspace→arquivo, sem executar Agent.

**Áreas.** `woobe-api/http/artifacts`, DTOs/OpenAPI, Runtime Key interface, handlers administrativos e capabilities.

**Implementação detalhada:**

1. Implementar famílias Workspace/Artifact/Upload/download pela fachada; routers não abrem banco nem instanciam repositories.
2. Suportar paginação keyset, filtros bounded, idempotency keys, CAS, códigos de erro e capability discovery.
3. Servir Range e Content-Disposition seguro; emitir download proxy ou URL temporária curta apenas após autorização, sem persisti-la como referência.
4. Usar URLs proxy revogáveis para contextos browser sensíveis; documentar que URL S3 assinada já entregue permanece válida até expirar, sem prometer revogação instantânea impossível.

**Testes e evidências a produzir:**

- HTTP end-to-end com PostgreSQL e ambos os storages: provisionar, enviar, listar, baixar, renomear e consultar revisão.
- Matriz de Control/Runtime Key, escopos cruzados, ausência de interface, cursor adulterado e range inválido.
- Confirmar headers/cache/CORS e que logout/revogação bloqueiam novas resoluções de download.

**Critério de conclusão.** Aplicação externa consegue operar arquivos com API real e sem depender de Session/Run.

---

### Bloco 13–19 — Processamento documental e derivados

#### Etapa 13 — Definir receitas e registro de processamento

**Commit único:** `feat(processing): define versioned processor and indexer profiles`  
**Trailer:** `Plan-Step: 13/60`  
**Dependências:** 03, 04, 12

**Objetivo.** Transformar processamento em capacidade configurável e reproduzível, não em lógica fixa do upload.

**Áreas.** ProcessingProfileRevision, registry de processors/indexers, contracts de capabilities e configuração de Environment.

**Implementação detalhada:**

1. Definir entradas/saídas, formatos, limites de bytes/páginas/tempo e capacidades de cada processor/indexer; separar extração, OCR, sumarização e indexação.
2. Persistir receitas imutáveis com versões de bibliotecas/modelos, parâmetros e referências seguras de configuração; não armazenar secrets no perfil.
3. Implementar seleção explícita e default por Workspace/policy, incluindo opção de armazenar sem processar e reprocessar manualmente.
4. Calcular fingerprint de processamento e declarar estados/cobertura; formats unsupported não aparecem como ready.

**Testes e evidências a produzir:**

- Validação de receita inválida, perfil inexistente, limite incompatível e dependência opcional ausente.
- Mesmos bytes+mesma receita produzem identidade de reuso; mudar parser/modelo/parâmetro invalida o cache.
- Criar/importar configuração sem executar parser, instalar modelo ou chamar provider.

**Critério de conclusão.** Perfis versionados e capabilities verificáveis, sem acoplar upload a uma biblioteca específica.

---
#### Etapa 14 — Executar processamento durável nos Workers existentes

**Commit único:** `feat(workers): orchestrate durable artifact processing jobs`  
**Trailer:** `Plan-Step: 14/60`  
**Dependências:** 04, 05, 13

**Objetivo.** Processar documentos fora de requests HTTP com retomada e publicação protegida.

**Áreas.** ProcessingJob, outbox/inbox existentes, background boundary e consumidores de `woobe-workers`.

**Implementação detalhada:**

1. Persistir request e outbox juntos; consumir com lease, heartbeat, fencing token e checkpoints por etapa. Identidade de job é estável; tentativas são separadas.
2. Definir queued/running/succeeded/failed/cancel_requested/cancelled/uncertain e tratar terminalização concorrente sem afirmar cancelamento não confirmado.
3. Revalidar autorização/configuração antes de I/O e antes de publicar; limitar jobs por Workspace/Project para evitar monopólio da fila.
4. Expor status e cancelamento de ProcessingJob sem habilitar Runtime Jobs genéricos ou introduzir um novo scheduler do produto.

**Testes e evidências a produzir:**

- Crash antes/depois de checkpoint, redelivery, lease vencida, worker antigo tentando publicar e fila reiniciada.
- ACK perdido após conclusão recupera resultado original; retry não repete etapas de extração já duráveis.
- Cancelamento durante I/O, revogação de acesso e erro permanente não entram em loop de retry ilimitado.

**Critério de conclusão.** Jobs retomam por tentativa autorizada e apenas o dono atual do lease publica resultados.

---
#### Etapa 15 — Processar formatos textuais com origem preservada

**Commit único:** `feat(processing): normalize text markdown JSON and CSV sources`  
**Trailer:** `Plan-Step: 15/60`  
**Dependências:** 13, 14

**Objetivo.** Entregar um caminho documental leve, determinístico e sem chamadas ao modelo.

**Áreas.** Processors nativos, contrato de documento canônico, fixtures de idioma/encoding e detecção MIME.

**Implementação detalhada:**

1. Normalizar TXT e Markdown com estrutura de headings, listas, blocos de código e offsets; preservar conteúdo original em sua revisão.
2. Preservar JSON como dados estruturados e CSV com colunas/linhas e limites; não inventar capítulos sem evidência.
3. Gerar bloco IDs e mapeamento para linhas/offset de origem, distinguindo bytes, Unicode e finais de linha; não fabricar páginas para texto simples.
4. Tratar encoding inválido, documento vazio, limites e conteúdo que parece instrução como dado não confiável, nunca instrução de sistema.

**Testes e evidências a produzir:**

- Fixtures em português com acentos, Unicode, CRLF/LF, headings repetidos, código contendo marcadores e tabelas vazias.
- Comparar extração e locators contra golden files; read por range deve apontar ao trecho correto.
- Assegurar que parsing não executa scripts, HTML ou referências remotas embutidas.

**Critério de conclusão.** Formatos textuais geram estrutura e fontes verificáveis sem custo de modelo.

---
#### Etapa 16 — Extrair PDFs textuais e preservar páginas

**Commit único:** `feat(processing): extract PDF text with page-level provenance`  
**Trailer:** `Plan-Step: 16/60`  
**Dependências:** 13, 14, 15

**Objetivo.** Preparar apostilas textuais com paginação rastreável e diagnóstico de cobertura.

**Áreas.** PDF processor nativo, renderer seguro, metadata de páginas e fixtures PDF sintéticas licenciadas.

**Implementação detalhada:**

1. Escolher/reutilizar parser adequado após auditoria de dependências; extrair texto por página e mapear índice físico, número de apresentação e rótulo impresso.
2. Detectar páginas sem texto, ordem de leitura degradada e necessidade de OCR; não marcar documento inteiro como completamente extraído quando partes faltam.
3. Preservar original e oferecer renderização controlada para consulta visual; aplicar limites de resolução, páginas, memória e tempo.
4. Identificar PDFs protegidos/corrompidos e retornar erro/cobertura precisos sem travar o worker ou inserir texto vazio como sucesso.

**Testes e evidências a produzir:**

- PDFs com sumário, numeração romana, duas colunas, páginas vazias, capítulos que atravessam páginas e fonte com ligaturas.
- Testar PDF protegido/corrompido, arquivo que não é PDF apesar da extensão e renderização cancelada.
- Conferir que referências à página 12 abrem a página física correta, sem off-by-one.

**Critério de conclusão.** PDF textual navegável e páginas sem conteúdo extraído claramente identificadas.

---
#### Etapa 17 — Adicionar Docling como perfil opcional de extração

**Commit único:** `feat(processing): integrate optional Docling document conversion`  
**Trailer:** `Plan-Step: 17/60`  
**Dependências:** 13, 14, 16

**Objetivo.** Ampliar qualidade estrutural de PDFs complexos e documentos Office sem mudar o contrato público.

**Áreas.** Adapter Docling, extras/imagem de processamento e tradutor para documento canônico.

**Implementação detalhada:**

1. Fixar versões e dependências, conferir licenças de bibliotecas/modelos e disponibilizar aquisição de pesos controlada por manifesto.
2. Converter DoclingDocument para blocos, hierarquia, tabelas, figuras e locators da Woobe; manter JSON de origem como evidência interna quando apropriado.
3. Habilitar DOCX e PDFs de layout complexo conforme suporte efetivamente testado; desabilitar execução de macros e acesso remoto implícito.
4. Evitar import pesado na API; executar em perfil de Workers com memória/CPU configuradas e diretório temporário exclusivo.

**Testes e evidências a produzir:**

- Integração real da biblioteca com fixtures de PDF multicoluna, DOCX, tabela e figura, não apenas mock do adapter.
- Golden checks de estrutura/localização e marcação de extração parcial; não exigir igualdade byte a byte de resultados inferidos.
- Iniciar API/Core sem extra Docling e comprovar erro de capability ao solicitar esse perfil indisponível.

**Critério de conclusão.** Docling funciona como adapter opcional e produz o mesmo contrato canônico utilizado pelos demais processors.

---
#### Etapa 18 — Adicionar OCR seletivo e cobertura visual

**Commit único:** `feat(processing): add selective OCR and visual coverage diagnostics`  
**Trailer:** `Plan-Step: 18/60`  
**Dependências:** 14, 16, 17

**Objetivo.** Tratar PDFs escaneados e imagens sem confundir OCR com compreensão visual completa.

**Áreas.** Perfil OCR, detecção de páginas, modelos/idiomas e assets de renderização.

**Implementação detalhada:**

1. Executar OCR apenas nas páginas/imagens elegíveis segundo receita; conservar texto nativo quando válido e impedir duplicação de blocos.
2. Registrar engine, versão, idiomas e cobertura; usar confiança do provider quando existente, sem fabricar uma métrica de certeza.
3. Preservar imagem/renderização para tabelas, fórmulas ou texto não reconhecido; permitir consulta posterior por modelo visual autorizado.
4. Aplicar limites de pixels/páginas e isolamento de processo; cancelar com reconciliação e limpar temporários.

**Testes e evidências a produzir:**

- Executar OCR real em fixtures locais de português, páginas híbridas, rotação e baixa qualidade conhecida.
- Verificar que não ter modelo/idioma instalado produz diagnóstico e não ready vazio.
- Testar recuperação de job, interrupção, limite de recursos e ligação do texto reconhecido à página/imagem original.

**Critério de conclusão.** Conteúdo escaneado tem caminho executável e cobertura honesta; OCR não é anunciado como análise completa de figuras.

---
#### Etapa 19 — Publicar derivados e mapa de fontes atomicamente

**Commit único:** `feat(artifacts): publish coherent representation sets and source maps`  
**Trailer:** `Plan-Step: 19/60`  
**Dependências:** 14, 15, 16, 17, 18

**Objetivo.** Tornar derivados reutilizáveis e citáveis sem apresentar bundles incompletos como prontos.

**Áreas.** RepresentationSet/ArtifactRepresentation, SourceRef, storage staging e publication use case.

**Implementação detalhada:**

1. Criar Markdown, estrutura, outline, tabelas, figuras e referências como um conjunto com manifesto/hash e entradas read-only.
2. Validar a coerência do bundle e publicar o ponteiro ready em transação única após objetos verificáveis; jobs antigos não substituem geração mais recente.
3. Associar derivados à revisão original e à receita, distinguindo extração literal, OCR e enriquecimento inferido.
4. Expor original+Representações como visão lógica; editar um derivado cria novo Artifact e mantém lineage, não altera o bundle histórico.

**Testes e evidências a produzir:**

- Falha ao produzir uma figura, objeto ausente, manifesto inconsistente e worker concorrente com fencing inválido.
- Atualizar original durante processamento: resultado antigo continua ligado à revisão antiga e não aparece como processamento da nova.
- Read de SourceRef valida checksum, revisão, bloco/página e autorização atuais.

**Critério de conclusão.** Cada bundle pronto é coerente, rastreável e independente do estado atual do arquivo original.

---

### Bloco 20–24 — Indexação, busca e leitura verificável

#### Etapa 20 — Construir índice hierárquico nativo

**Commit único:** `feat(indexing): build versioned structural document trees`  
**Trailer:** `Plan-Step: 20/60`  
**Dependências:** 13, 19

**Objetivo.** Fornecer navegação por capítulos e seções mesmo sem PageIndex ou provider de modelo.

**Áreas.** DocumentIndex/DocumentNode, structural indexer e validação de árvore.

**Implementação detalhada:**

1. Construir árvore a partir da estrutura canônica e headings, preservando seções, relações pai/filho e ranges de origem.
2. Definir IDs estáveis dentro de um index_id e limites de profundidade/nós; permitir paginação da árvore e leitura de folhas grandes.
3. Usar fallback estrutural por páginas/blocos quando o documento não tiver sumário confiável, explicitando o tipo de árvore gerada.
4. Registrar engine/versão/receita, cobertura e manifesto; índices não armazenam cópias divergentes do texto como nova fonte de verdade.

**Testes e evidências a produzir:**

- Árvores com headings repetidos, níveis faltantes, seções longas, documento sem capítulos e caracteres não latinos.
- Rejeitar ciclos, referências fora de range, árvore vazia indevida e nós sem origem verificável.
- Testar reprocessamento gerando novo index_id sem invalidar índice histórico ainda retido.

**Critério de conclusão.** Navegação hierárquica real disponível sem embeddings nem chamada a serviço externo.

---
#### Etapa 21 — Instrumentar enriquecimento por modelo no processamento

**Commit único:** `feat(processing): govern model-assisted indexing through runtime ports`  
**Trailer:** `Plan-Step: 21/60`  
**Dependências:** 13, 14, 20

**Objetivo.** Permitir resumos e refinamento estrutural com os mesmos controles de credenciais, custo e observação da Woobe.

**Áreas.** DocumentModelGateway, composição de providers/model operations, metering e eventos de ProcessingJob.

**Implementação detalhada:**

1. Definir chamadas de sumarização/refinamento com entrada limitada, schema de saída, timeout e budget agregado por job.
2. Injetar provider/modelo congelados na receita, respeitando configuração e aprovação de Environment; não ler chave global de outro tenant.
3. Registrar tokens/custo quando reportados, cache por receita/origem e checkpoints de chamadas concluídas; resultado incerto não dispara cobrança duplicada por retry cego.
4. Marcar summaries como derivados inferidos; validar que locators e ranges retornados pelo modelo pertencem ao documento e nunca são aceitos como autoridade.

**Testes e evidências a produzir:**

- Fake provider determinístico para contrato e um ensaio real com provider autorizado para o caminho anunciado.
- Dois jobs concorrentes de credenciais diferentes não cruzam configuração, payload, cache ou resultado.
- Timeout, output inválido, budget esgotado e provider revogado produzem estados tipados e custo contabilizado quando conhecido.

**Critério de conclusão.** Enriquecimento por modelo passa pelo controle da Woobe, sem cliente paralelo ou chave global mutável.

---
#### Etapa 22 — Integrar PageIndex local como indexador substituível

**Commit único:** `feat(indexing): add a pinned local PageIndex adapter`  
**Trailer:** `Plan-Step: 22/60`  
**Dependências:** 19, 20, 21

**Objetivo.** Entregar a abordagem PageIndex com contratos e autorização da Woobe, sem adotar seu storage/chat como plataforma paralela.

**Áreas.** `artifacts/infra/indexers/pageindex_adapter`, dependency lock, notices e fixtures de conformidade.

**Implementação detalhada:**

1. Auditar a API da revisão upstream escolhida e fixar SHA/versão; registrar claramente quais caminhos PDF/Markdown são realmente suportados.
2. Executar índice local em scratch exclusivo e converter a saída para DocumentIndex, preservando o mapa de páginas/blocos existente.
3. Usar gateway instrumentado para chamadas de modelo; integrar subset estrutural/shim mínimo atribuído se a biblioteca não aceitar injeção, sem monkeypatch global de clientes/segredos.
4. Validar completude/ranges e implementar fallback nativo apenas por policy explícita, retornando engine efetiva. Não usar PageIndex Cloud, seu chat loop ou um filesystem global para todos os clientes.

**Testes e evidências a produzir:**

- Executar a biblioteca/algoritmo real em PDFs textuais e confrontar nós/páginas com fixtures verificáveis.
- Testar concorrência de jobs, reinício, documento sem sumário, output fora de range, falha de modelo e fallback identificado.
- Comprovar que storage/índices de um Workspace não são descobertos por outro e que ausência do extra não impede inicialização.

**Critério de conclusão.** Adapter PageIndex real, versionado e intercambiável; nenhuma capacidade cloud é anunciada como local.

---
#### Etapa 23 — Implementar busca textual e descoberta de documentos

**Commit único:** `feat(search): add scoped workspace and document text retrieval`  
**Trailer:** `Plan-Step: 23/60`  
**Dependências:** 04, 05, 19, 20, 22

**Objetivo.** Permitir localizar documentos relevantes antes de navegar suas árvores, sem varrer o catálogo inteiro no prompt.

**Áreas.** Índice textual PostgreSQL, catálogo, queries as-of e resultados/cursors de busca.

**Implementação detalhada:**

1. Indexar títulos, paths, metadados permitidos, headings e texto normalizado com language config definida; preservar caracteres importantes de fórmulas/código em busca exata.
2. Filtrar Project, Environment, Workspace, catálogo e revogação dentro da consulta, antes de ranking/retorno.
3. Retornar snippets bounded com SourceRefs e estado de cobertura; oferecer busca literal e textual, sem exigir embeddings.
4. Atualizar índices idempotentemente por publicação/revisão e remover resultados após exclusão; não misturar resumo gerado com fonte original sem identificação.

**Testes e evidências a produzir:**

- Consultas em português, termos raros, referência a apêndice, nomes duplicados e documento sem correspondência.
- Cursors adulterados, mudança concorrente de revisões e tentativa de search em Workspace alheio.
- Planos SQL e paginação em massa sem carregamento global de todos os documentos.

**Critério de conclusão.** Busca escopada devolve trechos citáveis da revisão correta e informa ausência/corte de resultados.

---
#### Etapa 24 — Expor navegação, leitura e resolução de fontes

**Commit único:** `feat(api): expose document outlines bounded reads and citations`  
**Trailer:** `Plan-Step: 24/60`  
**Dependências:** 12, 19, 20, 22, 23

**Objetivo.** Criar a interface comum de leitura que servirá API, Explorer e Tools dos Agents.

**Áreas.** Casos de uso documentais, endpoints de índices/representações/SourceRef e fixtures públicas.

**Implementação detalhada:**

1. Implementar árvore parcial com cursor/depth, leitura por node/page/linha/bloco, seleção de representação e imagens de páginas/figuras autorizadas.
2. Retornar limite aplicado, has_more/continuation, cobertura e IDs exatos; leitura truncada nunca aparenta completude.
3. Resolver referências em lote limitado para citações/previews, com página física/rótulo e bounding box apenas quando existirem.
4. Garantir que referência histórica não aponta ao current revision após rename/reprocessamento e que fonte expurgada retorna indisponibilidade sem substituição.

**Testes e evidências a produzir:**

- Read de capítulo que atravessa páginas, árvore com muitos filhos, continuação de leitura e cache condicionado à autorização.
- Resolver referências exatas antes/depois de rename, nova revisão, revogação e purga.
- Paridade dos mesmos payloads entre caller direto e facade usada pelo runtime.

**Critério de conclusão.** Navegação e fontes funcionam ponta a ponta com contrato estável e leitura limitada verificável.

---

### Bloco 25–32 — Bindings, Agents, Networks e protocolo de runtime

#### Etapa 25 — Versionar bindings e permissões nas definições de Agents

**Commit único:** `feat(agent): version artifact bindings and runtime policies`  
**Trailer:** `Plan-Step: 25/60`  
**Dependências:** 03, 06, 13, 24

**Objetivo.** Configurar Artifacts como capability genérica congelada nas definições e Releases.

**Áreas.** Agent/Network schemas, settings/runtime config, validators, release snapshots e portable package contracts.

**Implementação detalhada:**

1. Adicionar artifacts.enabled, workspace_binding, ações/limites e referência de processing profile; default desligado para definições existentes.
2. Validar binding contra contrato External Context, scope e modelo/estratégia; field ausente, scope divergente ou configuração incoerente são erros de autoria.
3. Congelar policy/receita/versões em Releases sem congelar conteúdo vivo de todos os Workspaces; mudanças de grants atuais continuam prevalecendo.
4. Atualizar serializers/export/import/hashes de forma compatível; exportação carrega requisitos lógicos e não IDs/arquivos privados de usuários.

**Testes e evidências a produzir:**

- Roundtrip Draft→Staging→Release→export/import com e sem Artifacts; preservar hashes e comportamento de Releases históricas.
- Rejeitar definição com capability de Tool em modelo incompatível, sem impedir estratégia de imagem sem Tools.
- Editar default de Project não altera silenciosamente policy de Release congelada.

**Critério de conclusão.** Artifacts configurável e versionado, com compatibilidade retroativa comprovada.

---
#### Etapa 26 — Resolver Workspace na Acceptance pelo External Context

**Commit único:** `feat(runtime): bind authorized workspaces through external context`  
**Trailer:** `Plan-Step: 26/60`  
**Dependências:** 05, 06, 25

**Objetivo.** Selecionar o ambiente de arquivos antes de qualquer chamada ao modelo, sem conceder acesso por ID.

**Áreas.** Agent Acceptance, External Context resolver, Session continuity e RuntimeArtifactBinding.

**Implementação detalhada:**

1. Resolver o campo configurado, validar Project/Environment/grant e persistir Workspace efetivo e versão observada de catálogo na Acceptance.
2. Respeitar scope=session e omissão posterior já exigida; falhar antes de execução quando Workspace obrigatório faltar ou não for autorizado.
3. Permitir scope=run com guardas de continuidade: mudança de Workspace numa Session stateful com histórico anterior exige outra Session.
4. Não expor IDs técnicos ocultos ao modelo; contexto amigável só é injetado se o contrato autoriza model.expose e permanece dado, não instrução.

**Testes e evidências a produzir:**

- Novo vínculo, repetição pública de campo session já fixado, valor diferente, grant revogado e Workspace inexistente.
- Mesmo Agent alterna estudos usando Sessions distintas; Session stateful não mistura material/histórico de Workspaces.
- Agents legados e stateless sem Artifacts continuam com sua identidade e fluxo anteriores.

**Critério de conclusão.** Run aceita conhece exatamente seu Workspace e autorização; não existe criação implícita ou troca silenciosa de contexto.

---
#### Etapa 27 — Propagar escopo e permissões dentro de Networks

**Commit único:** `feat(network): constrain artifact access per node and child run`  
**Trailer:** `Plan-Step: 27/60`  
**Dependências:** 25, 26

**Objetivo.** Compartilhar arquivos entre especialistas sem ampliar privilégios na delegação.

**Áreas.** Network definition/release, Node policies, agent invocation bridge e child Session binding.

**Implementação detalhada:**

1. Adicionar permissões redutivas por Node e registrar sua policy na definição congelada da Network.
2. Propagar binding resolvido pela Network Session/Run às chamadas internas; não permitir que o modelo escolha outro workspace_id.
3. Interseccionar permissões da Network, do Agent Release e do Node; operações diretas do Agent fora da Network continuam com seu próprio contexto.
4. Permitir transferência de ArtifactRef produzido por um Node a outro autorizado; bloquear Node sem capacidade inclusive para listagem/metadados.

**Testes e evidências a produzir:**

- Rede A escreve, B lê, C não pode listar nem abrir URL; Node com grant mais amplo não amplia o grant da raiz.
- Replay interno idêntico de campos fixos é tratado conforme contrato existente; conflito interno é erro.
- Cancelamento, nova tentativa e child reattach conservam binding e referências sem duplicar artefatos.

**Critério de conclusão.** Cooperação multi-Agent funciona com isolamento por Node e identidade de Workspace única na execução.

---
#### Etapa 28 — Congelar fontes utilizadas sem copiar o Workspace inteiro

**Commit único:** `feat(runtime): pin artifact source manifests to run catalog versions`  
**Trailer:** `Plan-Step: 28/60`  
**Dependências:** 04, 19, 24, 26, 27

**Objetivo.** Garantir reprodutibilidade das leituras e citações em Workspaces vivos de alta cardinalidade.

**Áreas.** SourceManifest, consultas as-of, artifact output overlay e journal de uso de fontes.

**Implementação detalhada:**

1. Usar catalog_version capturada na Acceptance para resolver listagens/buscas e fixar revisões representações/índices durante leitura.
2. Persistir manifest apenas das fontes realmente utilizadas, com locators e hashes, e deduplicar leituras repetidas.
3. Permitir read-your-writes por referências explícitas de artefatos da própria Run/Nodes autorizados, sem enxergar todas as mudanças concorrentes.
4. Revalidar acesso atual em replay/reattach; fonte purgada ou revogada fica unavailable, nunca é substituída por latest.

**Testes e evidências a produzir:**

- Atualizar/remover documento durante geração, reprocessar índice, renomear arquivo e retomar após crash.
- Duas Runs concorrentes veem seus catálogos e artefatos próprios conforme regra, sem snapshot integral do Workspace.
- Escala do tamanho do manifest depende das fontes utilizadas, não do número total de arquivos.

**Critério de conclusão.** Run e conteúdo gerado possuem fontes exatas e reconstituíveis quando ainda autorizadas/retidas.

---
#### Etapa 29 — Aceitar mensagens com partes e referências tipadas

**Commit único:** `feat(runtime): add backward-compatible multimodal content parts`  
**Trailer:** `Plan-Step: 29/60`  
**Dependências:** 12, 24, 25, 26, 28

**Objetivo.** Estender input/output sem converter todo conteúdo para strings ou quebrar clientes textuais.

**Áreas.** DTOs públicos Agent/Network, message persistence, prepared input e contract validation.

**Implementação detalhada:**

1. Adicionar content_parts de texto e ArtifactRef, com revisão, tipo e validação de vínculo; rejeitar combinações ambíguas com input legado.
2. Normalizar payload textual antigo para representação interna compatível; não exigir texto quando operação válida aceita somente imagem.
3. Persistir referências em mensagens/histórico e metadados do resultado, sem bytes/base64/URLs assinadas duráveis.
4. Validar formatos/capabilities e disponibilidade de revisão antes de invocar provider; documentar resposta segura a cliente antigo.

**Testes e evidências a produzir:**

- Matriz de input string, parts textuais, texto+imagem, somente imagem e referências não autorizadas.
- Roundtrip histórico, streaming/síncrono e Agent/Network; clientes antigos recebem projeção textual coerente.
- IDs de outra Session/Workspace, revisão inexistente e tipo de arquivo incompatível falham antes do provider.

**Critério de conclusão.** Entrada multimodal aditiva e tipada, com comportamento textual legado preservado.

---
#### Etapa 30 — Disponibilizar capacidades internas de navegação e escrita

**Commit único:** `feat(agent): expose governed artifact and document tools`  
**Trailer:** `Plan-Step: 30/60`  
**Dependências:** 23, 24, 25, 26, 27, 28, 29

**Objetivo.** Dar ao Agent acesso operacional aos documentos pelo mesmo backend da API direta.

**Áreas.** Runtime capability inventory, Tool schemas internos, facade Artifacts e registros de Tool execution.

**Implementação detalhada:**

1. Registrar list/inspect/search/outline/read/write/process conforme ações efetivas e disponibilidade; Workspace vem do runtime e não de argumentos livres.
2. Retornar resultados compactos com referencias e continuação, mantendo lista de Tools limitada e nomes estáveis.
3. Usar o mecanismo existente de chamadas/evidências de Tools para idempotência de escrita e observação; não criar um terceiro protocolo externo.
4. Process retorna job_id e status; acompanhamento respeita limite e só usa suspensão durável se comprovadamente suportada, sem polling infinito.

**Testes e evidências a produzir:**

- Agent encontra capítulo, lê origem e grava resumo via execução real de Tools com modelo determinístico de teste.
- Chamadas diretas por nome de Tool não exposta continuam negadas; alterar argumentos não troca escopo.
- Falha de processamento não vira resposta vazia bem-sucedida; write repetido reutiliza recibo.

**Critério de conclusão.** Agents navegam e produzem arquivos com ferramentas autorizadas, sem shell nem storage client exposto.

---
#### Etapa 31 — Controlar orçamento de leitura e montagem de contexto

**Commit único:** `feat(context): budget artifact exploration and preserve source fidelity`  
**Trailer:** `Plan-Step: 31/60`  
**Dependências:** 28, 29, 30

**Objetivo.** Evitar que exploração documental descarregue o Workspace inteiro no prompt ou esconda truncamento.

**Áreas.** ContextManager/assembler, policies de fontes, PreparedContext e limitações de Tool results.

**Implementação detalhada:**

1. Integrar textos/figuras selecionados ao prepared context com source type e trust explícitos; não tratar documento como instrução do sistema.
2. Aplicar budgets de bytes/tokens/páginas/chamadas e limitar profundidade/rodadas de investigação, com erro ou continuação explícita.
3. Deduplicar trechos idênticos já lidos por revisão/locator; resumos podem auxiliar navegação, mas não substituir automaticamente fonte citada.
4. Preservar distinção entre estimativa textual e unidades multimodais desconhecidas; registrar cobertura parcial sem afirmar contagem exata fictícia.

**Testes e evidências a produzir:**

- Documento muito grande, nó com tabela extensa, busca ampla e leitura repetida respeitam limite e indicam conteúdo não lido.
- Instruções maliciosas em PDF/Markdown não mudam grants, system prompt ou destinos de transferência.
- Compaction mantém SourceRefs e não troca revisão nem mistura contextos de Workspaces.

**Critério de conclusão.** Contexto é limitado, rastreável e não confunde ausência de leitura com ausência de informação.

---
#### Etapa 32 — Persistir artefatos de saída e projetá-los no streaming

**Commit único:** `feat(runtime): persist artifact outputs and resumable stream projections`  
**Trailer:** `Plan-Step: 32/60`  
**Dependências:** 11, 28, 29, 30, 31

**Objetivo.** Entregar resultados multimodais duráveis e reconstruíveis sem reexecutar trabalho.

**Áreas.** Run result contracts, event journal/projections existentes, run.state e SSE protocol v2.

**Implementação detalhada:**

1. Adicionar output_artifacts/source_refs aos resultados síncronos e projeções, com schema version e compatibilidade de campos existentes.
2. Publicar artefato em storage/catalog antes do evento ready; usar recibo/outbox para recuperar falha entre persistência e emissão.
3. Emitir eventos de criação, disponibilidade e processamento sem blobs/segredos, preservando run_id/session_id/event_id/sequence.
4. Reconstruir run.state com referências e status; observar novamente uma Run não invoca modelo, Tool, processamento ou geração de imagem.

**Testes e evidências a produzir:**

- Queda de SSE antes/depois de artifact.ready, sequência faltante, Redis indisponível e leitura de Run terminal do armazenamento durável.
- Terminalização concorrente com upload de saída não anuncia arquivo ausente.
- Duas observações do mesmo Run apresentam os mesmos IDs e não aumentam número de revisões.

**Critério de conclusão.** Artefatos aparecem em resultados/reattach com identidade estável e sem execução duplicada.

---

### Bloco 33–39 — Tools externas, multimodalidade e exploração fundamentada

#### Etapa 33 — Transferir arquivos por Tools HTTP configuradas

**Commit único:** `feat(tools): bind artifact inputs to authorized HTTP transfers`  
**Trailer:** `Plan-Step: 33/60`  
**Dependências:** 05, 12, 25, 28, 30, 32

**Objetivo.** Permitir que um Agent envie arquivos a processamento externo sem tornar a Tool um proxy arbitrário.

**Áreas.** Tool definitions, FileTransferBinding, guarded HTTP executor e ArtifactTransferReceipt.

**Implementação detalhada:**

1. Adicionar binding de campo de Tool para ArtifactRef e modo permitido multipart/bytes/url, com MIME, tamanho e destino congelados.
2. Resolver bytes com autorização atual e transmitir em streaming; URLs temporárias só para destinatário aprovado e curta duração.
3. Aplicar egress/redirect/DNS/private network policies existentes, credenciais server-side e idempotency key quando o destino suportar.
4. Registrar recibo com referência/hash enviados; ausência de resposta não autoriza replay automático de efeito externo.

**Testes e evidências a produzir:**

- PDF→HTTP com multipart real e hash do conteúdo, autorização de leitura sem transfer negada e destino fora da policy bloqueado.
- Redirecionamento para host não aprovado, arquivo muito grande, MIME incompatível e cancelamento durante stream.
- ACK perdido com/sem suporte remoto à idempotência resulta respectivamente em reconciliação ou estado incerto explícito.

**Critério de conclusão.** Transferência HTTP funciona por contrato de Tool, sem URLs livres nem vazamento de blobs no contexto.

---
#### Etapa 34 — Transferir arquivos por MCP conforme o contrato negociado

**Commit único:** `feat(mcp): support schema-bound artifact transfer and resource results`  
**Trailer:** `Plan-Step: 34/60`  
**Dependências:** 28, 30, 32, 33

**Objetivo.** Adicionar interoperabilidade MCP sem inventar um protocolo universal de upload.

**Áreas.** MCP provider/Tool bindings, transport adapters e normalização de resultados estruturados.

**Implementação detalhada:**

1. Validar schema/capabilities do servidor e configurar como um campo de arquivo será materializado: URL autorizada, bytes limitados ou etapa HTTP contratada.
2. Negar envio de caminhos locais/URIs internas como se o servidor remoto pudesse abri-los; ausência de binding compatível é erro tipado.
3. Tratar structuredContent/resource_link/content blocks conforme versão negociada, com autorização e leitura segura de recursos disponíveis.
4. Preservar permissões allow/review/deny e normalização de isError; não alterar credenciais ou escopo de sessão MCP por argumento do modelo.

**Testes e evidências a produzir:**

- Peer MCP de teste real com upload contratual, recurso retornado, erro isError e servidor que não suporta arquivos.
- URI externa não aprovada, recurso maior que limite e esquema que muda após discovery.
- Teste de isolamento de cache/sessão por binding/contexto e de compatibilidade com Tools MCP textuais antigas.

**Critério de conclusão.** Arquivos atravessam MCP somente nos modos efetivamente suportados e autorizados.

---
#### Etapa 35 — Ingerir outputs externos e reconciliar operações demoradas

**Commit único:** `feat(artifacts): ingest external tool outputs with durable provenance`  
**Trailer:** `Plan-Step: 35/60`  
**Dependências:** 14, 19, 32, 33, 34

**Objetivo.** Transformar respostas de processamento externo em artefatos persistentes sem duplicação ou perda de autoria.

**Áreas.** Output bindings de Tool, transfer receipts, ingestion use cases e callbacks/polling configurados.

**Implementação detalhada:**

1. Aceitar respostas binárias, refs de recursos ou JSON com arquivos, validando MIME/hash/tamanho e schema antes de publicar.
2. Criar novo Artifact/revisão com lineage entrada→Tool/provider→Run→saída; resultados inferidos não substituem o original.
3. Persistir operation_ref remoto quando fornecido e suportar reconciliação apenas por endpoint/callback previamente autorizado e autenticação verificável.
4. Não manter request SQL aberto durante espera e não criar um executor assíncrono genérico paralelo; resultado tardio é associado à operação original e status atual.

**Testes e evidências a produzir:**

- Tool gera Markdown/imagem, resposta é perdida após ingestão, callback é duplicado e polling retorna ready repetidamente.
- Output com hash divergente, URL não autorizada, payload parcial ou erro de aplicação não é publicado como ready.
- Resultado tardio após cancelamento/revogação não reabre acesso nem cria nova Run sem pedido.

**Critério de conclusão.** Resultados externos tornam-se artefatos verificáveis, com retomada e estados incertos honestos.

---
#### Etapa 36 — Executar entrada visual sobre referências autorizadas

**Commit único:** `feat(models): resolve artifact images for vision-capable providers`  
**Trailer:** `Plan-Step: 36/60`  
**Dependências:** 19, 25, 28, 29, 31, 32

**Objetivo.** Permitir que o Agent examine figuras, páginas e imagens preservadas no Workspace.

**Áreas.** ModelOperation adapters, ModelSpec compatibility, prepared inputs e provider inicial OpenAI.

**Implementação detalhada:**

1. Implementar tradução ArtifactRef→bloco de imagem/arquivo no provider inicial, com limites reais e URL/bytes autorizados conforme API oficial.
2. Consultar effective capability e estratégia suportada, não nome presumido de modelo; modelo textual incompatível falha antes de receber bytes.
3. Permitir leitura de figura/página renderizada com origem e revisão fixadas; não enviar todas as páginas do PDF automaticamente.
4. Manter bytes/base64 apenas no boundary do provider quando necessários, sem persistir em mensagens, logs ou eventos públicos. Modelo exato é configurado/pinado na qualificação, não hardcoded no domínio. [S17]

**Testes e evidências a produzir:**

- Contrato com provider peer verificando payload visual e um smoke real com credencial autorizada.
- Arquivo ausente/revogado, imagem excessiva, tipo incompatível e modelo sem visão.
- Resultado textual inclui as referências corretas; contagem multimodal desconhecida não é apresentada como medida exata.

**Critério de conclusão.** Pelo menos um adapter visual real qualificado e inputs não autorizados bloqueados antes da chamada.

---
#### Etapa 37 — Executar geração de imagem com output persistente

**Commit único:** `feat(models): generate images into artifact workspaces`  
**Trailer:** `Plan-Step: 37/60`  
**Dependências:** 25, 26, 29, 32, 36

**Objetivo.** Completar o caso em que a Woobe produz uma imagem e a disponibiliza em conversas futuras.

**Áreas.** Image ModelOperationStrategy, output validator, estratégia de invocação única e adapter inicial OpenAI.

**Implementação detalhada:**

1. Implementar image.generate com parâmetros validados a partir das capacidades do modelo/provider; não forçar semântica de chat/tool calling em modelo de imagem.
2. Usar estratégia de uma operação quando apropriado e ModelResult multimodal; ausência de texto não invalida imagem pronta.
3. Validar/armazenar cada resultado com quota, MIME e hash antes de emitir readiness; devolver ArtifactRefs, usage e origem da Run.
4. Tratar timeout/cancelamento/resultado incerto sem repetir cobrança cegamente; consulta posterior e reattach recuperam o mesmo artefato. Seguir contrato oficial e não fixar modelos depreciados no core. [S18]

**Testes e evidências a produzir:**

- Peer de provider gera bytes fixture; smoke real produz arquivo que pode ser baixado e referenciado em nova Run.
- Falha após retorno do provider antes da publicação, múltiplas imagens, quota excedida e imagem inválida.
- Run image-only chega ao terminal correto e reattach não gera uma segunda imagem.

**Critério de conclusão.** Geração nativa de imagem executável com resultado durável e compatibilidade de modelos validada.

---
#### Etapa 38 — Tornar recuperação legada opcional sem quebrar Releases

**Commit único:** `feat(knowledge): allow artifact-only agents with legacy RAG compatibility`  
**Trailer:** `Plan-Step: 38/60`  
**Dependências:** 25, 30, 31, 36, 37

**Objetivo.** Permitir exploração documental sem pipeline vetorial obrigatório e sem redefinir a semântica histórica de Knowledge.

**Áreas.** KnowledgeStrategy registry/config, NoKnowledgeStrategy, author validators e package compatibility.

**Implementação detalhada:**

1. Registrar seleção explícita none/no-op no contrato canônico e na autoria; campo omitido continua resolvendo para rag histórico.
2. Garantir que artifact tools operam independentemente de KnowledgeStrategy e que desabilitar RAG não remove arquivos ou capacidade de busca.
3. Não injetar resultados de Artifacts automaticamente em paralelo às Tools nem executar dois retrievers sem configuração explícita.
4. Preservar Collections/Vector Snapshots/Releases antigos e hashes; qualquer migração de documentos legados é opt-in e separada da seleção de estratégia.

**Testes e evidências a produzir:**

- Regressões de Agents legados, import/export sem novo campo, releases congeladas e configurações com rag explícito.
- Agent artifact-only usa busca/árvore/leitura sem embeddings, Collection ou vector snapshot.
- Desabilitar Knowledge não permite ignorar policies de Context/Tools/Artifacts.

**Critério de conclusão.** Novos Agents dispensam recuperação vetorial; comportamento legado permanece intacto.

---
#### Etapa 39 — Criar Skill de exploração documental fundamentada

**Commit único:** `feat(skills): add bounded evidence-based document exploration`  
**Trailer:** `Plan-Step: 39/60`  
**Dependências:** 24, 30, 31, 38

**Objetivo.** Orientar o Agent a usar a capacidade documental com método, sem transformar instruções de Skill em autorização.

**Áreas.** Skill versionada Woobe, referências de Tools e exemplos de consulta/produção de conteúdo.

**Implementação detalhada:**

1. Definir procedimento localizar→inspecionar sumário→ler fontes→comparar→produzir→citar, com uso de imagens quando a extração textual for insuficiente.
2. Exigir abertura do conteúdo original para afirmações relevantes; summaries servem à navegação e cobertura parcial deve ser reportada.
3. Definir orçamento de investigação e regras contra leitura repetida, pesquisa infinita e confusão entre fonte e instrução.
4. Declarar required_tools reais e exemplos genéricos; instalação/versionamento seguem infraestrutura de Skills existente e nunca criam grants.

**Testes e evidências a produzir:**

- Validar pacote, referências e required_tools contra o inventário; testar instalação por versão e restore de Release.
- Cenários de apêndice cruzado, tema inexistente e tabela ilegível devem produzir ação/limitação adequadas.
- Agent sem Tools autorizadas não ganha acesso por ativar a Skill.

**Critério de conclusão.** Skill utilizável e versionada, com orientação fundamentada e sem privilégios implícitos.

---

### Bloco 40–45 — SDKs, CLI e contratos de clientes

#### Etapa 40 — Ampliar SDK Go para acesso direto aos Workspaces

**Commit único:** `feat(sdk-go): add workspace artifact and processing clients`  
**Trailer:** `Plan-Step: 40/60`  
**Dependências:** 02, 12, 24

**Objetivo.** Permitir que a Lipo e outros backends operem arquivos sem executar um Agent.

**Áreas.** `clients/woobe-sdk-go/`: typed clients, transport, errors, pagination e examples.

**Implementação detalhada:**

1. Adicionar APIs de Workspace, Artifact, upload intent/part/finalize, download, processamento, busca, árvore e fontes usando os schemas canônicos.
2. Usar Runtime Key com interface artifacts e grants explícitos; não adicionar CRUD administrativo de Agent nem fallback para Control Key.
3. Preservar uso de biblioteca padrão Go, context.Context por operação, io.Reader/io.Writer e hooks do HTTP client existentes.
4. Implementar retorno de recibos/cursors e erros recuperáveis, sem retries automáticos de mutações incertas ou envio de secrets em URLs/logs.

**Testes e evidências a produzir:**

- Contract tests com servidor HTTP real de teste para upload streaming, Range, cancelamento, paginação e ACK perdido.
- Executar gofmt, vet e race, testes standalone GOWORK=off e no workspace do monorepo.
- Compilar exemplo de aplicação criando Workspace e baixando a revisão exata sem Run.

**Critério de conclusão.** SDK Go oferece o acesso direto completo e tipado sem alterar o escopo de autenticação existente.

---
#### Etapa 41 — Ampliar SDK Go para multimodalidade e eventos

**Commit único:** `feat(sdk-go): support artifact-aware runs and stream recovery`  
**Trailer:** `Plan-Step: 41/60`  
**Dependências:** 29, 32, 36, 37, 40

**Objetivo.** Consumir Runs com arquivos e resultados multimodais preservando APIs textuais.

**Áreas.** Chat/Run options, ContentPart/ArtifactRef/SourceRef, result models e protocolo v2 do SDK Go.

**Implementação detalhada:**

1. Adicionar métodos/opções para parts sem mudar assinaturas textuais existentes; validar ambiguidade local antes do POST quando possível.
2. Decodificar outputs de artefatos, fontes e novos eventos, tolerando campos aditivos sem ignorar identidade/protocolo inválidos.
3. Preservar external context exatamente fornecido pelo chamador; não reenviar silenciosamente campo session-scoped fixado.
4. Reattach reconcilia run.state e referências; download é operação explícita/lazy e não efeito colateral de receber evento.

**Testes e evidências a produzir:**

- Fixtures Agent/Network textuais antigas e novas, imagem-only, output com múltiplos artefatos e erro de fonte.
- Sequência interrompida e reconexão conservam Run ID e não fazem segundo POST; cancelamento continua explícito.
- Exemplo Go: carregar apostila→executar Tutor→ler citações→baixar resultado, sem chave no código.

**Critério de conclusão.** Consumidor Go completa o fluxo multimodal e mantém compatibilidade de streaming/reattach.

---
#### Etapa 42 — Entregar paridade no SDK Python

**Commit único:** `feat(sdk-python): add artifact workspaces multimodal parts and receipts`  
**Trailer:** `Plan-Step: 42/60`  
**Dependências:** 02, 12, 24, 29, 32, 36, 37, 40, 41

**Objetivo.** Oferecer os mesmos contratos ao cliente Python sem divergência semântica entre linguagens.

**Áreas.** `clients/woobe-sdk-python/src/woobe/`, tipos, client surfaces, resultados e documentação.

**Implementação detalhada:**

1. Adicionar Workspace/Artifacts/Processing/Search/Document clients e referências tipadas; manter comportamento async/sync suportado pelo SDK existente.
2. Implementar upload/download incremental com fechamento de handles, cancelamento e limites, sem leitura integral obrigatória de arquivos grandes.
3. Expandir chat/run/results/stream para content_parts e artefatos, preservando lazy execution e métodos legados.
4. Consumir as mesmas fixtures de erro, recibos, paginação, External Context e protocolo v2 do SDK Go.

**Testes e evidências a produzir:**

- Rodar testes standalone e contrato cruzado Python↔API↔Go para os mesmos dados.
- Validar cleanup em erro, interrupção de stream, mutação com resposta perdida e reattach.
- Construir wheel/sdist local para verificação sem upload a registro nem alteração automática de versão.

**Critério de conclusão.** SDK Python funcional e equivalente ao Go nas capacidades anunciadas.

---
#### Etapa 43 — Operar Artifacts pela CLI

**Commit único:** `feat(cli): add workspace artifact upload and document commands`  
**Trailer:** `Plan-Step: 43/60`  
**Dependências:** 02, 12, 24, 40, 41

**Objetivo.** Permitir desenvolvimento/operação por terminal sem depender do Explorer nem de scripts ad hoc.

**Áreas.** `clients/woobe-cli/internal/cli/`, command discovery, output formats e integração com SDK Go.

**Implementação detalhada:**

1. Adicionar grupos de Workspace e Artifact conforme catálogo congelado: create/list/resolve/get/upload/download/move/revisions/process/tree/read/search.
2. Usar Control Key apenas em operações administrativas e Runtime Key em APIs públicas; seleção de contexto/Environment/Workspace explícita.
3. Suportar JSON/compact/tabelas e cursores; manter IDs e recibos necessários à recuperação, sem imprimir bytes/base64 no output normal.
4. Download e upload usam streams e confirmação em operações destrutivas; salvar checkpoint local privado para retomada, sem secrets.

**Testes e evidências a produzir:**

- Golden tests de help/discovery, outputs, campos selecionados e erros; integração HTTP real com upload/retomada.
- Casos de paths com espaços/Unicode, piping, stdout vs stderr e download incompleto sem arquivo final falsamente válido.
- CLI usa SDK local novo no monorepo e não duplica transporte/runtime auth.

**Critério de conclusão.** CLI opera Workspaces e documentos com comportamento previsível para humanos e Agents de programação.

---
#### Etapa 44 — Atualizar autoria CLI, pacotes e skill de desenvolvimento

**Commit único:** `feat(cli): author artifact bindings and multimodal runtime manifests`  
**Trailer:** `Plan-Step: 44/60`  
**Dependências:** 25, 29, 38, 39, 41, 43

**Objetivo.** Concluir o fluxo YAML→validação→Draft/Release testável para as novas capacidades.

**Áreas.** Decode de runtime_input, manifest/package authoring, skill embarcada e referências offline da CLI.

**Implementação detalhada:**

1. Aceitar content_parts em inputs de runtime e referências exatas; manter input string, rejeitar spelling incorreto e campos duplicados/conflitantes.
2. Exportar/importar artifacts policy, logical workspace requirements e profiles pinados; preservar hashes legados e não exportar arquivos privados por padrão.
3. Atualizar discovery/schema/validate-input/diff/dry-run para refletir suporte real do servidor e reportar capability ausente.
4. Atualizar skill e exemplos de External Context session/run, uploads, PageIndex opcional, fontes e transferências; diferenciar skill da CLI da Skill runtime documental.

**Testes e evidências a produzir:**

- Roundtrip do YAML de Agent e Network, payload multimodal e fallback de servidor antigo.
- Export package não contém binários, secrets, signed URLs ou workspace IDs de usuários; binding de destino requer resolução autorizada.
- Executar CLI end-to-end até validação/teste em ambiente isolado, sem promover produção ou publicar releases de plataforma.

**Critério de conclusão.** Autoria e operações de CLI acompanham a API e permitem validar todo o fluxo sem edição manual de estados internos.

---
#### Etapa 45 — Estender o runtime-client compartilhado do navegador

**Commit único:** `feat(runtime-client): decode artifact content and stream state`  
**Trailer:** `Plan-Step: 45/60`  
**Dependências:** 29, 32, 41, 42

**Objetivo.** Compartilhar tipos/protocolo entre UI e ChatSurface sem duplicar parsers de eventos.

**Áreas.** `packages/woobe-runtime-client/src/`, fixtures TypeScript e interfaces de transporte.

**Implementação detalhada:**

1. Adicionar tipos de ContentPart, ArtifactRef, SourceRef e ArtifactOutput com validação do envelope v2.
2. Decodificar eventos incrementais e run.state mantendo semântica de replacement; suportar campos aditivos com checagem de identidade.
3. Expor primitives de paginação/referência sem acoplar React, auth administrativa, upload UI ou execução de Run ao pacote de protocolo.
4. Compartilhar fixtures com SDKs para impedir que UI e clientes interpretem disponibilidade/cancelamento de maneira diferente.

**Testes e evidências a produzir:**

- Unit tests de stream quebrado, evento fora de ordem, duplicata, fonte removida e arquivo ainda processing.
- Typecheck/build standalone e consumidores Web/Embed com payload textual legado.
- Comprovar que apenas observar eventos não dispara download, upload nem geração.

**Critério de conclusão.** Runtime-client reconhece artefatos de forma comum e compatível com o protocolo existente.

---

### Bloco 46–51 — Explorer, Playground, Network e ChatSurface

#### Etapa 46 — Criar Explorer de Workspaces e arquivos

**Commit único:** `feat(ui): add paginated artifact workspace explorer`  
**Trailer:** `Plan-Step: 46/60`  
**Dependências:** 12, 24, 45

**Objetivo.** Oferecer navegação humana sobre os mesmos dados acessíveis por API e Agents.

**Áreas.** `woobe-frontend/features/artifacts`, rotas project-scoped, component library e visual inventory.

**Implementação detalhada:**

1. Criar listagem de Workspaces com busca/paginação, identidade externa sob detalhes, Environment visível e criação autorizada.
2. Implementar árvore/lista de arquivos paginada/virtualizada, breadcrumbs, sort, upload, rename/move e ações conforme permissões efetivas.
3. Mostrar original, revisão, tamanho, origem e estado de processamento separadamente; agrupar derivados em Representações.
4. Preservar identidade visual e componentes existentes; loading/erro/empty/partial são estados distintos e seleção tardia de outro Workspace não reaproveita conteúdo antigo.

**Testes e evidências a produzir:**

- Browser fixtures e integração real para upload/listagem/mutação, inclusive trocar Workspace durante request em voo.
- Telas 1366×768, 1440px, 768px, 390px e 320px, nomes longos, teclado e foco.
- Inspecionar renderização para evitar árvore/cabeçalhos consumindo quase toda a área útil.

**Critério de conclusão.** Explorer funcional, responsivo e paginado sem reduzir segurança a controles visuais.

---
#### Etapa 47 — Criar leitor documental com árvore e fontes

**Commit único:** `feat(ui): add document reader with hierarchy and source provenance`  
**Trailer:** `Plan-Step: 47/60`  
**Dependências:** 24, 46

**Objetivo.** Permitir verificar o material que fundamenta o trabalho do Agent.

**Áreas.** Document viewer, tree browser, representation tabs, source overlays e controles de leitura.

**Implementação detalhada:**

1. Exibir Markdown sanitizado, PDF/página, figuras e tabelas; selecionar nó navega para o local correto no original quando o mapa existe.
2. Permitir árvore progressiva e busca de seções sem carregar todo documento; mostrar coverage parcial e missing OCR de forma explícita.
3. Oferecer histórico de revisões/representações e links de citações para a revisão exata, sem substituir automaticamente por latest.
4. Em telas pequenas alternar árvore/leitor/detalhes por tabs ou drawer; não manter múltiplas sidebars simultâneas.

**Testes e evidências a produzir:**

- Citação de página física vs rótulo impresso, imagem com bbox e Markdown sem páginas.
- HTML/SVG malicioso sanitizado, documento removido, representação não pronta e download interrompido.
- Visual/keyboard/accessibility em breakpoints e zoom, preservando foco ao abrir/fechar referência.

**Critério de conclusão.** Usuário consegue inspecionar fontes exatas e entender limites de extração sem sair do fluxo.

---
#### Etapa 48 — Configurar Artifacts nos editores de Agent e Network

**Commit único:** `feat(ui): configure artifact bindings profiles and permissions`  
**Trailer:** `Plan-Step: 48/60`  
**Dependências:** 25, 26, 27, 38, 46

**Objetivo.** Tornar configurável a capability sem exigir edição manual de JSON interno.

**Áreas.** Agent editor, Network inspector, External Context form, profile selectors e release views.

**Implementação detalhada:**

1. Adicionar seção Artifacts com enable, campo de binding, scope, permissões e budgets; mostrar quais capacidades estão realmente disponíveis.
2. Validar relação com External Context e avisar sobre binding session-scoped fixo; separar display title de identificador técnico oculto.
3. Exibir diferenças Draft/Staging/Release, profile revision e policy por Node, com interação consistente nos editores standalone e Network.
4. Não fazer grants automáticos, não carregar keys em formulário e não confundir Artifact Workspace com Workspace administrativo da conta.

**Testes e evidências a produzir:**

- Criar/editar/salvar/descartar configuração, autor sem permissão, modelo incompatível e perfil ausente.
- Testes compartilhados dos dois editores e do snapshot de Release para impedir roundtrip parcial.
- Contenção geométrica em inspector estreito, labels completas e navegação por teclado.

**Critério de conclusão.** Configuração de Artifacts utilizável na UI e fiel aos contratos e snapshots do backend.

---
#### Etapa 49 — Integrar upload, menções e resultados no Playground

**Commit único:** `feat(ui): add artifact mentions attachments and output previews`  
**Trailer:** `Plan-Step: 49/60`  
**Dependências:** 29, 32, 36, 37, 45, 46, 47, 48

**Objetivo.** Entregar o fluxo conversar sobre arquivos e produzir novos arquivos dentro da Session.

**Áreas.** ChatComposer, Playground, session stores, message rendering e galeria por capability.

**Implementação detalhada:**

1. Adicionar upload com progresso/cancelamento/retomada e impedir envio de refs ainda não committed.
2. Implementar autocomplete @ por Workspace, desambiguação de nomes e chip contendo revisão/arquivo selecionado; payload final é tipado.
3. Mostrar outputs gerados, previews, downloads e citações; modelo de imagem usa controles/galeria compatíveis, sem chat textual artificial obrigatório.
4. Ao trocar estudo/Workspace, selecionar/criar Session correspondente; não reaproveitar histórico anterior nem exibir resultados tardios no novo contexto.

**Testes e evidências a produzir:**

- Upload→@referência→resposta fundamentada→imagem gerada→nova mensagem citando essa imagem.
- Nome duplicado, rename depois de selecionar, revisão apagada, falha de upload e perda do stream.
- Reload/reattach não dispara novo envio e reconstrói artefatos do backend.

**Critério de conclusão.** Playground usa arquivos de ponta a ponta com UX clara e identidade de contexto preservada.

---
#### Etapa 50 — Integrar Explorer e artefatos ao fluxo visual de Networks

**Commit único:** `feat(ui): expose network artifact scope and node outputs`  
**Trailer:** `Plan-Step: 50/60`  
**Dependências:** 27, 32, 45, 46, 47, 48, 49

**Objetivo.** Tornar visível quem produziu/consumiu arquivos sem duplicar o Explorer por Node.

**Áreas.** Network workspace/canvas, Node inspector, execution details e filtros do Explorer.

**Implementação detalhada:**

1. Exibir Workspace efetivo da Network Session e arquivos da Run/Node como filtros sobre o catálogo comum.
2. Detalhar ações permitidas por Node e proveniência das saídas, sem deixar a UI editar permissões da Release em execução.
3. Reutilizar componentes de Explorer/leitor e garantir que o canvas permaneça a área central útil.
4. Representar saídas de imagem e documento entre Nodes por referência; Node negado não recebe metadados via um painel compartilhado indevido.

**Testes e evidências a produzir:**

- Rede com produtor/leitor/Node negado, reattach, cancelamento e nova Run na mesma Session.
- Comparar interface e resposta do backend para permissões reduzidas e fontes removidas.
- Browser layout em 1366×768 e mobile, sem recortar canvas ou esconder ações essenciais.

**Critério de conclusão.** Operação multi-Agent e seus artefatos ficam compreensíveis e coerentes com a autorização real.

---
#### Etapa 51 — Entregar paridade no ChatSurface/Embed

**Commit único:** `feat(embed): add scoped artifact conversations and downloads`  
**Trailer:** `Plan-Step: 51/60`  
**Dependências:** 26, 29, 32, 45, 47, 49, 50

**Objetivo.** Levar arquivos à superfície browser-facing sem expor credenciais da aplicação.

**Áreas.** ChatSurface server-side sessions, embed transport/composer, uploads e downloads contextuais.

**Implementação detalhada:**

1. Resolver binding a partir do contexto autenticado emitido pelo backend da superfície; visitante não escolhe Workspace global por query string.
2. Reutilizar content parts, upload/referências, preview e reattach; aplicar limites específicos da Surface sem ampliar policy do Agent.
3. Encaminhar bytes por endpoints autorizados/tokens curtos, mantendo Control/Runtime Keys amplas fora do browser e do iframe.
4. Propagar logout/revogação e trocar contexto de forma explícita; não compartilhar cache de documentos entre sessões/usuários.

**Testes e evidências a produzir:**

- Duas sessões de visitantes com Workspaces diferentes, upload cruzado, URL reutilizada e token expirado.
- Fluxo completo no embed: anexo→resposta→citação/download→reload, sem segundo POST.
- Compatibilidade com Surfaces textuais antigas e estados sem capability de arquivo.

**Critério de conclusão.** ChatSurface oferece os mesmos recursos com isolamento efetivo do acesso direto da aplicação.

---

### Bloco 52–60 — Operação, compatibilidade, qualificação e encerramento Draft

#### Etapa 52 — Instrumentar operações, custos e auditoria passiva

**Commit único:** `feat(observability): trace artifact processing retrieval and transfer`  
**Trailer:** `Plan-Step: 52/60`  
**Dependências:** 14, 21, 28, 32, 35, 37, 51

**Objetivo.** Permitir operar e diagnosticar a capacidade sem expor conteúdo privado ou criar acoplamento de controle no Observer.

**Áreas.** Audit events, metrics/tracing existentes, metering, project summaries e logs seguros.

**Implementação detalhada:**

1. Registrar operações de Workspace/Artifact, etapas de processamento, busca/leitura, transferências, negações e uso de modelo por correlação.
2. Separar bytes armazenados, bytes lidos/transferidos e custo reportado/estimado/desconhecido; não confundir cache hit com execução de modelo.
3. Usar labels agregadas de baixa cardinalidade e IDs apenas em eventos/traces autorizados; redigir tokens, URLs assinadas, corpos e texto de documentos.
4. Expor cobertura, engine real, profile version, latency e fila, sem exportar raciocínio privado do modelo nem fazer o Observer escolher ações.

**Testes e evidências a produzir:**

- Testes de redaction de headers/query/body e inexistência de workspace_id/user_id como label ilimitada.
- Correlação source→job→Run→Artifact output, inclusive chamadas diretas sem Run.
- Falha de exportador de observabilidade não reverte publicação de artefato já concluída.

**Critério de conclusão.** Operação é auditável e mensurável sem alterar fluxos nem divulgar dados/segredos.

---
#### Etapa 53 — Empacotar perfis de execução e capacidades opcionais

**Commit único:** `chore(deploy): add optional document worker profiles and capability probes`  
**Trailer:** `Plan-Step: 53/60`  
**Dependências:** 13, 14, 17, 18, 22, 36, 37, 52

**Objetivo.** Entregar uma instalação executável sem transformar parsers/modelos pesados em requisito universal.

**Áreas.** Pyproject/locks, Dockerfiles/Compose, volumes, configuration e startup probes.

**Implementação detalhada:**

1. Empacotar perfil leve, perfil documental/OCR e extra PageIndex no pacote de Workers, com locks e modelos provisionados por manifesto.
2. Manter API/Core/execuções textuais iniciáveis sem extras; probes distinguem processo vivo, fila consumida e capacidade instalada.
3. Configurar limites de CPU/memória/concurrency, scratch efêmero, storage compartilhado/S3 e graceful shutdown de leases.
4. Adicionar flags de disponibilidade para API, processing, runtime bindings e superfícies; sem publicação de imagens ou mudança automática de versão.

**Testes e evidências a produzir:**

- Compose mínimo sem extras e Compose documental com PostgreSQL/queue/object store reais, verificando bootstrap e migrations.
- Worker sem pesos/OCR/PageIndex anuncia indisponibilidade; UI não oferece funcionalidade falsamente habilitada.
- Build reproduzível e usuário não root com volume/scratch graváveis; sem download de dependência iniciado por um Agent.

**Critério de conclusão.** Perfis operacionais claros e instaláveis, sem serviço externo obrigatório de conhecimento.

---
#### Etapa 54 — Preparar upgrade e rollback compatíveis

**Commit único:** `feat(compat): preserve legacy runtime and package contracts during rollout`  
**Trailer:** `Plan-Step: 54/60`  
**Dependências:** 25, 29, 32, 38, 40, 41, 42, 44, 51, 53

**Objetivo.** Habilitar a evolução sem quebrar Releases, chaves, Sessions ou clientes antigos.

**Áreas.** Migrations/compatibility readers, capability negotiation, ASaC/package contracts e rollout fixtures.

**Implementação detalhada:**

1. Validar upgrade de base populada, lazy initialization de campos opcionais e schemas legados; não criar Workspace para cada Session existente automaticamente.
2. Garantir que import/export/autoria compreendem policies novas e que artefatos privados não entram em closure de releases de configuração.
3. Definir desligamento por feature flags preservando metadados/bytes e observação de Runs; nenhum rollback de código executa DROP de dados novos.
4. Rejeitar operação nova em servidor antigo por capability explícita; não degradar referência de arquivo silenciosamente para texto sem conteúdo.

**Testes e evidências a produzir:**

- Clientes antigos↔servidor novo e clientes novos↔servidor antigo, cobrindo erros previsíveis e texto legado.
- Sessions já existentes com campos session-scoped, Releases anteriores sem artifacts e snapshots/hashes persistidos.
- Ensaio upgrade→uso→feature off→feature on e restauração de configuração anterior em ambiente de teste.

**Critério de conclusão.** Compatibilidade documentada e testada, com rollback conservador e sem migração destrutiva automática.

---
#### Etapa 55 — Validar dois acessos com consumidor de referência

**Commit único:** `test(integration): qualify direct and agentic workspace access end to end`  
**Trailer:** `Plan-Step: 55/60`  
**Dependências:** 24, 26, 27, 28, 32, 35, 37, 39, 41, 42, 44, 51, 54

**Objetivo.** Comprovar o cenário da Lipo usando somente contratos públicos e sem alterar seu domínio/repositório.

**Áreas.** `tests/integration/artifacts/`, consumidor Go de referência, fixtures de produto genéricas e suites HTTP.

**Implementação detalhada:**

1. Criar dois usuários sintéticos de aplicação e três Workspaces: duas jornadas de um usuário e uma de outro, no mesmo Project técnico.
2. Provisionar/upload/processar via SDK Go; executar o mesmo Tutor em Sessions separadas por Workspace; comparar visão direta e agentic.
3. Gerar documento/imagem, abrir fonte/citação, encaminhar arquivo a HTTP/MCP peer e consumir resultado em Run posterior.
4. Simular app backend que valida dono e delega scope; usar também tokens restritos de ChatSurface, sem assumir que uma chave backend ampla identifica sozinha o aluno.

**Testes e evidências a produzir:**

- Fluxo real API/worker/PostgreSQL/storage; models sintéticos para determinismo e smokes reais identificados separadamente.
- Troca ENEM→Matemática não mistura histórico/arquivos; usuário B não acessa bytes/metadados/citações do A.
- Interrupção/restart do consumidor e reattach preservam Run/revisões/recibos originais.

**Critério de conclusão.** Os dois acessos ao mesmo Workspace funcionam de ponta a ponta com isolamento, sem APIs internas especiais para Lipo.

---
#### Etapa 56 — Concluir retenção, purga, exportação e restauração

**Commit único:** `feat(operations): manage artifact retention garbage collection and restore`  
**Trailer:** `Plan-Step: 56/60`  
**Dependências:** 06, 10, 11, 19, 23, 28, 35, 52, 53, 54, 55

**Objetivo.** Manter consistência entre catálogo, objetos, derivados e índices durante todo o ciclo de vida.

**Áreas.** Lifecycle workers, GC/reconciler, export manifests, backup/restore runbooks e ferramentas operacionais.

**Implementação detalhada:**

1. Implementar purga assíncrona de Workspace/revisão e cleanup de staging/multipart órfão, respeitando referências retidas e estado de publicação.
2. Remover resultados de busca/caches após exclusão; citações antigas mostram source_unavailable e não buscam latest.
3. Exportar originais/derivados/índices autorizados com manifesto de hashes e versões; download em streaming, sem ZIP expansion perigosa no core.
4. Ensaiar backup consistente de metadados/objetos e restauração com reconciliação de exclusões; documentar janela e procedimento sem prometer apagar cópias fora do controle da Woobe.

**Testes e evidências a produzir:**

- Purge concorrente com upload/processamento/leitura e queda no meio da remoção; repetição converge sem apagar objetos válidos.
- Restore de Workspace com múltiplas revisões verifica hashes, índice e refs; exclusão posterior ao backup não reexpõe dados.
- Run histórica continua observável no que for permitido, mesmo com arquivo expurgado.

**Critério de conclusão.** Lifecycle completo e recuperação operacional comprovada em ambiente de teste.

---
#### Etapa 57 — Ensaiar alta cardinalidade, concorrência e falhas

**Commit único:** `perf(artifacts): qualify scale bounds backpressure and recovery`  
**Trailer:** `Plan-Step: 57/60`  
**Dependências:** 14, 23, 24, 28, 32, 35, 51, 52, 53, 56

**Objetivo.** Validar que muitos Workspaces não viram contexto, conexões ou filas ilimitadas.

**Áreas.** Load harness, datasets sintéticos, fault injection e relatórios de queries/resources.

**Implementação detalhada:**

1. Gerar catálogo reproduzível com pelo menos 10 mil Workspaces, 100 mil artefatos e 1 milhão de blocos distribuídos, sem documentos privados.
2. Medir list/resolve/search/read e concorrência de uploads/jobs, registrando hardware, parâmetros, percentis e planos SQL.
3. Validar backpressure/fairness entre Workspaces/Projects, limites de memória/bytes por chamada e limpeza de leases/streams.
4. Injetar falhas de worker, banco, broker, Redis e object store; preservar resultados já aceitos e explicitar degraded/uncertain sem replay indiscriminado.

**Testes e evidências a produzir:**

- Confirmar zero vazamento entre scopes sob carga e ausência de uma thread/bucket/connection dedicada por Workspace.
- Aplicar budgets de ensaio definidos previamente na seção 12; não reduzir metas depois de ver resultados sem registrar mudança de requisito.
- Comparar baseline e implementação com perfil sem LLM para separar custo do storage/DB do provider.

**Critério de conclusão.** Relatório de escala real do ambiente de teste, limites conhecidos e regressões corrigidas; sem alegar capacidade de milhões comprovada.

---
#### Etapa 58 — Avaliar qualidade de recuperação e geração fundamentada

**Commit único:** `test(retrieval): benchmark hierarchical navigation and grounded outputs`  
**Trailer:** `Plan-Step: 58/60`  
**Dependências:** 16, 17, 18, 20, 21, 22, 23, 24, 31, 39, 55, 57

**Objetivo.** Medir o ganho da nova capacidade com tarefas representativas, sem reutilizar métricas comerciais upstream.

**Áreas.** Corpus sintético/licenciado, queries/gold SourceRefs, harness de avaliação e relatório comparativo.

**Implementação detalhada:**

1. Congelar corpus, perguntas, fontes esperadas, budgets e rubrica antes da execução; incluir português, apêndices, nomes duplicados, tabelas e ausência de resposta.
2. Comparar busca textual, árvore estrutural nativa e PageIndex sob mesmo modelo/condições, registrando custo de indexação separado do custo por pergunta.
3. Medir localização de fonte, cobertura, referências válidas, groundedness, chamadas/tokens, latência e custo conhecido; não chamar resumo inferido de evidência.
4. Executar testes determinísticos de contrato e qualificação real distinta; registrar falhas, skips e campos não observáveis. Não concluir superioridade universal com uma amostra restrita.

**Testes e evidências a produzir:**

- Conjunto de 80 consultas e 20 tarefas de geração descrito na seção 12, com revisão de referências e critérios predefinidos.
- Documentos que exigem visual/OCR devem falhar honestamente se o perfil estiver indisponível; não aprovar com resposta inventada.
- Ausência de credencial/budget impede concluir a qualificação real, mas não é convertida em teste aprovado.

**Critério de conclusão.** Relatório comparativo rastreável sustenta a escolha do perfil recomendado e separa código implementado de qualidade homologada.

---
#### Etapa 59 — Concluir documentação operacional, APIs e guias de clientes

**Commit único:** `docs(artifacts): publish developer integration and operations guides`  
**Trailer:** `Plan-Step: 59/60`  
**Dependências:** 39, 40, 41, 42, 43, 44, 48, 51, 54, 55, 56, 57, 58

**Objetivo.** Tornar a capacidade operável e integrável sem depender de conhecimento informal da implementação.

**Áreas.** Docs runtime/API/architecture/operations, README de packages/clients e referências da CLI/Skill.

**Implementação detalhada:**

1. Documentar provisionamento, upload/retomada, External Context, dois acessos, autorização/delegação, troca de Sessions e exemplos Go/Python/CLI.
2. Documentar recipes, extração/OCR, índices, PageIndex opcional, limites/cobertura, custo de modelo e transferência HTTP/MCP contratual.
3. Atualizar arquitetura, OpenAPI, schemas, help, package authoring e runbooks de upgrade/rollback/backup/GC com links e comandos efetivamente testados.
4. Explicitar status Draft e ausência de publicação; não dizer que pacotes de registros/mirrors já suportam mudanças da branch. Mostrar Lipo apenas como exemplo genérico.

**Testes e evidências a produzir:**

- Executar exemplos contra a stack de teste e validar snippets/links internos e generated docs.
- Conferir que fontes externas estão pinadas/referenciadas e que licenças/avisos foram preservados.
- Checklist de coerência API↔SDK↔CLI↔UI↔Skill sem comandos ou capabilities inexistentes.

**Critério de conclusão.** Documentação completa, consistente com o código e suficiente para operar a entrega em ambiente de validação.

---
#### Etapa 60 — Auditar a entrega e encerrar mantendo o PR em Draft

**Commit único:** `chore(artifacts): finalize acceptance evidence and retain draft status`  
**Trailer:** `Plan-Step: 60/60`  
**Dependências:** 01–59; todos os gates aplicáveis.

**Objetivo.** Fechar a série de implementação com evidência por requisito, sem promover a entrega ou alterar seu estado de revisão.

**Áreas.** Ledger, matriz de aceitação, relatório final, guards de PR e manifestos de evidências do CI.

**Implementação detalhada:**

1. Conferir todos os requisitos/60 etapas, ausência de TODOs funcionais e completude dos caminhos Storage→Processing→Index→Agent→SDK/CLI/UI.
2. Rodar as suites oficiais e novas no estado final; distinguir bloqueios ambientais de defeitos e manter requisitos não homologados explicitamente abertos.
3. Reconciliar a série de exatamente 60 commits/trailers após eventuais amendments; não agregar commits soltos de correção ou merge.
4. Atualizar documentação de encerramento e corpo do único PR, registrando draft=true, auto-merge desligado, nenhum tag/release/deploy. CI sobre o SHA final é registrado como artefato externo para evitar autorreferência de hash.

**Testes e evidências a produzir:**

- Contagem e unicidade da série, git diff de escopo, schema checks, unit/integration/security/architecture/browser/SDK/CLI e smoke operacional final.
- Verificar PR por API após concluir; continua aberto e Draft, inclusive com testes verdes.
- Confirmar que não houve commits em repositórios externos, alterações no #219, publicação ou promoção de produção.

**Critério de conclusão.** Entrega e evidências concluídas quando todos os gates exigidos passam; PR permanece Draft. Pendência real é reportada, nunca mascarada para fechar o plano.

---

---

## 12. Matriz de requisitos, aceitação e validação final

### 12.1. Rastreabilidade requisito → etapas

| ID | Requisito obrigatório | Etapas principais |
|---|---|---|
| R01 | Um módulo Artifacts interno, sem microsserviço obrigatório | 01, 03, 07, 13, 53 |
| R02 | Uma branch e um PR, Draft do começo ao encerramento, 60 commits | 01, 02, 60 |
| R03 | Workspace independente e anterior a Sessions | 04, 06, 12, 26, 55 |
| R04 | Acesso direto e agentic aos mesmos arquivos | 05, 12, 24, 30, 40, 55 |
| R05 | External Context seleciona; autoridade concede acesso | 05, 25, 26, 27, 51 |
| R06 | Não misturar histórico quando trocar Workspace | 26, 28, 49, 51, 55 |
| R07 | Alta cardinalidade sem recurso dedicado por Workspace | 04, 06, 23, 46, 57 |
| R08 | Filesystem/S3, streams e integridade | 07, 08, 09, 10, 12 |
| R09 | Upload retomável e recibo idempotente | 10, 12, 40, 42, 43, 49 |
| R10 | Revisões imutáveis, rename/move e fonte histórica | 04, 11, 19, 24, 28 |
| R11 | Processamento assíncrono durável e limitado | 13, 14, 21, 53, 57 |
| R12 | Texto/Markdown/PDF/DOCX e estrutura | 15, 16, 17, 19 |
| R13 | OCR seletivo, imagens/tabelas e cobertura honesta | 16, 17, 18, 19, 47 |
| R14 | Índice hierárquico nativo sem embeddings | 20, 23, 24, 38 |
| R15 | Adapter PageIndex local e substituível | 21, 22, 53, 58 |
| R16 | Busca antes da navegação; árvore/leitura progressivas | 23, 24, 30, 31, 39 |
| R17 | Referências e citações verificáveis | 19, 24, 28, 32, 47, 58 |
| R18 | Não alimentar o contexto com biblioteca inteira | 23, 24, 28, 31, 57 |
| R19 | Transferência de arquivos para HTTP | 33, 35, 55 |
| R20 | Transferência/recursos MCP por contrato real | 34, 35, 55 |
| R21 | Arquivos externos retornam ao Workspace com origem | 11, 19, 32, 35 |
| R22 | Permissões redutivas por Node da Network | 25, 27, 30, 50 |
| R23 | Mensagens multimodais e `@arquivo` | 29, 36, 41, 42, 44, 49 |
| R24 | Geração de imagem persistida e reutilizável | 32, 37, 49, 55 |
| R25 | RAG legado opcional nos novos Agents, sem quebra histórica | 25, 38, 54 |
| R26 | SDK Go consumer-facing completo | 40, 41, 55 |
| R27 | SDK Python e paridade contratual | 42, 45, 54 |
| R28 | CLI, YAML, help e skill de desenvolvimento | 43, 44, 59 |
| R29 | UI Explorer/leitor/Playground/Network responsiva | 46, 47, 48, 49, 50 |
| R30 | ChatSurface isolada e sem chaves amplas no browser | 45, 51, 55 |
| R31 | Streaming/reattach não duplica efeitos | 28, 32, 35, 37, 41, 45, 49, 51 |
| R32 | Quotas, revogação e lifecycle de objetos | 05, 06, 10, 11, 56, 57 |
| R33 | Métricas, auditoria, backup e restauração | 52, 56, 59 |
| R34 | Compatibility de Releases/ASaC/Knowledge/clients | 07, 25, 38, 44, 54 |
| R35 | Qualidade e custos medidos, sem benchmark fictício | 21, 52, 57, 58 |
| R36 | Entrega utilizável apenas com Lipo/consumidor + Woobe | 01, 03, 53, 55, 59, 60 |

### 12.2. Cenários de aceitação de ponta a ponta

| Caso | Ação/condição | Evidência exigida |
|---|---|---|
| A01 | Aplicação cria Workspace sem Session | ID durável, resolve idempotente, catálogo vazio correto e ausência de Run criada. |
| A02 | Mesmo Agent atende dois estudos | Sessions separadas, bindings distintos, histórico/documentos sem mistura. |
| A03 | Outro usuário tenta citar arquivo do primeiro | Rejeição antes de modelo/download/Tool, sem metadados privados na resposta. |
| A04 | Acesso direto e pelo Agent | Mesmos IDs, revisões e hashes para o mesmo catálogo autorizado. |
| A05 | Upload cai após finalização no servidor | Consulta recupera mesmo recibo; nenhuma revisão extra. |
| A06 | Duas criações com mesma chave externa | Um Workspace ou conflito explícito de payload, nunca duplicação silenciosa. |
| A07 | PDF extenso é processado | Original preservado, capítulos/páginas navegáveis, cobertura e locators conferidos. |
| A08 | PDF escaneado/híbrido | OCR real quando habilitado; páginas ausentes explícitas quando não habilitado. |
| A09 | Documento com figuras, equação e tabela | Assets preservados e trecho ilegível identificado, sem texto estrutural inventado. |
| A10 | Arquivo renomeado após uma citação | Citação abre a revisão antiga correta pelo ID; nome amigável pode atualizar sem mudar fonte. |
| A11 | Original recebe nova revisão durante Run | Run usa visão/pins previstos; não mistura revision_id antigo com texto novo. |
| A12 | Reprocessar com nova receita/indexador | Novo RepresentationSet/DocumentIndex; histórico preservado. |
| A13 | PageIndex falha | Erro ou fallback nativo explicitamente autorizado e identificado; nunca engine mentirosa. |
| A14 | Buscar assunto inexistente | Ausência informada sem inventar evidência nem varrer infinitamente. |
| A15 | Capítulo aponta a um apêndice | Agent navega à origem correta dentro de budget e registra as fontes lidas. |
| A16 | Documento contém instrução para exfiltrar | Documento tratado como dado; autoridade/destinos não se alteram. |
| A17 | Tool HTTP recebe PDF | Bytes/hash corretos, destino permitido e recibo de envio; nenhuma URL arbitrária. |
| A18 | MCP não tem contrato de arquivo | `FILE_TRANSFER_UNSUPPORTED` sem simular upload ou passar path do host. |
| A19 | Tool devolve Markdown/imagem | Artifact validado e citável com lineage da entrada e Tool/Run. |
| A20 | ACK da Tool é perdido | Reconciliação via contrato remoto ou estado incerto; sem repetir efeito automaticamente. |
| A21 | Worker morre durante processamento | Nova tentativa retoma checkpoint; fence antigo não publica. |
| A22 | SSE cai ao receber arquivo gerado | Reattach mostra mesma Run/Artifact e não chama provider de novo. |
| A23 | Modelo de imagem produz sem texto | Resultado é válido e baixável; nova Run pode referenciar essa imagem. |
| A24 | Network A escreve, B lê, C é negado | Evidência de permissões efetivas e nenhuma ampliação por Node. |
| A25 | Revogar grant durante operação | Próxima leitura/transferência/publicação é reavaliada; URL já emitida obedece TTL documentado. |
| A26 | Purga de fonte citada | Busca/caches deixam de mostrá-la e histórico informa indisponibilidade sem trocar para latest. |
| A27 | Restore de backup | Catálogo/objetos/hashes consistentes e exclusões reaplicadas. |
| A28 | CLI/Go/Python/Browser repetem o mesmo fluxo | Contratos e erros equivalentes, sem baixar/uploadar implicitamente em observação. |
| A29 | Servidor novo com cliente textual antigo | Fluxo existente preservado; nenhuma exigência automática de Workspace. |
| A30 | ChatSurface e Project Explorer simultâneos | Privilégios corretos por principal, sem chave ampla no browser. |
| A31 | Tela de 1366×768 e viewport estreito | Área útil, teclado, foco, leitores e menus funcionais, sem sobreposição/clipping. |
| A32 | Encerramento da implementação | Série de 60 commits, PR aberto Draft, auto-merge off, sem release/tag/deploy. |

### 12.3. Gates técnicos por camada

**G0 — Baseline/arquitetura:** imports e boundaries permitidos; nenhum novo domínio pedagógico; Core sobe sem parsers opcionais; evidência de origem dos clientes; PR Draft.

**G1 — Persistência e storage:** migrations sobre base antiga/populada; PostgreSQL real; filesystem e S3-compatible reais; checksum, Range, multipart e intent recovery; sem blobs nos eventos/SQL de mensagens.

**G2 — Autorização:** matriz multi-Project/Environment/Workspace/principal/Node; revogação; scoping de busca/cursor/cache; testes negativos devem passar em todas as superfícies, não apenas API pública.

**G3 — Processamento:** extração nativa, Docling e OCR reais nos perfis anunciados; fixtures versionadas; jobs com kill/restart/fencing; cobertura e memória limitadas.

**G4 — Indexação/recuperação:** índice nativo e PageIndex real; locators/árvore válidos; leitura progressiva; corpus comparativo; nenhuma performance/qualidade upstream apresentada como resultado da Woobe.

**G5 — Runtime:** Acceptance/External Context/Network, content parts, imagem de entrada/saída, fontes pinadas, stream v2 e reattach. Desconectar cliente não cancela nem recria Run.

**G6 — Integração externa:** HTTP/MCP peers reais, schemas/negociação, envio e ingestão de arquivos, errors/uncertain states e proteção de destino.

**G7 — Clientes e UX:** Go/Python/CLI standalone e integração; typecheck/build Web/Embed; testes browser visuais/interação/acessibilidade com API real em casos selecionados.

**G8 — Operação/encerramento:** backups, purge, carga/fairness, modelo/provider real anunciado, docs executáveis, matriz completa e PR ainda Draft.

Não usar a quantidade de testes como substituta desses gates. Um teste `skipped` por ausência de OCR/provider não comprova a capacidade correspondente.

### 12.4. Budgets e ensaio de escala

Os números abaixo são **metas iniciais de projeto/aceitação**, não medições realizadas nem SLOs de produção. A etapa 01/13 congela os defaults finais e a etapa 57 registra os resultados.

| Item | Ponto de partida proposto |
|---|---|
| Upload | 128 MiB por arquivo no perfil padrão, configurável por policy; processamento pode ter limites menores declarados. |
| Listagem/árvore | 50 itens por página por padrão, máximo 200; depth explícita e continuação. |
| Busca | 20 resultados por padrão, máximo 100; snippets limitados. |
| Leitura textual de Tool | 64 KiB por chamada antes da montagem de contexto; budget de tokens continua sendo limite adicional. |
| Rodadas documentais | 24 chamadas por Run como default inicial configurável; término explícito ao atingir limite. |
| Transferência externa | Limite próprio por Tool/formato; nunca herdar automaticamente quota total do Workspace. |
| Corpus de carga | ≥10.000 Workspaces, ≥100.000 artefatos, ≥1.000.000 blocos, distribuição documentada. |
| Concorrência de ensaio | 50 clientes de metadados; uploads/jobs em teste separado com limites próprios. |
| Metadados/listagem | Meta inicial p95 ≤500 ms, sem upload e sem chamada LLM. |
| Busca textual | Meta inicial p95 ≤1.500 ms no corpus controlado, sem LLM. |
| Memória de leitura/escrita | Crescimento limitado pelo tamanho dos buffers/concorrência, não pelo total de bytes do arquivo ou do Workspace. |
| Ambiente de referência | Registrar CPU/RAM/disco/rede e versões; proposta inicial API 4 vCPU/8 GiB e PostgreSQL 4 vCPU/16 GiB, object store na mesma rede de teste. |

Medir throughput e latência de processing separadamente por formato, engine, páginas e hardware. Não existe um SLA único honesto para OCR, índices com modelo e geração de imagem. Ajustar metas antes do ensaio é decisão registrada; reduzir metas silenciosamente depois de falhar não encerra uma etapa.

Alta cardinalidade significa desenho sem resource-per-Workspace e acesso limitado/paginado. Não significa declarar milhões de Workspaces homologados com um teste de dez mil.

### 12.5. Avaliação de qualidade

Preparar **36 documentos sintéticos ou com licença de uso compatível**: 12 PDFs textuais, 6 PDFs escaneados/híbridos, 6 DOCX, 6 Markdown e 6 imagens com textos/figuras. JSON/CSV e casos inválidos também entram em fixtures unitárias específicas.

Congelar **80 consultas**: 24 localizações factuais, 24 navegações por estrutura, 12 referências cruzadas/apêndices, 8 consultas em múltiplos documentos, 8 consultas de tabela/imagem e 4 consultas sem resposta no corpus. Acrescentar **20 tarefas de geração**: 8 sínteses, 8 conjuntos de exercícios/perguntas e 4 documentos compostos com referências/figuras.

Para cada consulta, registrar gold sources, answerability, revisão/index_id, budget, perfil/LLM, latência, tokens/custo conhecidos, fontes efetivamente abertas e resposta. Para geração, avaliar correção sustentada por evidência, cobertura do pedido, validade de referências, respeito a formato e ausência de afirmação de leitura integral quando houve corte.

Comparar lexical, árvore nativa e PageIndex. Repetições, modelo, temperatura/seed quando suportados e critério de agregação devem ser definidos antes da execução. Não usar correspondência exata de texto como medida de qualidade generativa.

Gates invariantes: **nenhuma citação aceita para fonte não autorizada; nenhuma referência publicada como válida para locator inexistente; nenhum vazamento entre Workspaces; nenhuma execução classificada como real se usou fixture**. Metas de qualidade semântica devem ser fixadas com a rubrica antes do ensaio; o relatório identifica avaliador automático/humano e divergências. Uma melhora média não autoriza ignorar falha de isolamento.

### 12.6. Checklist de encerramento

- [ ] Os 36 requisitos da matriz possuem etapa, implementação e evidência correspondente.
- [ ] Os 32 cenários end-to-end têm resultado real registrado ou pendência explícita.
- [ ] APIs diretas funcionam antes de existir uma Session; Workspace não é propriedade descartável de conversa.
- [ ] External Context apenas seleciona e o backend autoriza todas as operações.
- [ ] Documentos originais, derivados e índices têm identidade/versionamento distintos e fontes verificáveis.
- [ ] PageIndex real é adapter opcional; perfil nativo continua útil sem ele.
- [ ] RAG histórico, Releases, Runtime Keys, streaming e clientes textuais não sofreram quebra silenciosa.
- [ ] HTTP/MCP transferem arquivos apenas por contrato aprovado e respeitam resultados incertos.
- [ ] CLI, SDK Go/Python, Web e Embed têm paridade das capacidades anunciadas.
- [ ] Imagem de entrada/geração possui smoke real do provider escolhido, não apenas tipo no ModelSpec.
- [ ] Backup/restore/purge, carga, quotas e isolamento foram ensaiados.
- [ ] Dependências/licenças/modelos estão pinados; exemplos/docs correspondem ao código final.
- [ ] A série tem exatamente 60 commits com trailer de etapa, sem PRs satélites nem alterações em master.
- [ ] O único PR permanece **aberto e Draft**, sem auto-merge, tag, release, publicação ou promoção de produção.

Se algum item obrigatório não puder ser executado no ambiente, a entrega é reportada como **implementada com qualificação pendente**, identificando o item e a evidência faltante. Não atribuir um percentual artificial de conclusão nem marcar testes não executados como aprovados.

---

## 13. Fontes, proveniência e limites da análise

As referências de Woobe apontadas por SHA documentam o estado observado. Links de clientes e projetos externos foram consultados em 20/10/2026; a implementação deve fixar revisões/dependências reais, não usar `latest` como contrato de produção. As propostas de arquitetura, nomes de entidades, limites, endpoints novos e distribuição das 60 etapas são decisões deste plano, não funcionalidades já existentes.

| ID | Fonte |
|---|---|
| S01 | [Branch master da Woobe consultada](https://api.github.com/repos/A1b3rt0M3rcad0/woobe/branches/master); SHA registrado: `3dbcb3e1a7559f4a50ebca320e411933d46e8012`. |
| S02 | [Woobe PR #219](https://github.com/A1b3rt0M3rcad0/woobe/pull/219); estado observado aberto/Draft, HEAD registrado na seção 2. |
| S03 | [Arquitetura da Woobe na baseline](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/docs/ARCHITECTURE.md). |
| S04 | [Streaming e External Context](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/docs/runtime/STREAMING.md), [contrato Agent](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/packages/woobe-core/src/modules/agent/domain/external_context_contract.py) e [contrato Network](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/packages/woobe-core/src/modules/network/domain/external_context_contract.py). |
| S05 | [Porta FileStorage existente](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/packages/woobe-core/src/modules/agent/application/interfaces/file_storage.py) e [adapters existentes](https://github.com/A1b3rt0M3rcad0/woobe/tree/3dbcb3e1a7559f4a50ebca320e411933d46e8012/packages/woobe-core/src/modules/agent/infra/storage). |
| S06 | [KnowledgeStrategy registry](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/packages/woobe-core/src/modules/agent/application/knowledge_strategy_registry.py). |
| S07 | [Rotas públicas de runtime e Jobs 501](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/packages/woobe-api/src/public_runtime_routes.py). |
| S08 | [Model Runtime](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/docs/MODEL_RUNTIME.md) e [catálogo de Execution Strategies](https://github.com/A1b3rt0M3rcad0/woobe/blob/3dbcb3e1a7559f4a50ebca320e411933d46e8012/packages/woobe-core/src/modules/agent/application/execution_strategy_registry.py). |
| S09 | [SDK Go da Woobe](https://github.com/A1b3rt0M3rcad0/woobe-sdk-go/blob/master/README.md). |
| S10 | [Input runtime da CLI](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/internal/cli/runtime_input.go). |
| S11 | [PageIndex oficial](https://github.com/VectifyAI/PageIndex): árvore documental e distinção local/cloud. |
| S12 | [PageIndex Document Processing](https://docs.pageindex.ai/sdk/documents): contratos de documento/árvore/páginas e escopo do modo local. |
| S13 | [PageIndex Agent Integration](https://docs.pageindex.ai/sdk/agents): integração de Tools; referência, não autorização substituta da Woobe. |
| S14 | [DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/): estrutura de documento. |
| S15 | [Serialização Docling](https://docling-project.github.io/docling/concepts/serialization/): representação estruturada e Markdown. |
| S16 | [MCP Tools — especificação de referência](https://modelcontextprotocol.io/specification/2025-06-18/server/tools): conteúdo estruturado e recursos. Negociar/testar a versão efetivamente implementada, sem supor upload universal. |
| S17 | [OpenAI — imagens e visão](https://developers.openai.com/api/docs/guides/images-vision): referência do adapter inicial; modelos e limites devem ser confirmados no momento da qualificação. |
| S18 | [OpenAI — geração de imagens](https://developers.openai.com/api/docs/guides/image-generation): APIs de imagem e integração de outputs. |

**Planejamento anterior consultado:** `WOOBE_PLANO_IMPLEMENTACAO_SESSION_FILES_MULTIMODAL.md`, disponível na biblioteca desta conversa. Foram preservadas sua restrição literal de PR único, a consolidação dos clientes e a cobertura multimodal; foram substituídos o acoplamento do armazenamento a uma Session e a separação obrigatória do tratamento documental. Isso é continuidade de planejamento, não evidência de código já implementado.

**Não realizado nesta elaboração:** criação de branch ou PR, alteração de repositórios, instalação de parsers, execução de providers, testes da stack, benchmarks ou deploy. O artefato entregue é o plano completo para realizar essas ações de implementação, com os limites e gates descritos acima.
