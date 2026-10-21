# Migração do protótipo Python para o CLI Go

Este guia compara o [protótipo inspecionado](https://github.com/A1b3rt0M3rcad0/woobe/blob/177d580eaaca4ee8743e1125c440cc3a25f0d76e/packages/woobe-cli/src/woobe_cli/main.py) com os comandos implementados neste repositório. O cliente Go é a fonte canônica; a disponibilidade de Control Keys continua dependendo do backend. A versão pública 0.13.7 e os guias atuais estão em [INSTALLATION.md](INSTALLATION.md).

## Instalação e troca do executável

1. Registre a versão/caminho da instalação antiga: `command -v woobe` em POSIX ou `Get-Command woobe` no PowerShell.
2. Instale o binário Go do archive correspondente ao sistema/arquitetura, verificando seu SHA-256 contra o manifesto do mesmo build. O archive não exige Python nem o código-fonte do backend.
3. Confira o executável selecionado com `woobe version --output json`: `data.version`, `data.commit`, `data.os` e `data.arch` identificam o artefato. Remova a instalação antiga pelo mesmo gerenciador que a instalou, evitando colisão no PATH.
4. Para desenvolvimento, use `go build -o bin/woobe ./cmd/woobe`. Para instalação reproduzível por `go install`, selecione uma tag efetivamente publicada e validada; use uma tag efetivamente publicada.

## Mapeamento de entradas

| Protótipo Python | Cliente Go | Observação |
| --- | --- | --- |
| `--url` | `--api-url` | `WOOBE_API_URL` permanece disponível. |
| `--api-key` ou `WOOBE_API_KEY` | Referência `--credential` ou `WOOBE_CONTROL_KEY` | A referência aponta para uma chave importada; não contém o segredo. Flags com o valor da chave e o nome legado da variável não são aceitos. |
| `request METHOD PATH --data @body.json` | `request METHOD PATH --file body.json` | `--file -` lê JSON de stdin; não existe `--data` literal. |
| `request ... --query KEY=VALUE` | Mesmo formato repetível | Paths devem começar com `/`; URLs externas e redirects são recusados. |
| `request ... --form` / `--file FIELD=PATH` | Upload dedicado de Knowledge | O HTTP genérico aceita JSON. Não há substituto genérico para formulários/multipart nesta versão. |
| `control-key list --workspace W` | Mesmo alias, ou `workspace control-key list --workspace W` | Mesmo handler canônico, sem política de autorização separada. |
| `control-key create --name ... --permissions ... --grants ...` | `workspace control-key create --workspace W --file key.json --secret-file issued.json` | Os campos passam no documento HTTP, com `permissions` em array e `project_grants`. A resposta com segredo fica exclusivamente no arquivo privado. |
| `control-key update --key-id K ...` | `workspace control-key update K --workspace W --file patch.json` | PATCH distingue campos ausentes, `null`, listas vazias e valores. |
| `control-key revoke --key-id K` | `workspace control-key revoke K --workspace W --yes` | Revogação exige confirmação explícita pelo flag. |
| `control-key rotate --key-id K ...` | `workspace control-key rotate K --workspace W --file rotate.json --secret-file issued.json` | Documento é opcional quando o servidor permite; destino não pode existir. |

Os aliases preservam nomes de famílias; não preservam todos os flags antigos. Consulte `woobe help --output json` e `woobe schema --command "workspace control-key create"` antes de migrar um script. Use `server-schema` para os DTOs anunciados pelo servidor, pois os campos do catálogo local não substituem seus contratos.

## Contextos e credenciais

O protótipo inspecionado não persistia perfis nem cookies. Crie o contexto explicitamente; não copie configurações de uma implementação Python diferente sem verificar seu formato.

```bash
woobe context create dev --api-url http://localhost:8000
woobe auth credential import --name editor --stdin < control-key.txt
woobe context credential attach dev --credential editor
woobe context use dev
woobe context set --workspace WORKSPACE --project PROJECT
```

O arquivo `control-key.txt` do exemplo precisa já existir com acesso protegido. A importação não concede autoridade no servidor. Para runtime, importe outra referência e use `context runtime-credential attach dev --runtime-credential runtime`; o cliente nunca usa a chave administrativa como fallback do runtime.

Precedência: flag explícito → variável de ambiente → contexto → default. Um flag explicitamente vazio limpa o valor herdado naquela invocação. Um Workspace diferente limpa o Project herdado, salvo Project fornecido explicitamente por flag/ambiente. `context show NAME` seleciona o perfil informado; `context unset NAME workspace` remove Workspace e Project do perfil. `context unset NAME credential runtime-credential` remove somente referências, preservando os segredos armazenados.

Configuração v1 recusa campos desconhecidos, duplicados, versão incompatível, contexto ativo inexistente, nomes inválidos e URLs com credenciais/query/fragment. Leitura é limitada a 1 MiB. Correções devem preservar o formato documentado; falha de validação não substitui um arquivo existente.

POSIX oferece arquivos privados como fallback; não há migração automática para keychains. Windows usa Credential Manager para Control/Runtime Keys locais; variáveis de ambiente continuam opcionais. Cookies humanos não são importados do protótipo; autentique novamente contra a API suportada.

## Scripts, saída e recuperação

O protótipo emitia o objeto da API diretamente e texto de erro em stderr. O Go usa envelope JSON: leia `data` para o resultado e `success`/`error`/`meta` para o estado. JSONL de eventos de runtime tem contrato próprio. Segredos administrativos são redigidos; não extraia uma chave do stdout. Use o arquivo privado de emissão e preserve sua confidencialidade.

Os códigos de saída são tipados, conforme [USAGE.md](USAGE.md). Não trate todo erro como exit 2. O HTTP genérico também exige `--yes` para DELETE. Escritas não têm retry automático; uma falha de transporte pode significar resultado desconhecido. Reconcilie o recurso antes de repetir uma criação ou emissão.

Checkpoints de manifestos não existiam neste protótipo. No cliente Go, não remova um checkpoint incerto para repetir o apply: use status e reconciliação explícita. Arquivos com identidade antiga/incompatível são recusados; este guia não declara migração automática de checkpoints.

Finalize a migração verificando discovery local, contexto resolvido e leituras autorizadas na instalação de teste. O aceite final exige o fluxo real de configuração/publicação/runtime e matriz de autorização; fixtures de cliente e cross-builds não comprovam esses comportamentos do servidor.


## Continuação: validação e checkpoints

Scripts podem optar por `--validate-body` em comandos HTTP canônicos ou apply. O flag acrescenta uma leitura OpenAPI antes da escrita; não deve ser adicionado a request genérico, upload multipart ou runtime SDK. `manifest preflight` fornece evidências somente de bodies; leia a completude e use `--require-complete` quando uma validação incompleta precisa bloquear o pipeline.

Checkpoints existentes preservam o hash do plano. Arquivos com IDs/resultados fora do plano, passos terminais sem resultado ou dependências incompletas são recusados. Não corrija isso apagando um checkpoint incerto e repetindo a criação: reconcilie primeiro o que o servidor efetivamente aceitou. O novo estado `not_attempted` identifica uma escrita que não foi enviada; apply pode repetir esse passo depois de corrigir o pré-requisito, preservando os já concluídos.

O onboarding recomendado é `context create`, `context use`, `auth login --cli-key`. A descoberta requer o novo endpoint de self-discovery na Woobe; backends anteriores continuam aceitando o fluxo explícito legado.


## Optional coding assistant skill

Use the built-in `woobe skill install` after upgrading to a CLI containing this
feature, or the optional `woobe-cli-skill` npm installer. Neither migrates credentials nor replaces
the executable. Current Codex uses `.agents/skills`; choose `codex-legacy` for
`.codex/skills`. Move any existing unmanaged/custom skill before installation,
which refuses to overwrite it. Existing CLI contexts, protected credentials,
`.woobe-config`, `.state` and runtime Skills remain independent.
See [AGENT_SKILL.md](AGENT_SKILL.md) for the exact command and publication status.
