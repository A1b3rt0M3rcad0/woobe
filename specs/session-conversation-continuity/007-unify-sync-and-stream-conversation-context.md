# 007 — unify-sync-and-stream-conversation-context

## Tipo

refactor

## Objetivo

Eliminar a duplicação de resolução, reconstrução e montagem de contexto entre ask síncrono e streaming.

## Contexto

Os arquivos `ask_use_case.py` e `ask_agent_stream_service.py` mantêm cópias quase idênticas de `_resolve_session`, `_load_history` e `_build_messages`. Um hotfix isolado tende a divergir imediatamente.

## Pré-condições

- 003 a 006 completed.

## Alterações permitidas

- `src/modules/agent/application/handlers/**`;
- use cases sync/stream e composers;
- ports estritamente necessários;
- testes de arquitetura e comportamento.

## Alterações proibidas

- mover regra de negócio para controller;
- instanciar infra concreta no handler compartilhado;
- criar base genérica em `shared` com semântica do agent;
- mudar payload SSE ou body sync sem teste de compatibilidade.

## Plano de implementação

1. Criar componente do módulo agent, por exemplo `ConversationContextBuilder`.
2. Entradas: `AskInput`, `Agent`, repositories/ports necessários e política de janela.
3. Saída tipada contendo:
   - sessão resolvida ou `None`;
   - histórico reconstruído;
   - lista final de mensagens do prompt;
   - contadores/truncamento;
   - ID do user message persistido, quando aplicável.
4. Sync e stream devem chamar o mesmo componente.
5. Ask job deve reutilizar o mesmo fluxo ou delegar ao use case canônico.
6. Remover métodos privados duplicados após testes passarem.
7. Adicionar teste de arquitetura que impeça nova duplicação.

## Contratos esperados

- dado o mesmo agent, input e estado de repositório, sync e stream produzem a mesma sequência de mensagens antes da chamada LLM;
- diferenças ficam restritas ao transporte da resposta;
- nenhum componente compartilhado entre módulos recebe regra de conversação.

## Testes obrigatórios

- parity snapshot do prompt sync/stream;
- mesma sessão retornada;
- mesmos contadores de histórico;
- mesmos erros para sessão inválida;
- teste de arquitetura contra métodos duplicados.

## Comandos de validação

```bash
pytest tests/modules/agent/unit/application/test_conversation_context_builder.py -q
pytest tests/modules/agent/integration/test_stream_and_non_stream_parity.py -q
pytest tests/architecture -q
```

## Critérios de aceite objetivos

- uma única implementação canônica de resolução/histórico;
- rotas e payloads existentes preservados;
- sync/stream parity comprovada.

## Rollback

Restaurar ambos os fluxos ao mesmo commit; rollback parcial é proibido.

## Atualização obrigatória de runtime.md

Registrar novo componente e próxima spec `008`.
