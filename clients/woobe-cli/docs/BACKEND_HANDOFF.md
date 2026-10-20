# Current backend boundary

The assistant skill adds no API routes or backend changes. Its documented
managed-development/package operations require the compatible backend delivered
in merged [Woobe PR #179](https://github.com/A1b3rt0M3rcad0/woobe/pull/179).
CLI examples target 0.13.7 or newer. Runtime Skills in Woobe remain distinct from
the terminal assistant skill. See [AGENT_SKILL.md](AGENT_SKILL.md).

## Historical handoff evidence

Updated 2026-10-05. The integration described below was delivered in [Woobe PR #177](https://github.com/A1b3rt0M3rcad0/woobe/pull/177), at `77c53832f0e5b35488d1574b3cf62777486f5189`. Seven workflows passed, including required real API/worker CLI scenarios and migration/upgrade acceptance. That PR was merged on 2026-10-06.

The current client continuation delivers reviewed body pagination; the existing backend PR can pin that immutable client revision and extend live category/audit history tests. Native credentials, complete semantic reconciliation and schema coverage, and stream replay/gaps remain independent client work. See [STATUS.md](STATUS.md) and [REMAINING.md](REMAINING.md).

The rest of this document is the historical handoff procedure. Its earlier percentage and zero-acceptance statements describe the pre-integration checkpoint, not current status.

## Historical backend entry procedure

O próximo bloco de implementação deve começar em `A1b3rt0M3rcad0/woobe`. O CLI já oferece descoberta, chamadas públicas, credenciais separadas, manifests recuperáveis, comparação sem perda de precisão e preflight explícito para exercitar os contratos. Isso permite iniciar a integração do servidor; não significa CLI completo, backend homologado ou autorização para release.

## Primeiro PR no backend: reconciliar a fonte canônica

1. Ler as instruções do repositório e atualizar a master através do acesso autenticado. Criar uma branch a partir dessa master. Registrar o SHA efetivo antes de editar.
2. Localizar as categorias de autoridade já implementadas, inclusive em outras branches. Preservar entidades, IDs, nomes e semântica existentes. Não criar um cadastro concorrente.
3. Comparar o Control Plane existente com `feat/cli-control-plane`; portar apenas o necessário. As referências de PLAN.md são históricas: master `42e6667`, branch `177d580`. Sua divergência e colisão de revisões Alembic exigem revisão sobre o head atual, não merge automático nem cópia da revisão `0072`.
4. Mapear os cinco contratos dependentes de branch e os doze contratos propostos pelo CLI para implementação existente, ausente ou substituída. Usar o registro do CLI e o OpenAPI efetivamente gerado pelo servidor. Não tomar uma rota anunciada como prova de autorização.
5. Entregar migração a partir do head Alembic efetivo, políticas no servidor, DTOs/OpenAPI e testes de integração do domínio que foi reconciliado. Revalidar instruções de migração em banco de teste antes de propor execução fora dele.

## Ordem dos blocos seguintes

| Bloco | Resultado verificável |
| --- | --- |
| Control Keys e categorias | Contrato canônico de CRUD, grants materializados, histórico de revisão, delegação por subconjunto e proteção da linhagem da credencial. Reutilizar o domínio localizado. |
| Autorização de operações | Matriz com humano viewer, editor, publisher e runtime; negar cross-tenant, elevação de grants, alvos/ambientes fora do escopo e produção quando proibida. Comandos dedicados e `request` passam pelas mesmas políticas. |
| Capabilities e autoridade efetiva | Introspecção consistente com as decisões reais do servidor; documentação do catálogo granular, códigos de erro e compatibilidade. |
| Recuperação e revisões | Semântica documentada de ETag/If-Match e idempotência/identidade de operações. Leitura do estado não atribui uma escrita original. Só habilitar recuperação automática com evidência autoritativa. |
| Workflow completo | Criar/configurar Agent e Network, gerar/testar release, publicar explicitamente e executar/observar com credencial runtime separada. Verificar também recusas de publicação e execução. |
| Retorno ao CLI | Atualizar rotas/DTOs contra o contrato aprovado, cobrir paginação/completude, validação de entradas e stream replay/gaps. Executar os gates reais de PLAN.md e atualizar COMPLETENESS.json somente com evidência. |

## Evidência e conclusão

Cada PR deve registrar SHA do servidor, revisão de banco, cenário/principal, comando CLI, status, request ID e resultado esperado, usando credenciais de teste e saída redigida. Guardar o OpenAPI da instância com hash e sua referência de origem. Executar o workflow em ambiente de teste com Workspace/Project identificados; excluir qualquer segredo das evidências.

A prontidão para **iniciar** o backend está atendida no cliente. A aceitação ponta a ponta permanece 0/10; o planejamento completo permanece 39/101 requisitos concluídos (38,6%). Ainda há trabalho independente no CLI, incluindo armazenamento nativo de credenciais, testes reais nas plataformas e completude de manifests. Ele pode acompanhar os PRs do servidor, sem bloquear o início da reconciliação canônica.

Nenhuma alteração no backend é entregue por este PR documental. O acesso, a master atual, o domínio de categorias e a instância de teste precisam ser verificados no início do trabalho em `woobe`; os SHAs históricos não certificam seu estado atual.
