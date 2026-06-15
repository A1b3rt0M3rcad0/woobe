# 004 — fix-current-turn-persistence-and-prompt-order

## Tipo

refactor

## Objetivo

Garantir que o turno atual apareça exatamente uma vez no prompt e que a persistência continue atomicamente consistente.

## Contexto

O código salva a pergunta atual, carrega o histórico incluindo essa pergunta e depois anexa a pergunta novamente em `_build_messages`.

## Pré-condições

- 003 completed.

## Alterações permitidas

- use cases sync/stream do ask;
- handler de contexto compartilhado;
- testes do módulo agent;
- runtime.

## Alterações proibidas

- remover persistência do turno atual em stateful;
- persistir resposta assistant antes de conclusão do provider;
- duplicar gravação para contornar ordenação;
- manter comportamentos diferentes entre sync e stream.

## Plano de implementação

1. Carregar apenas turnos anteriores antes de persistir o turno atual, ou excluir o ID recém-criado da consulta de histórico.
2. Preferir a sequência:
   - resolver sessão;
   - carregar histórico anterior;
   - persistir pergunta atual;
   - construir prompt = system + RAG + histórico anterior + pergunta atual;
   - invocar LLM;
   - persistir resposta.
3. Garantir flush/commit necessário para expor a sessão ao stream sem encerrar prematuramente a unidade lógica.
4. Documentar a fronteira transacional do stream, que possui chamada externa longa.
5. Não incluir o turno atual por comparação textual; usar identidade/ordem, evitando remover perguntas repetidas legítimas.

## Invariantes

- quantidade de `HumanMessage` adicionada pelo turno atual = 1;
- perguntas anteriores idênticas continuam preservadas;
- persistência stateful contém exatamente um registro user e um assistant por interação concluída;
- falha antes da resposta não cria assistant vazio.

## Testes obrigatórios

- turno atual aparece uma vez;
- duas perguntas idênticas em turnos distintos aparecem duas vezes, não uma;
- stream cancelado preserva política definida para user message e não cria assistant falso;
- contagem de mensagens após N interações = 2N quando todas concluem.

## Comandos de validação

```bash
pytest tests/modules/agent/unit/application -q
pytest tests/modules/agent/integration -q
```

## Critérios de aceite objetivos

- teste de duplicação da spec 001 passa;
- ordem do prompt é determinística;
- sync e stream persistem a mesma sequência lógica.

## Rollback

Reverter a alteração de ordem junto com testes e documentação transacional.

## Atualização obrigatória de runtime.md

Registrar a sequência final e próxima spec `005`.
