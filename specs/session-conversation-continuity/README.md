# Continuidade de Conversação Stateful — ProjectRAI

## Objetivo

Eliminar a degradação silenciosa de sessões stateful para comportamento stateless e garantir que os endpoints síncrono e streaming reconstruam exatamente o mesmo histórico, reutilizem a sessão informada e preservem o último turno da conversa.

## Branches

- baseline de diagnóstico: `development`;
- branch exclusiva de implementação: `development_session-conversation-continuity`;
- a branch de implementação deve ser criada a partir do SHA atual de `development` antes da spec 001.

## Diagnóstico principal

A causa mais provável e diretamente suportada pelo código está nos dois reconstruidores de histórico:

- `src/modules/agent/application/use_cases/ask_use_case.py`;
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py`.

Para mensagens anteriores do assistente sem tool calls, o código instancia `AIMessage(content=..., tool_calls=None)`. O contrato de `AIMessage.tool_calls` é lista, não `None`. A validação falha; em seguida, `except Exception: return []` descarta todo o histórico. O modelo recebe o turno atual sem contexto e pode responder que se trata da primeira interação.

Há quatro problemas adicionais:

1. o turno atual é salvo antes da leitura do histórico e depois anexado novamente ao prompt, duplicando a pergunta;
2. `session_id` inexistente ou inválido é silenciosamente substituído por uma nova sessão;
3. a sessão carregada não é validada contra `project_id`, `agent_id`, tenant, usuário e status;
4. o repositório retorna os 100 registros mais antigos, não os mais recentes, e ordena apenas por `created_at`.

O frontend já envia `session_id` e atualiza o valor recebido nos eventos SSE `meta` e `done`. Portanto, a ausência total de memória durante a mesma tela não deve ser atribuída primariamente ao React. O frontend ainda precisa de endurecimento para reload, troca de modo e nova conversa.

## Relação com o painel Runtime

O seletor exibido no playground é parte do próprio ProjectRAI:

- `Session Mode = Stateful`: permite criar/reutilizar sessão e persistir mensagens;
- `Session Mode = Stateless`: `_resolve_session` retorna `None`, logo não existe memória entre chamadas;
- `Status = Active`: somente autoriza a execução do agente; não controla memória.

O valor `stateful` é necessário, mas não suficiente. A continuidade depende também de:

- reutilizar o mesmo `session_id`;
- carregar o histórico sem erro;
- não degradar falhas para lista vazia;
- montar o prompt na ordem correta.

O playground envia `snapshot_override` em cada chamada; portanto, mudanças ainda não salvas no seletor de modo já podem alterar o comportamento da execução. Isso deve ficar explícito na UI e coberto por teste.

## Ordem de execução

Executar as specs em ordem numérica conforme `MANIFEST.md`. Não pular specs bloqueadas. Toda pendência deve ser registrada em `execution/runtime.md`.

## Artefatos esperados

- diagnóstico reproduzível;
- contrato stateful/stateless formalizado;
- reconstrutor de histórico único para sync e stream;
- resolução de sessão estrita e com ownership;
- janela recente e ordenação determinística;
- continuidade de sessão no playground;
- observabilidade de carga de histórico;
- testes unitários, integração, contrato e frontend;
- relatório final com evidências.

## Condição de conclusão

A correção só está concluída quando a spec 013 passa integralmente e comprova, em ambos os endpoints, que uma pergunta como “qual foi minha pergunta anterior?” recebe contexto do turno anterior usando o mesmo `session_id`.
