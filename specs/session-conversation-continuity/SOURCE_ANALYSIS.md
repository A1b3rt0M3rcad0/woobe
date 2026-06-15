# Análise da Fonte — Continuidade de Sessão

## Escopo inspecionado

Baseline lógica: branch `development`, analisada em 2026-06-15.

| Arquivo | SHA do conteúdo inspecionado | Evidência |
|---|---|---|
| `src/modules/agent/application/use_cases/ask_use_case.py` | `37dfb8c8e0782ed9dca06708860c17b884aae612` | salva turno atual antes de carregar histórico; reconstrói `AIMessage` com `tool_calls=None`; suprime qualquer erro e retorna `[]` |
| `src/modules/agent/application/use_cases/ask_agent_stream_service.py` | `88d7e6b3c127aef5b1d8a3c524bc97ae55165588` | repete os mesmos três comportamentos no caminho streaming |
| `src/modules/agent/infra/database/repositories.py` | `558631abb6a7aca44b41f8aaaecd8b22e78cd09b` | `get_by_id` levanta `SessionNotFoundError`; `list_by_session` ordena ascendente e limita os registros mais antigos |
| `src/modules/agent/infra/database/mappers.py` | `2857968192c0504aa2d0aa0e02966feb8cb05c52` | mensagens sem tool calls são persistidas com `data=None` ou sem `tool_calls` |
| `src/modules/agent/application/dtos/runtime_dtos.py` | `5f4871079f542724680817ff7bad55913759b4fa` | `AskInput.session_id` é opcional e está disponível nos dois fluxos |
| `web/src/pages/AgentPlaygroundPage.tsx` | `836a23fca4f399651734205b45457a8b08ec3e87` | envia `session_id`, captura `session_id` dos eventos `meta`/`done` e mantém em state local |
| `web/src/features/playground/api.ts` | `243b4856182ed4e0326c5c25fb6ca995ff16c3f9` | serializa `session_id` no request e normaliza o ID retornado no stream |
| `web/src/features/playground/components/AgentSettingsTab.tsx` | `967ddedc87e1bef5d1fadd159f6695a25bff4e1e` | painel Runtime expõe `stateful/stateless` e `active/inactive` |
| `web/src/features/playground/AgentEditorContext.tsx` | `c6615db0bc07d85c444aa2f25402fbb5646f6b18` | `snapshot_override` inclui `session_mode`, inclusive quando a alteração ainda não foi salva |

## Cadeia causal do defeito principal

1. O primeiro request stateful cria uma sessão e persiste a mensagem do usuário.
2. A resposta do assistente normalmente é persistida sem `data.tool_calls`.
3. No segundo request, `_load_history` percorre a resposta anterior.
4. `raw_tool_calls` fica vazio e a variável local `tool_calls` recebe `None`.
5. O código executa `AIMessage(content=m.content, tool_calls=tool_calls)`.
6. `AIMessage.tool_calls` possui tipo lista; `None` é entrada inválida para a validação Pydantic.
7. O `except Exception` externo captura a falha e retorna `[]`.
8. Nenhum erro é exposto, logado ou registrado no trace.
9. O prompt é montado sem turnos anteriores e o agente se comporta como em primeira interação.

Confiança do diagnóstico: **alta (0,95)**. A cadeia está presente, de forma idêntica, nos fluxos sync e stream. A reprodução deve ser confirmada pela spec 001 no ambiente do projeto.

## Defeito de duplicação do turno atual

Nos dois fluxos:

1. `_save_user_message(...)` é chamado;
2. `_load_history(...)` consulta a sessão e inclui essa nova mensagem;
3. `_build_messages(...)` executa `messages.extend(history)`;
4. `_build_messages(...)` adiciona novamente `HumanMessage(content=user_message)`.

Resultado: o turno atual pode aparecer duas vezes no prompt. Isso distorce respostas, tool calls, contagem de tokens e testes de continuidade.

## Defeito de resolução silenciosa da sessão

`_resolve_session` captura qualquer exceção de `get_by_id` e cria uma nova sessão. Como o repositório já levanta `SessionNotFoundError`, um ID inválido deveria produzir erro explícito. O comportamento atual transforma erro de integridade em uma conversa nova, sem avisar o cliente.

A sessão retornada também não é comparada com:

- `project_id` do request;
- `agent_id` em execução;
- `tenant_id` e `user_id`, quando informados;
- status `closed`, `expired` ou `error`.

## Defeito de janela de histórico

`list_by_session(session_id, offset=0, limit=100)` usa:

```python
.order_by(MessageModel.created_at).offset(offset).limit(limit)
```

Depois de 100 mensagens, o contexto contém os turnos mais antigos, não os mais recentes. A ordenação também não possui desempate por ID.

## Avaliação do frontend

O frontend não é a causa primária durante uma sequência normal na mesma página:

- request inclui `session_id`;
- SSE `meta` atualiza `sessionId`;
- SSE `done` atualiza novamente;
- o próximo request reutiliza o state.

Gaps restantes:

- reload da página perde o `sessionId` ativo;
- a URL não identifica a sessão selecionada;
- ao trocar para stateless, um ID antigo pode continuar no state até o próximo retorno;
- o modo efetivo pode vir de um draft não salvo via `snapshot_override`, sem indicação suficientemente explícita.

## Decisão recomendada

Manter memória gerenciada pelo ProjectRAI, em banco, usando `session_id`. Não delegar continuidade a estado proprietário do provedor LLM. Essa decisão preserva portabilidade entre OpenAI, Anthropic, Google, Groq e providers customizados, além de permitir auditoria e replay.
