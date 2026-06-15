# 011 — add-backend-unit-integration-and-contract-tests

## Tipo

test

## Objetivo

Bloquear regressões de memória, sessão, ordenação e paridade sync/stream.

## Contexto

Os testes atuais do agent concentram-se em arquitetura, UoW e messaging. A continuidade multi-turn precisa de testes comportamentais reais.

## Pré-condições

- 003 a 010 completed.

## Alterações permitidas

- `tests/modules/agent/unit/**`;
- `tests/modules/agent/integration/**`;
- `tests/contract/**`;
- fixtures/helpers de teste.

## Alterações proibidas

- validar somente chamadas de mocks sem inspecionar prompt/estado;
- depender de provider externo real;
- usar sleeps como sincronização principal;
- omitir o endpoint streaming.

## Matriz mínima obrigatória

| Caso | Sync | Stream | Persistência | Resultado |
|---|---:|---:|---:|---|
| stateful, primeiro turno | sim | sim | sessão + 2 mensagens | retorna ID |
| stateful, segundo turno | sim | sim | mesma sessão | prompt contém turno anterior |
| assistant sem tools | sim | sim | normal | histórico preservado |
| assistant com tools | sim | sim | tool metadata | sequência válida |
| ID inexistente | sim | sim | zero nova sessão | erro explícito |
| ID de outro agent/project | sim | sim | zero writes | not found |
| stateless | sim | sim | zero sessão/mensagem | ID null |
| sessão > limite | sim | sim | sem alteração | últimos N turnos |
| erro de mapper | sim | sim | sem chamada LLM | erro explícito |
| turno atual | sim | sim | uma mensagem user | aparece uma vez no prompt |

## Cenário de aceitação principal

1. enviar `Minha última pergunta é: qual é o identificador?`;
2. receber resposta;
3. enviar `Qual foi minha pergunta anterior?` com o mesmo `session_id`;
4. fake LLM deve observar o primeiro turno no prompt;
5. resposta deve mencionar a pergunta anterior;
6. repetir em sync e stream.

## Comandos de validação

```bash
pytest tests/modules/agent/unit -q
pytest tests/modules/agent/integration -q
pytest tests/contract -q
pytest tests/architecture -q
```

## Critérios de aceite objetivos

- matriz completa implementada;
- nenhum teste usa API externa;
- falha antes da correção e passa depois;
- cobertura inclui os dois transportes.

## Rollback

Testes só podem ser removidos junto com rollback integral da funcionalidade e justificativa no runtime.

## Atualização obrigatória de runtime.md

Registrar contagem de testes, duração e próxima spec `012`.
