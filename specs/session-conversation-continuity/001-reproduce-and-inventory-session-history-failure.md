# 001 — reproduce-and-inventory-session-history-failure

## Tipo

discovery

## Objetivo

Produzir uma reprodução automatizada do defeito e um inventário completo do fluxo de sessão/mensagens antes de alterar produção.

## Contexto

A inspeção indica que `AIMessage(tool_calls=None)` falha e que a exceção é suprimida por `_load_history`. A hipótese precisa ser convertida em teste vermelho no ambiente real do projeto.

## Pré-condições

- 000 completed;
- checkout exclusivo da branch `development_session-conversation-continuity` baseado no SHA registrado de `development`.

## Estado atual a detectar

```bash
test "$(git branch --show-current)" = "development_session-conversation-continuity"
git rev-parse HEAD
rg -n "AIMessage\(content=m\.content, tool_calls=tool_calls\)" src/modules/agent
rg -n "except Exception:|return \[\]" src/modules/agent/application/use_cases/ask_use_case.py src/modules/agent/application/use_cases/ask_agent_stream_service.py
rg -n "list_by_session" src/modules/agent tests
```

## Alterações permitidas

- `tests/modules/agent/unit/application/test_conversation_history_regression.py`;
- `specs/session-conversation-continuity/execution/inventory/**`;
- `specs/session-conversation-continuity/execution/runtime.md`.

## Alterações proibidas

- alterar produção para fazer o teste passar;
- mockar `AIMessage` de forma que a validação real não seja exercitada;
- considerar o teste concluído sem observar o estado vermelho esperado.

## Plano de implementação

1. Criar teste que reconstrói uma mensagem assistant sem tool calls.
2. Demonstrar que o método atual retorna `[]`, apesar de existir histórico.
3. Criar teste que demonstre duplicação do turno atual na lista enviada ao LLM.
4. Criar teste que demonstre criação de nova sessão após `SessionNotFoundError`.
5. Inventariar sync, stream, job assíncrono, endpoints de listagem e frontend.
6. Salvar evidências em `execution/inventory/session-history-flow.md`.

## Cenário mínimo de reprodução

- turno 1 user: `Meu código é AZ-17`;
- turno 1 assistant: `Entendido.` sem tool calls;
- turno 2 user: `Qual é o meu código?`;
- mesma `session_id`;
- antes da correção, `_load_history` não pode produzir o par anterior de mensagens.

## Testes obrigatórios

- `test_assistant_without_tool_calls_must_not_erase_history`;
- `test_current_user_turn_is_not_present_twice`;
- `test_missing_session_id_must_not_create_replacement_session`.

## Comandos de validação

```bash
pytest tests/modules/agent/unit/application/test_conversation_history_regression.py -q
```

O resultado esperado nesta spec é teste vermelho para cada defeito reproduzido. Registrar o output integral. Não marcar completed se o defeito não for reproduzido; registrar hipótese rejeitada e atualizar o diagnóstico.

## Critérios de aceite objetivos

- teste reproduz a perda de histórico sem tool calls;
- teste reproduz duplicação do turno atual;
- teste reproduz fallback silencioso de sessão;
- inventário identifica todos os consumidores do fluxo;
- nenhum arquivo de produção alterado.

## Rollback

Remover os testes de caracterização somente se a hipótese for objetivamente rejeitada e o runtime registrar a evidência.

## Atualização obrigatória de runtime.md

Registrar SHA, outputs, hipóteses confirmadas/rejeitadas e próxima spec `002`.
