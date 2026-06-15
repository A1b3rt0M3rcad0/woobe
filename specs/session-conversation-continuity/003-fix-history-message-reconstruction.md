# 003 — fix-history-message-reconstruction

## Tipo

refactor

## Objetivo

Corrigir a reconstrução de mensagens anteriores e impedir que uma resposta assistant sem tool calls apague todo o histórico.

## Contexto

Os dois fluxos passam `tool_calls=None` para `AIMessage`. O campo aceita lista. A validação é capturada por um `except Exception` que retorna histórico vazio.

## Pré-condições

- 002 completed;
- teste vermelho da spec 001 presente.

## Alterações permitidas

- `src/modules/agent/application/use_cases/ask_use_case.py`;
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py`;
- novo mapper/handler em `src/modules/agent/application/handlers/**`;
- `tests/modules/agent/unit/application/**`;
- runtime.

## Alterações proibidas

- capturar exceção e continuar com `[]` em modo stateful;
- remover reconstrução de tool calls e tool results;
- importar repositório concreto no componente compartilhado de aplicação;
- alterar o conteúdo persistido de mensagens existentes.

## Plano de implementação

1. Extrair a conversão `Message -> BaseMessage[]` para um único componente de aplicação.
2. Para assistant sem tool calls, construir `AIMessage(content=m.content)` sem argumento `tool_calls`.
3. Para assistant com tool calls, passar lista validada e reconstruir os `ToolMessage` correspondentes.
4. Tratar explicitamente roles `system`, `tool_call` e `tool_result`, ou rejeitá-los com erro de domínio documentado; nunca ignorar de forma acidental.
5. Substituir `except Exception: return []` por erro explícito `ConversationHistoryLoadError` ou equivalente.
6. Logar `session_id`, quantidade de registros e classe da exceção sem incluir conteúdo sensível.
7. Fazer sync e stream usarem o mesmo mapper até a consolidação completa da spec 007.

## Forma mínima correta

```python
if tool_calls:
    history.append(AIMessage(content=message.content, tool_calls=tool_calls))
else:
    history.append(AIMessage(content=message.content))
```

A forma acima é somente o hotfix mínimo; a implementação final deve centralizar a lógica.

## Testes obrigatórios

- assistant sem tool calls preserva histórico;
- assistant com tool calls preserva AIMessage + ToolMessage;
- tool call incompleta produz erro explícito;
- erro de mapper não retorna `[]`;
- sync e stream usam o mesmo resultado de conversão.

## Comandos de validação

```bash
pytest tests/modules/agent/unit/application/test_conversation_history_regression.py -q
ruff check src/modules/agent tests/modules/agent
pyright
```

## Critérios de aceite objetivos

- teste vermelho de perda de histórico passa;
- nenhum `AIMessage(..., tool_calls=None)` permanece;
- nenhum `except Exception: return []` permanece no carregamento de histórico;
- tool calls continuam funcionais.

## Rollback

Restaurar os dois fluxos e o mapper em conjunto; não deixar um caminho corrigido e outro antigo.

## Atualização obrigatória de runtime.md

Registrar arquivos, decisão de erro e evidências. Próxima spec `004`.
